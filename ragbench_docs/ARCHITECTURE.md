# ARCHITECTURE.md — How RAGBench works

> Read with `BRIEF.md` Part B. This file explains **what each part does, why it exists, and what breaks without it**, so every component can be defended in an interview.

## 1. The big picture

RAGBench has two halves:

- **Offline benchmark (laptop):** runs once per config, produces numbers.
- **Online outputs (free hosting):** a static dashboard and a demo chat.

```
                         OFFLINE (laptop)                                   ONLINE
 ┌───────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐
 │ PDFs +    │─▶│ INGEST │─▶│ CHUNK  │─▶│ INDEX  │─▶│ RETRIEVE │─▶│ GENERATE │
 │ golden set│  │ parse  │  │ split  │  │ embed, │  │ dense /  │  │ Groq     │
 └───────────┘  └────────┘  └────────┘  │ BM25   │  │ hybrid,  │  └────┬─────┘
                                        └────────┘  │ rerank   │       │
                                                    └──────────┘       ▼
                                                                  ┌──────────┐
                                                                  │ JUDGE    │
                                                                  │ Mistral  │
                                                                  └────┬─────┘
                                                                       ▼
                                                                  ┌──────────┐     ┌────────────┐
                                                                  │ EVALUATE │────▶│ results.   │──▶ Dashboard (Vercel)
                                                                  │ metrics +│     │ json       │
                                                                  │ attrib.  │     └────────────┘
                                                                  └──────────┘
                        winning config ────────────────────────────────────────────▶ Demo chat (HF Spaces)
```

## 2. Components

| Module | What it does | Why it exists | What breaks without it | Failure stage it relates to |
| --- | --- | --- | --- | --- |
| `ingest.py` | Turns each PDF page into text (`basic` or `layout`) | The LLM can only use text it can read | Garbled columns and tables, so wrong answers everywhere downstream | Ingestion |
| `chunk.py` | Splits text into ≤256-token chunks (`fixed` or `structure`), optionally adds a context header | Embedding models have input limits, and retrieval needs focused pieces | Chunks too long (truncated) or answers cut in half | Indexing |
| `index.py` | Embeds chunks into ChromaDB; builds a BM25 keyword index | Makes chunks searchable by meaning and by exact words | No way to find relevant text | Indexing |
| `retrieve.py` | Finds top chunks: dense or hybrid (RRF), then optional re-rank | Picks what the LLM gets to see | The LLM answers from the wrong text | Retrieval |
| `generate.py` | Sends the question plus 5 chunks to Groq with a fixed grounded prompt | Produces the answer, with citations and refusals | No answer, or ungrounded answers | Generation |
| `judge.py` | Asks Mistral to grade correctness and faithfulness | Grading 420 answers by hand is not feasible | No scalable quality measure | Evaluation |
| `textmatch.py` | Normalises text and fuzzy-matches the supporting sentence | PDFs change whitespace and hyphens; exact matching gives false failures | Attribution blames the wrong stage | Evaluation |
| `evaluate.py` | Computes metrics and runs the 4-check failure attribution | Turns raw logs into findings | Numbers with no diagnosis | Evaluation |
| `cache.py` | Saves and reloads expensive intermediate results | Laptop protection and resumable runs | Re-embedding every run (the v0 slowdown) | — |
| `run_benchmark.py` | CLI that runs stages for a config × doc | One reproducible entry point | Ad-hoc scripts, irreproducible results | — |

## 3. Data artifacts and cache keys

Every expensive output is saved, so the next stage reuses it.

| Artifact | Path | Key | Rebuilt when |
| --- | --- | --- | --- |
| Parsed pages | `cache/parsed/{doc_id}__{parsing}.json` | doc + parsing mode | Parsing mode changes |
| Chunks | `cache/chunks/{doc_id}__{chunk_sig}.jsonl` | doc + parsing + chunking + headers | Any of those change |
| Vector index | `cache/chroma/` collection `{doc_id}__{chunk_sig}__{embed_model}` | chunks + embedding model | Chunks or model change |
| BM25 index | `cache/bm25/{doc_id}__{chunk_sig}.pkl` | chunks | Chunks change |
| Retrieval results | `results/runs/{config_id}__{doc_id}__retrieval.jsonl` | config + doc | Config changes |
| Answers | `results/runs/{config_id}__{doc_id}__answers.jsonl` | config + doc + qid | Never (resume skips done qids) |
| Judgements | `results/runs/{config_id}__{doc_id}__judged.jsonl` | config + doc + qid | Never (resume skips done qids) |
| Aggregate | `results/results.json` | all runs | Every `--stage aggregate` |

`chunk_sig` is a short hash of the parsing and chunking settings. Configs that share settings share the cache. For example, C4–C7 reuse the same chunks.

## 4. Run modes (stages)

```
python -m src.run_benchmark --config C1 --doc fund_doc --stage retrieve --limit 3
```

| `--stage` | Does | LLM calls | Use it to |
| --- | --- | --- | --- |
| `ingest` | Parse + chunk + index | 0 | Check parsing and chunk counts |
| `retrieve` | Retrieval + hit@5 / MRR + attribution checks 1–3 | 0 | Debug cheaply; compare configs for free |
| `generate` | Answers via Groq | 1 per question | Produce answers (paced) |
| `judge` | Grades via Mistral | 1 per answer | Score answers (paced) |
| `aggregate` | Builds `results.json` | 0 | Feed the dashboard |
| `all` | Everything in order | — | Final run only |

Flags: `--config C1..C7|all`, `--doc annual_report|fund_doc|ghg_scope3|all`, `--limit N`, `--force` (ignore cache).

## 5. Life of one question (C6 example)

1. Load question `FD-07` from the golden set.
2. **Retrieve:** BM25 top-20 and dense top-20, merged with RRF, then the cross-encoder re-ranks to top-5.
3. **Checks 1–3** (free): is the supporting text in the parsed text? In any chunk? In the top-5?
4. **Generate:** prompt with 5 labelled chunks → Groq → answer + latency + tokens.
5. **Judge:** question + gold answer + context + answer → Mistral → `{correctness, faithful, reason}`.
6. **Attribute:** if wrong, assign the first failing stage (ingestion → indexing → retrieval → generation).
7. Append one JSON line per stage file. Never overwrite.

## 6. Why the laptop won't freeze this time

| v0 risk | v1 design choice |
| --- | --- |
| Running an LLM locally (Ollama) uses most of the RAM | All LLM calls go to Groq and Mistral; only small models run locally |
| Re-embedding on every run | Disk cache keyed by settings |
| Testing everything at once | `--limit`, one doc and one config at a time, retrieval-only stage |
| Loading models per question | Models loaded once per process |
| Big grid of configs | 7-step ladder, shared caches |

## 7. Online parts

- **Dashboard (Next.js on Vercel):** static site; reads `results/results.json` copied into `dashboard/public/`. No server, no database, no API keys.
- **Demo chat (Gradio on Hugging Face Spaces):** loads the winning config's prebuilt index (committed to the Space), calls Groq at query time. The Groq key is stored as a Space secret. It uses the same generator prompt, citations and refusal rule.

## 8. Security and hygiene

- Keys live in `.env` locally and in platform secrets online; `.env` is git-ignored.
- Only public PDFs are committed. No employer documents, ever.
- Retrieved text is passed to the LLM as data, inside clearly marked context blocks, and the prompt tells it to ignore instructions inside the context.
