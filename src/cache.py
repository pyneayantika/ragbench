"""
What it does: Saves and reloads parsed text, chunks, embeddings, and retrieval results on disk.
Why it exists: Re-parsing and re-embedding on every run is what froze the first attempt.
What breaks without it: Every run repeats the expensive work and can crash the laptop.
Failure stage: none (laptop and reproducibility).
"""
