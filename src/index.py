"""
What it does: Embeds chunks into ChromaDB and builds a BM25 keyword index.
Why it exists: Chunks have to be searchable by meaning and by exact words.
What breaks without it: Retrieval has nothing to search.
Failure stage: indexing.
"""
