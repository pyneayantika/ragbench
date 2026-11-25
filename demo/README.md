---
title: RAGBench Demo
emoji: 📊
colorFrom: blue
colorTo: gray
sdk: gradio
sdk_version: 6.32.0
app_file: demo/app.py
pinned: false
---

# RAGBench — Grounded Document Q&A Demo

Interactive Gradio demo running the winning **C7** configuration (`layout` parsing, `structure` chunking with contextual headers, `BAAI/bge-small-en-v1.5`, hybrid Dense + BM25 RRF, and `cross-encoder/ms-marco-MiniLM-L-6-v2` re-ranking) on a prebuilt index.

## Deploying to Hugging Face Spaces

1. Create a new **Gradio** Space on [huggingface.co/spaces](https://huggingface.co/spaces).
2. Add your Groq API key under **Settings → Variables and secrets → New secret**:
   - Name: `GROQ_API_KEY`
   - Value: your Groq API key (never commit `.env` or hardcode keys).
3. Push the required files to the Space repository:
   - `demo/app.py`, `demo/requirements.txt`, `demo/README.md` (copy `demo/README.md` to root `README.md` and `demo/requirements.txt` to root `requirements.txt` if deploying from Space root)
   - `src/`, `configs/`, `results/results.json`
   - Prebuilt index caches for the winning config (`C7`):
     - `cache/chunks/*__3142f573135a.jsonl`
     - `cache/bm25/*__3142f573135a.pkl`
     - `cache/chroma/` (vector store for `C7`)
   *(Note: Ensure `cache/` is included in the Space repo so the demo starts immediately without re-embedding the PDFs.)*
4. The Space will start `demo/app.py`, preload the embedding and re-ranker models once, and serve the UI.
