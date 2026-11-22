# POSTMORTEM_V0.md — Why my first RAGBench attempt stalled

> 30 minutes, before writing any v1 code. Blameless and honest: the point is to learn, not to judge. This becomes the opening of the case study: *"My first attempt failed. Here's why, and what I changed."*
> Points marked _(verify)_ are what I remember of v0; check them against the archived folder.

## 1. What v0 was meant to do

- A full-grid experiment and playground: default config = 8 chunkers × 3 retrievers × 2 re-rank options × 4 query transforms = **192 configs**; a reduced v1 file had 36 _(audit: src/config.py, experiment_config*.yaml)_
- Stack: Groq (generation, and judge with llama-3.1-8b-instant), **Ollama locally** (nomic-embed-text embeddings; llama3.1:8b for contextual chunk summaries, HyDE and query rewrite), ChromaDB, FastAPI, Next.js dashboard
- Corpus: 11 mixed documents (GHG Scope 3, insurance and HR PDFs, plus synthetic handbook and clinical files); 20 + 10 evaluation queries in JSON

## 2. What actually happened

| Question | My answer |
| --- | --- |
| How far did it get? | |
| What worked? | |
| Where exactly did it stop? | |
| What were the symptoms? (slow tests, laptop freezing, errors) | |
| How long did one test run take? | |
| What data was it tested on? | Synthetic data; I discovered results were not from real documents _(verify)_ |

## 3. Likely root causes (tick and add evidence from the archived folder)

- [x] **Local LLMs via Ollama** for embeddings, contextual chunk summaries, HyDE and query rewrite, running alongside the re-ranker (audit: experiment_config.yaml L67–87).
- [x] **Sentence-by-sentence model calls** in the semantic chunker (~1 s per sentence in the log), with no disk cache for that step.
- [ ] **No caching:** partly. Parsing, chunking and Chroma were cached; contextual and semantic steps were not.
- [x] **Far too many configs:** 192 configs × 20 queries ≈ 3,840 runs, each with 1 generation + 3 judge calls.
- [x] **Synthetic or mixed test data:** 10 of 20 queries were on a synthetic handbook.
- [x] **No real golden set:** no page numbers or supporting sentences; no unanswerable questions.
- [x] **The judge never used the gold answer:** it scored plausibility, not correctness (generation_metrics.py).
- [x] **Loose retrieval check:** "relevant" meant 30% word overlap with the answer.
- [x] **No failure attribution by stage:** failures were shown, but not where they happened.
- [x] **No small test mode:** no `--limit` anywhere in the repo.
- [x] **Hard-coded dashboard numbers** (dashboard/app/page.tsx).
- [ ] **Building without understanding:** _(my own honest assessment)_
- [ ] Other: ______________________

## 4. What I'd tell myself before v0

_(3–5 sentences in my own words.)_

## 5. How v1 is designed differently

| v0 problem | v1 design choice | Where it's written |
| --- | --- | --- |
| Local LLM froze the laptop | All LLM calls go to Groq / Mistral; only small models run locally | `AGENTS.md` §4 |
| Re-embedding every run | Disk cache keyed by settings | `ARCHITECTURE.md` §3 |
| 36-config grid | 7-config one-change ladder | `BRIEF.md`, Pipeline design |
| Synthetic data | 60 hand-written questions on 3 real public PDFs | `GOLDEN_SET_GUIDE.md` |
| No way to test small | `--limit`, retrieval-only stage, one doc at a time | `ARCHITECTURE.md` §4 |
| AI decided, I followed | Every step explained before and after; I write the golden set and the analysis | `AGENTS.md` §2, `BUILD_PLAN.md` |
| Only measured "which config wins" | Failure attribution: which stage broke | `BRIEF.md`, Evaluation design |

## 6. Optional: let the agent gather facts (read-only)

Paste into Cursor, opened on the **archived** folder:

```
Read-only task, change nothing. Inspect this folder and list:
1) the configs or pipeline variants defined, 2) which modules exist and which look unfinished,
3) whether any LLM runs locally (e.g. Ollama), 4) whether parsed text, chunks or embeddings are
cached to disk, 5) what data the tests ran on, 6) any results files and what they contain.
Report facts only, with file paths. No recommendations.
```

Then write sections 2–4 yourself, in your own words.
