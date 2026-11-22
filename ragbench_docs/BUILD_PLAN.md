# BUILD_PLAN.md — Step-by-step build with prompts and checks

> One step at a time. Paste the prompt into Cursor (or Antigravity / Claude Code), check the result against **Done when**, read **Understand this**, then commit and move on.
> Rule: never start a step until the previous one passes its check.
> **Use `PROMPTS.md` for the actual prompts to paste:** each one includes the guardrail header and the report format. The short prompts below are summaries.
> At the end of every step, the agent updates `PROGRESS.md`. Before going public (Steps 11–12), run the checklist in `GUARDRAILS.md` §7.

## Overview

| Step | What | Hours (of 48) | LLM calls |
| --- | --- | --- | --- |
| 0 | Archive v0, post-mortem, pick PDFs | 0–2 | 0 |
| G | Write the golden set (human only) | 2–10 | 0 |
| 1 | Setup and API check | 10–11 | 2 |
| 2 | Ingest (basic + layout) | 11–12 | 0 |
| 3 | Chunk (fixed, structure, headers) | 12–13 | 0 |
| 4 | Index + dense retrieval | 13–15 | 0 |
| 5 | Text matching + retrieval metrics + checks 1–3 | 15–17 | 0 |
| 6 | Generation (Groq), resumable | 17–19 | ~60 |
| 7 | Judge (Mistral) + attribution + aggregate | 19–22 | ~60 |
| 8 | Hybrid, re-rank, headers; run C2–C7 | 22–32 | ~720 |
| 9 | Hand-score 20 answers; judge agreement | 32–34 | 0 |
| 10 | Analysis: hypotheses, failure examples, winners | 34–38 | 0 |
| 11 | Dashboard (Vercel) | 38–42 | 0 |
| 12 | Demo chat (HF Spaces) | 42–44 | few |
| 13 | Case study, Loom, LinkedIn | 44–48 | 0 |

---

## Step 0 — Archive v0 and start clean (no AI agent needed)

1. **Don't delete the old folder.** Rename it to `ragbench_v0_archive`.
2. Free disk space inside it by deleting only the heavy, re-creatable folders: `venv/`, `.venv/`, `node_modules/`, `__pycache__/`, and any `chroma*` or model cache folders. Keep the code, notes and results.
3. Spend 30 minutes filling `POSTMORTEM_V0.md`. This becomes the opening of your case study.
4. Create a fresh folder `ragbench/`, `git init`, and copy in all the docs: `BRIEF.md`, `AGENTS.md`, `ARCHITECTURE.md`, `BUILD_PLAN.md`, `GUARDRAILS.md`, `PROGRESS.md`, `GOLDEN_SET_GUIDE.md`, `DECISION_LOG.md`, `POSTMORTEM_V0.md`, `README.md`. Keep the `.cursor/rules/ragbench.mdc` file (Cursor's always-on rules). `CLAUDE.md` is a copy of `AGENTS.md` for Claude Code; if you edit one, update the other.
5. Download the 3 public PDFs (up to ~150 pages each; see `GOLDEN_SET_GUIDE.md` §2). Save them as `data/raw/annual_report.pdf`, `data/raw/fund_doc.pdf` and `data/raw/ghg_scope3.pdf`.

**Done when:** a clean `ragbench/` folder with the docs and 3 trimmed PDFs, and a filled post-mortem.

---

## Step G — Golden set (you, not the AI)

Follow `GOLDEN_SET_GUIDE.md`. Write all 60 questions **before Step 4**.

**Done when:** `data/golden_set.csv` has 60 rows, passes the checklist in the guide, and has been reviewed (send the first 10 to Claude for review).

---

## Step 1 — Setup and API check

```
Read AGENTS.md, BRIEF.md and ARCHITECTURE.md fully. Then do Step 1 of BUILD_PLAN.md only:
1. Create a Python 3.11 virtual environment.
2. Install PyTorch CPU-only first, then the packages in BRIEF.md B11.
3. Create the folder structure from BRIEF.md B2 plus cache/ (ARCHITECTURE.md §3), with the
   comment block at the top of each module (AGENTS.md §2).
4. Create .env.example (GROQ_API_KEY, MISTRAL_API_KEY) and a .gitignore covering .env, venv,
   cache/, __pycache__.
5. Create configs/c1.yaml to c7.yaml matching the ladder in BRIEF.md Part A and format B4.
6. Write scripts/check_apis.py that sends "Say OK" to Groq (openai/gpt-oss-120b) and Mistral
   (the judge model) once each and prints the reply, model name and token usage.
Explain each command in one line before running it. Stop after this step and show the output.
```

**Done when:** both APIs reply "OK", and `configs/` has 7 YAMLs whose values match the ladder table.
**Understand this:** why configs live in YAML (one place to change, reproducible, comparable).

---

## Step 2 — Ingest

```
Do Step 2 of BUILD_PLAN.md: implement src/ingest.py with parsing modes "basic" (PyMuPDF
page.get_text) and "layout" (pymupdf4llm.to_markdown with page_chunks=True). Output a list of
{doc_id, page, text}, cached at cache/parsed/{doc_id}__{parsing}.json. Add the "ingest" stage
to run_benchmark.py. Then write scripts/compare_parsing.py that prints page N of a document in
both modes side by side. Run it on a two-column page of the annual report and a table page of
the fund document.
```

**Done when:** all 3 docs parsed in both modes and cached, and you have *looked* at one two-column page and one table page in both modes.
**Understand this:** this comparison is your H1 evidence. Screenshot it for the case study.

---

## Step 3 — Chunk

```
Do Step 3: implement src/chunk.py. Strategies "fixed" (sliding window, max_tokens, overlap)
and "structure" (split on markdown headings, then cap at max_tokens on paragraph boundaries;
falls back to paragraphs when there are no headings). Count tokens with the tokenizer of the
config's embedding model. If contextual_headers is true, store embed_text =
"Document: {doc_name} | Section: {heading}\n{text}" and keep text unchanged.
Each chunk: {chunk_id, doc_id, page_start, page_end, section_heading, text, embed_text}.
Cache by chunk_sig (ARCHITECTURE.md §3). Print chunk counts and the max token length per
doc for C1, C3 and C7.
```

**Done when:** no chunk exceeds 256 tokens, and the counts look sensible (up to a few thousand chunks in total across the 3 documents).
**Understand this:** why 256 tokens (MiniLM's input limit), and why headers are only added to `embed_text`.

---

## Step 4 — Index and dense retrieval

```
Do Step 4: implement src/index.py (sentence-transformers embeddings in batches of 32 with a
progress bar, stored in a persistent ChromaDB collection named per ARCHITECTURE.md §3; plus a
BM25 index with rank_bm25, pickled) and the dense mode of src/retrieve.py (top candidate_k by
cosine similarity, then keep final_k). Load each model once per process. For C1 on fund_doc,
print the top-5 chunks (page + first 120 characters) for the first 5 golden questions.
```

**Done when:** a second run is near-instant (cache hit), and the printed chunks look relevant for at least some questions.
**Understand this:** embeddings vs keyword search, and why the index is rebuilt only when the chunks or the model change.

---

## Step 5 — Text matching, retrieval metrics, checks 1–3

```
Do Step 5: implement src/textmatch.py (normalise: lowercase, collapse whitespace, remove soft
hyphens and line-break hyphens; fuzzy_in(needle, haystack) using rapidfuzz partial_ratio >=
threshold, default 90). In src/evaluate.py implement hit@5, MRR, and attribution checks 1–3
(BRIEF.md B7). For "multi" questions split supporting_text on " ||| " and require all parts.
Add the "retrieve" stage writing results/runs/{config}__{doc}__retrieval.jsonl. Run C1 on all
3 docs. Print hit@5, MRR and counts of ingestion / indexing / retrieval failures per doc.
Also print 3 examples where fuzzy matching was borderline (score 80–95) so I can tune the threshold.
```

**Done when:** C1 retrieval metrics for all 60 questions, zero LLM calls, and a threshold confirmed by looking at the borderline examples. Write the threshold in `DECISION_LOG.md`.
**Understand this:** you can already compare configs on retrieval for free. Most of the insight comes before any LLM call.

---

## Step 6 — Generation

```
Do Step 6: implement src/generate.py using the exact generator prompt in BRIEF.md B6.
Label each chunk "[{doc_id} p.{page}]". Use temperature 0. Pace calls to ~6/minute; on 429,
back off exponentially. Log latency_ms, prompt_tokens, completion_tokens, and refused (answer
starts with "Not found in the documents"). Append to answers.jsonl and skip qids already done.
Run C1 on fund_doc with --limit 3, show the 3 answers, then run the full C1 for all docs.
```

**Done when:** 60 C1 answers saved; stopping and re-running skips completed questions.
**Understand this:** why temperature 0, and why citations and refusals are in the prompt.

---

## Step 7 — Judge, attribution, aggregate

```
Do Step 7: implement src/judge.py with the exact judge prompt in BRIEF.md B6, calling Mistral
(<= 1 call/second, retry on 429), parsing JSON strictly (retry once if invalid, then mark
"judge_error"). Skip "unanswerable" questions (score refusal by phrase). Implement full
attribution (BRIEF.md B7) and the "aggregate" stage producing results/results.json in the
shape of B8. Run on C1 and print the per-doc summary and failures_by_stage.
```

**Done when:** a complete `results.json` for C1. Write your first impression in `DECISION_LOG.md`, before you see any other config.
**Understand this:** H6 (most failures happen before generation) can already be checked on C1.

---

## Step 8 — Remaining configs

```
Do Step 8: add hybrid retrieval (BM25 + dense merged by RRF, rrf_k from config), cross-encoder
re-ranking of candidate_k down to final_k, and confirm contextual headers flow from chunk.py.
Then, for C2 to C7 in order: run --stage retrieve for all docs and print a comparison table of
hit@5 and MRR vs the previous config. Only after I confirm, run generate, judge and aggregate.
```

**Done when:** `results.json` holds 7 configs × 3 docs, and you've checked each upgrade's retrieval change before paying for generation.
**Understand this:** the ladder. Write one line per config in the decision log: expected vs actual.

---

## Step 9 — Hand-score and judge agreement

1. Pick 20 answers: about 7 per document, a mix of configs and question types, including at least 4 the judge marked wrong.
2. Score each yourself (0 / 0.5 / 1) in `results/hand_scores.csv` (`qid, config_id, my_score, note`) **before** looking at the judge's score.

```
Do Step 9: read results/hand_scores.csv, compare with the judge's correctness for the same
(qid, config_id), and add judge_agreement {n, agreed} to results.json (agreed = same score).
List the disagreements.
```

**Done when:** agreement reported, disagreements reviewed, and a note in the decision log.

---

## Step 10 — Analysis (you, with AI help for tables only)

- Fill the hypotheses table (H1–H7) in `DECISION_LOG.md`: confirmed, rejected or inconclusive, plus one line why.
- Pick 2 failure examples (ideally one ingestion and one retrieval) and write the diagnosis yourself.
- Choose the winner per document, weighing accuracy against latency.
- Note the sample-size caveat: with 20 questions per doc, differences under about 10 points are not conclusive.

---

## Step 11 — Dashboard

```
Do Step 11: create a Next.js app in dashboard/ that reads public/results.json and has the 4
pages in BRIEF.md B9. Static export, no server code, no API keys. Keep the design plain and
readable: the numbers are the product. Deploy to Vercel.
```

**Done when:** live URL; every number on the page traces to `results.json`.

---

## Step 12 — Demo chat

```
Do Step 12: create demo/app.py (Gradio) that runs the winning config's retrieval on a prebuilt
index and calls Groq with the same generator prompt. Show the answer, citations, and the
retrieved chunks in an expandable panel. Prepare it for Hugging Face Spaces (requirements.txt,
README with Space metadata, GROQ_API_KEY as a Space secret). Add a per-session limit of 20
questions to protect the free tier.
```

**Done when:** a live Space that cites pages and refuses an unanswerable question correctly.

---

## Step 13 — Tell the story

Case study (9-section template), a 90-second Loom (problem → ladder → one surprising finding → one failure → what's next), and a LinkedIn post (one finding, one failure, one chart).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Laptop freezes or fans max out | Model loaded per question, or embedding everything at once | Load once; batch 32; `--limit`; one doc at a time |
| Every run is slow | Cache not hit | Check the cache keys and paths; print "cache hit/miss" |
| hit@5 is near zero for everything | Text-match threshold too strict, or wrong page numbers in the golden set | Look at borderline matches; re-check page numbering (`GOLDEN_SET_GUIDE.md` §2) |
| Groq 429 errors | Token-per-minute limit | Slow to ~4 calls/minute; resume |
| Judge returns non-JSON | Model added text around the JSON | Strip to the first `{…}` block; retry once |
| All configs score the same | Configs not actually different | Print the resolved config and `chunk_sig` at the start of each run |
| Install fails on Python 3.13 | Library not yet compatible | Use Python 3.11 |
