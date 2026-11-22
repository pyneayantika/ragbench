"""
What it does: Stores the generator and judge model IDs for every API call.
Why it exists: The brief's original models are not on these free-tier accounts, so the replacements must live in one place.
What breaks without it: Later steps could call different models and the scores would not be comparable.
Failure stage: evaluation.
"""

GENERATOR_MODEL = "openai/gpt-oss-120b"
JUDGE_MODEL = "qwen/qwen3.8-27b"
