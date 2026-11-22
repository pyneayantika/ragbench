"""
What it does: Returns the top chunks by dense search, or by hybrid search with optional re-ranking.
Why it exists: The generator only sees the chunks this step selects.
What breaks without it: The model answers from the wrong text.
Failure stage: retrieval.
"""
