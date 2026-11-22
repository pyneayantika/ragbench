"""
What it does: Grades each answer against the golden answer, using the fixed judge prompt.
Why it exists: Fifty-four scores by hand would not be comparable across configs.
What breaks without it: Correctness and faithfulness stay unknown.
Failure stage: evaluation.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any

from groq import APIStatusError, RateLimitError

from src.generate import get_client, pace_judge, record_judge_usage
from src.prompts import JUDGE_PROMPT
from src.settings import JUDGE_MODEL

REFUSAL = "not found in the documents"
THINK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
ALLOWED_SCORES = {0.0, 0.5, 1.0}


def fill_prompt(question: str, gold_answer: str, context: str, answer: str) -> str:
    return (
        JUDGE_PROMPT.replace("{question}", question)
        .replace("{gold_answer}", gold_answer)
        .replace("{context}", context)
        .replace("{answer}", answer)
    )


def strip_think(text: str) -> str:
    return THINK_RE.sub("", text).strip()


def _as_score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    score = float(value)
    if score in ALLOWED_SCORES:
        return score
    return None


def parse_verdict(text: str) -> dict[str, Any] | None:
    cleaned = strip_think(text)
    candidates = [cleaned]
    found = OBJECT_RE.search(cleaned)
    if found and found.group(0) != cleaned:
        candidates.append(found.group(0))
    for candidate in candidates[:2]:
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(loaded, dict):
            continue
        score = _as_score(loaded.get("correctness"))
        faithful = loaded.get("faithful")
        reason = loaded.get("reason")
        if score is None or not isinstance(faithful, bool) or not isinstance(reason, str):
            continue
        if "<think>" in reason.lower():
            reason = strip_think(reason)
        return {"correctness": score, "faithful": faithful, "reason": reason.strip()}
    return None


def _reasoning_tokens(usage: Any) -> int | None:
    details = getattr(usage, "completion_tokens_details", None)
    if details is None:
        return None
    value = getattr(details, "reasoning_tokens", None)
    return int(value) if value is not None else None


def confirm_judge_model() -> None:
    listed = get_client().models.list()
    ids = [item.id for item in listed.data]
    if JUDGE_MODEL not in ids:
        raise SystemExit(f"{JUDGE_MODEL} is not in the Groq model list. Stopping.")


def _create(prompt: str) -> Any:
    delay = 2.0
    for attempt in range(6):
        try:
            return get_client().chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                reasoning_effort="none",
                reasoning_format="parsed",
            )
        except RateLimitError as exc:
            if attempt == 5:
                raise
            delay = _retry_delay(exc, delay)
            time.sleep(delay)
            delay *= 2
        except APIStatusError as exc:
            if exc.status_code != 429 or attempt == 5:
                raise
            delay = _retry_delay(exc, delay)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("Judge call failed after 5 retries")


def _retry_delay(exc: APIStatusError, fallback: float) -> float:
    headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return max(fallback, float(retry_after))
        except ValueError:
            return fallback
    return fallback


def judge_answer(question: str, gold_answer: str, context: str, answer: str) -> dict[str, Any]:
    prompt = fill_prompt(question, gold_answer, context, answer)
    pace_judge()
    started = time.perf_counter()
    response = _create(prompt)
    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = response.usage
    total_tokens = int(usage.total_tokens)
    record_judge_usage(total_tokens)
    message = response.choices[0].message
    content = message.content if isinstance(message.content, str) else ""
    verdict = parse_verdict(content)
    base = {
        "judge_model": str(response.model or JUDGE_MODEL),
        "latency_ms": latency_ms,
        "prompt_tokens": int(usage.prompt_tokens),
        "completion_tokens": int(usage.completion_tokens),
        "reasoning_tokens": _reasoning_tokens(usage),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if verdict is None:
        base.update({"judge_error": True, "correctness": None, "faithful": None, "reason": ""})
        return base
    base.update({"judge_error": False, **verdict})
    return base


def score_unanswerable(answer: str) -> dict[str, Any]:
    correct = answer.lower().startswith(REFUSAL)
    return {
        "skipped_judge": True,
        "judge_model": None,
        "judge_error": False,
        "correctness": 1.0 if correct else 0.0,
        "faithful": None,
        "reason": "",
        "latency_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
    }
