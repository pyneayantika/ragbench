# RAGBench

**Why does your RAG give wrong answers, and which stage should you fix first?**

RAGBench benchmarks 7 retrieval-augmented generation (RAG) configurations on 3 structurally different public documents: a two-column annual report, a table-heavy mutual fund document, and long-form GHG Protocol guidance. It scores every answer against 60 hand-written test questions, then traces each wrong answer to the stage that broke: **ingestion, indexing, retrieval or generation**.

> Status: 🚧 in progress. Results will be published here when the benchmark run is complete.

## Why this exists

Teams usually blame the LLM when a RAG chatbot gives a wrong answer. But a retrieval failure and a hallucination look identical from the outside: the model writes a fluent answer from whatever text it was given. RAGBench separates the two, so a team knows whether to fix parsing, chunking, search or the prompt.

## Method in one table

Each configuration adds exactly one upgrade to the previous one:

| Config | Stage changed | Upgrade |
| --- | --- | --- |
| C1 | — | Baseline: basic parsing, fixed 256-token chunks, MiniLM embeddings, dense top-5 |
| C2 | Ingestion | Layout-aware parsing |
| C3 | Indexing | Structure-aware chunking (split by headings) |
| C4 | Indexing | Stronger embedding model (bge-small) |
| C5 | Retrieval | Hybrid search (BM25 + dense, rank fusion) |
| C6 | Retrieval | Cross-encoder re-ranking |
| C7 | Indexing | Document and section headers added to each chunk |

Held constant: generator (GPT-OSS 120B via Groq, temperature 0, low reasoning effort), prompt, judge (Mistral Medium), and the 60 questions.

## Results

_[Coming soon: best config per document, accuracy gain per upgrade, failures by stage, latency and token cost, and judge–human agreement.]_

- 📊 Dashboard: _[link]_
- 💬 Demo chat: _[link]_
- 📝 Case study: _[link]_

## Run it yourself

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add GROQ_API_KEY and MISTRAL_API_KEY
python -m src.run_benchmark --config C1 --doc fund_doc --stage retrieve --limit 3
python -m src.run_benchmark --config all --doc all --stage all
```

All tools are free: Groq and Mistral free tiers for the LLM calls; everything else runs locally.

## Repository guide

| File | What it is |
| --- | --- |
| `BRIEF.md` | Problem statement, design and build spec |
| `ARCHITECTURE.md` | Components, data flow, caching, run modes |
| `GOLDEN_SET_GUIDE.md` | How the 60 test questions were written |
| `DECISION_LOG.md` | Decisions, hypotheses and findings |
| `data/golden_set.csv` | The test set |
| `results/results.json` | All benchmark numbers |

## Limitations

- 20 questions per document: differences under about 10 points are not conclusive.
- Documents capped at about 150 pages; one generator model and one judge model.

## Author

Built by Ayantika Pyne, product manager. I defined the problem, the evaluation design, the configurations and the trade-offs, and directed the build with AI coding tools.
