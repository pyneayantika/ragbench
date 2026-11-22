"""
What it does: Normalises text and fuzzy-matches a supporting sentence against parsed text or a chunk.
Why it exists: PDFs change spaces and hyphens, so exact matching reports false failures.
What breaks without it: Failure attribution blames the wrong stage.
Failure stage: evaluation.
"""

from __future__ import annotations

import re

from rapidfuzz.fuzz import partial_ratio

SOFT_HYPHEN = "\u00ad"
SPACE_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    cleaned = text.replace(SOFT_HYPHEN, "")
    cleaned = cleaned.replace("-\r\n", "").replace("-\n", "")
    cleaned = cleaned.lower()
    return SPACE_RE.sub(" ", cleaned).strip()


def fuzzy_in(needle: str, haystack: str, threshold: float = 90) -> tuple[bool, float]:
    left = normalise(needle)
    right = normalise(haystack)
    if not left or not right:
        return False, 0.0
    score = float(partial_ratio(left, right))
    return score >= threshold, score
