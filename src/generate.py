"""
What it does: Asks Groq to answer from the retrieved chunks, using the fixed prompt.
Why it exists: This is the step that writes the answer, the citation, and the refusal.
What breaks without it: There is no answer, or the answer is not tied to the documents.
Failure stage: generation.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from groq import APIStatusError, Groq, RateLimitError

from src.prompts import GENERATOR_SYSTEM
from src.settings import GENERATOR_MODEL, JUDGE_RPD, JUDGE_RPM, JUDGE_TPD, JUDGE_TPM

ROOT_ENV = os.path.join(os.path.dirname(__file__), "..", ".env")
CALLS_PER_MINUTE = 6
REFUSAL = "not found in the documents"
CITATION_RE = re.compile(r"\[[A-Za-z0-9_]+ p\.\d+\]")


def normalise_answer(raw_answer: str) -> dict[str, Any]:
    answer = raw_answer.replace("\u3010", "[").replace("\u3011", "]").strip()
    return {
        "raw_answer": raw_answer,
        "answer": answer,
        "refused": answer.lower().startswith(REFUSAL),
        "has_citation": CITATION_RE.search(answer) is not None,
    }
_CLIENT: Groq | None = None
_LAST_CALL = 0.0
_JUDGE_WINDOW: list[tuple[float, int]] = []
_JUDGE_DAY_CALLS = 0
_JUDGE_DAY_TOKENS = 0
JUDGE_TOKEN_HEADROOM = 0.75


def get_client() -> Groq:
    global _CLIENT
    if _CLIENT is None:
        load_dotenv(ROOT_ENV)
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            raise SystemExit("GROQ_API_KEY is missing from .env. Do not paste the key into chat.")
        _CLIENT = Groq(api_key=key)
    return _CLIENT


def user_message(question: str, doc_id: str, passages: list[tuple[int, str]]) -> str:
    lines = [question, ""]
    for page, text in passages:
        lines.append(f'<context source="[{doc_id} p.{page}]">')
        lines.append(text)
        lines.append("</context>")
        lines.append("")
    return "\n".join(lines).strip()


def pace_judge() -> None:
    """Wait so judge calls stay under the recorded token and daily limits."""
    global _LAST_CALL
    if JUDGE_TPM is None or JUDGE_RPD is None or JUDGE_TPD is None:
        raise SystemExit("Judge TPM, RPD, or TPD is missing from src/settings.py.")
    if _JUDGE_DAY_CALLS >= JUDGE_RPD or _JUDGE_DAY_TOKENS >= JUDGE_TPD:
        raise SystemExit("Judge daily limit reached for this run. Stopping before another call.")
    cap = int(JUDGE_TPM * JUDGE_TOKEN_HEADROOM)
    rpm_cap = int(JUDGE_RPM * JUDGE_TOKEN_HEADROOM) if JUDGE_RPM else None
    while True:
        now = time.perf_counter()
        recent = [(stamp, tokens) for stamp, tokens in _JUDGE_WINDOW if now - stamp < 60]
        _JUDGE_WINDOW[:] = recent
        used = sum(tokens for _stamp, tokens in recent)
        if rpm_cap is not None and len(recent) >= rpm_cap:
            time.sleep(1)
            continue
        if used >= cap and recent:
            time.sleep(max(0.5, 60 - (now - recent[0][0])))
            continue
        break
    _LAST_CALL = time.perf_counter()


def record_judge_usage(tokens: int) -> None:
    global _JUDGE_DAY_CALLS, _JUDGE_DAY_TOKENS
    _JUDGE_WINDOW.append((time.perf_counter(), tokens))
    _JUDGE_DAY_CALLS += 1
    _JUDGE_DAY_TOKENS += tokens


def _pace(calls_per_minute: float) -> None:
    global _LAST_CALL
    gap = 60.0 / calls_per_minute
    wait = gap - (time.perf_counter() - _LAST_CALL)
    if _LAST_CALL and wait > 0:
        time.sleep(wait)
    _LAST_CALL = time.perf_counter()


def _reasoning_tokens(usage: Any) -> int | None:
    details = getattr(usage, "completion_tokens_details", None)
    if details is None:
        return None
    value = getattr(details, "reasoning_tokens", None)
    return int(value) if value is not None else None


def _create(messages: list[dict[str, str]]) -> Any:
    delay = 2.0
    for attempt in range(6):
        try:
            return get_client().chat.completions.create(
                model=GENERATOR_MODEL,
                messages=messages,
                temperature=0,
                reasoning_effort="low",
                reasoning_format="parsed",
            )
        except RateLimitError:
            if attempt == 5:
                raise
            time.sleep(delay)
            delay *= 2
        except APIStatusError as exc:
            if exc.status_code != 429 or attempt == 5:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("Groq call failed after 5 retries")


def generate_answer(
    question: str,
    doc_id: str,
    passages: list[tuple[int, str]],
    calls_per_minute: float = CALLS_PER_MINUTE,
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": GENERATOR_SYSTEM},
        {"role": "user", "content": user_message(question, doc_id, passages)},
    ]
    _pace(calls_per_minute)
    started = time.perf_counter()
    response = _create(messages)
    latency_ms = int((time.perf_counter() - started) * 1000)
    message = response.choices[0].message
    content = message.content
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Groq returned no final answer in message.content")
    usage = response.usage
    record = normalise_answer(content)
    record.update(
        {
            "latency_ms": latency_ms,
            "prompt_tokens": int(usage.prompt_tokens),
            "completion_tokens": int(usage.completion_tokens),
            "reasoning_tokens": _reasoning_tokens(usage),
            "model": str(response.model),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    return record
