"""
What it does: Sends one short request to the generator and one to the judge, both on Groq, and prints each reply.
Why it exists: The benchmark cannot start until both model IDs work on this account.
What breaks without it: A bad key or a retired model is discovered halfway through a scored run.
Failure stage: evaluation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.settings import GENERATOR_MODEL, JUDGE_MODEL

PROMPT = "Say OK"


def require_key(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"{name} is missing. Copy .env.example to .env, add the key, and run this script again. "
            "Do not paste the key into chat."
        )
    return value


def usage_line(usage: object) -> str:
    if usage is None:
        return "none"
    if hasattr(usage, "model_dump"):
        return str(usage.model_dump())
    return str(usage)


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [getattr(part, "text", "") for part in content]
        return "".join(part for part in parts if isinstance(part, str)).strip()
    return ""


def rate_limit_headers(headers: object) -> str:
    matched: list[str] = []
    for name, value in headers.items():
        lowered = name.lower()
        if any(part in lowered for part in ("retry", "ratelimit", "rate-limit", "limit")):
            matched.append(f"{name}: {value}")
    return "\n".join(matched) if matched else "(none)"


def check_model(client: Groq, label: str, model: str) -> None:
    raw = client.chat.completions.with_raw_response.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT}],
        temperature=0,
        reasoning_effort="low",
        reasoning_format="parsed",
    )
    response = raw.parse()
    message = response.choices[0].message
    print(f"{label} reply: {message_text(message.content)}")
    print(f"{label} model: {response.model}")
    print(f"{label} temperature 0 accepted: yes")
    print(f"{label} reasoning_effort sent: low")
    print(f"{label} answer source: message.content")
    print(f"{label} reasoning field present: {message.reasoning is not None}")
    print(f"{label} usage: {usage_line(response.usage)}")
    print(f"{label} rate-limit headers:\n{rate_limit_headers(raw.http_response.headers)}")


def main() -> None:
    load_dotenv(ROOT / ".env")
    client = Groq(api_key=require_key("GROQ_API_KEY"))
    check_model(client, "Generator", GENERATOR_MODEL)
    check_model(client, "Judge", JUDGE_MODEL)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"API check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
