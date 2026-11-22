"""
What it does: Normalises text and fuzzy-matches a supporting sentence against parsed text or a chunk.
Why it exists: PDFs change spaces and hyphens, so exact matching reports false failures.
What breaks without it: Failure attribution blames the wrong stage.
Failure stage: evaluation.
"""
