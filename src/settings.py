"""
What it does: Stores the generator and judge model IDs for every API call.
Why it exists: The brief's original models are not on these free-tier accounts, so the replacements must live in one place.
What breaks without it: Later steps could call different models and the scores would not be comparable.
Failure stage: evaluation.
"""

GENERATOR_MODEL = "openai/gpt-oss-120b"
JUDGE_MODEL = "qwen/qwen3.8-27b"

# Groq console on 2026-11-22 for qwen/qwen3.8-27b.
# Requests per minute was not given, so it is left unset.
JUDGE_LIMITS_SOURCE = "Groq console, 2026-11-22"
JUDGE_RPM = None
JUDGE_TPM = 8_000
JUDGE_RPD = 1_000
JUDGE_TPD = 200_000
