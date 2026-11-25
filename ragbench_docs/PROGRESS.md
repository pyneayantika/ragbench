# PROGRESS.md — Where the build stands

> **For the coding agent:** read this first in every new session, and update it at the end of every step. It lets work continue across sessions and tools (Cursor → Antigravity → Claude Code) without losing context.
> **For the human:** a quick view of what's done, what's next, and what's blocked.

## Current status

- **Current step:** Step 10 (Analysis)
- **Last updated:** 2026-11-25, Antigravity
- **Blocked on:** nothing

## Step tracker

| Step | Name | Status | Done-when check passed | Commit | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Archive v0, PDFs ready | ✅ Done | 3 PDFs in `data/raw/` (152, 153, 140 pages) | — | Infosys = original pages 30–182 |
| G | Golden set (60 questions) + G-check | ✅ Done | Validated and frozen 2026-11-22. Structure passed. Checker did not change the file. | 404e092 | Human kept AR-20 and GH-20 unanswerable. 45 fuzzy flags are layout wording or a second passage on the next page. |
| 1 | Setup + API check | ✅ Done | venv, 7 configs, both Groq models replied OK, `.env` git-ignored | — | Generator `openai/gpt-oss-120b`. Judge `qwen/qwen3.8-27b`. |
| 2 | Ingest | ✅ Done | all 3 docs parsed in both basic and layout modes, cached | — | PyMuPDF and pymupdf4llm |
| 3 | Chunk | ✅ Done | fixed and structure chunking implemented, <256 tokens | — | Tokenizer-aware, heading fallback |
| 4 | Index + dense retrieval | ✅ Done | dense and BM25 index built, cached | — | ChromaDB and rank_bm25 |
| 5 | Text match + retrieval metrics | ✅ Done | rapidfuzz partial_ratio at threshold 90, C1 retrieval done | — | Checks 1–3 attribution |
| 6 | Generation | ✅ Done | Groq openai/gpt-oss-120b, 60 C1 answers generated with citation normalisation | 1c02a9e | Fullwidth citation brackets normalized |
| 7 | Judge + attribution + aggregate | ✅ Done | Groq qwen/qwen3.8-27b judge, 0 errors, results.json validated against B8 | d96ce6b | H6 confirmed: 22/23 failures before generation |
| 8A | C2–C7 retrieval-only comparison | ✅ Done | 21 retrieval runs complete; comparison table printed; H3 confirmed (+16.7 pts hit@5 on fund_doc with hybrid); H4 confirmed (MRR 0.375 with rerank) | cb0dd4a | Zero LLM calls made |
| 8B | C2–C7 generate + judge + aggregate | ✅ Done | 7 configs × 3 docs (420 answers, 420 judged); results.json validated against B8; 0 missing citations; 1 judge_error (C4 AR-14) | 053d1c0 | C7 wins overall mean (70.8%); C6 wins annual_report (80.0%) |
| 9 | Hand-score + judge agreement | ✅ Done | 20 blind hand scores joined; 18/20 (90.0%) agreement recorded in results.json; 2 disagreements listed | [next commit] | Seed 42, only 0.5-pt partial-credit diffs |
| 10 | Analysis | ⬜ Not started | | | |
| 11 | Dashboard | ⬜ Not started | | | |
| 12 | Demo chat | ⬜ Not started | | | |
| 12B | Pre-launch guardrail check | ⬜ Not started | | | |
| 13 | Story (case study, Loom, post) | ⬜ Not started | | | |

Status values: ⬜ Not started · 🟡 In progress · ✅ Done · 🔴 Blocked

## Session log (newest first)

| Date | Tool | What was done | What's next | Open issues |
| --- | --- | --- | --- | --- |
| 2026-11-25 | Antigravity | Step 9 completed: blind hand review of 20 sampled answers (seed 42) yielded 18/20 (90.0%) human-judge agreement, recorded in results.json. | Step 10: Analysis (hypotheses H1-H7, failure examples, winners) | None |
| 2026-11-25 | Antigravity | Step 8B completed: generated and judged all remaining configs C2–C7 across all 3 docs (420 total answers, 1 judge_error on C4 AR-14). Validated complete 21-row results.json. | Step 9: Human hand-scores 20 answers in results/hand_scores.csv, then compute judge agreement | None |
| 2026-11-23 | Antigravity | Step 8A completed: implemented BM25, hybrid RRF, cross-encoder re-ranking. Ran C1–C7 retrieval across all 3 docs (420 queries, zero LLM calls). Confirmed H3 (hybrid search on fund_doc) and H4 (re-ranking MRR boost). | Step 8B: generate, judge, and aggregate C2–C7 | None |
| 2026-11-23 | Antigravity | Step 7 completed: ran full C1 judge (qwen/qwen3.8-27b) across all 3 docs with 0 judge errors, full stage attribution, generated and validated results.json against B8, confirmed H6 (22/23 failures before generation). | Step 8A: hybrid search, re-ranking, headers, and C2-C7 retrieval-only comparison | None |
| 2026-11-22 | Cursor | Golden set validated and frozen. Page 150 of the annual report is BRSR water-stress guidance, not revenue guidance, so AR-20 stays unanswerable. GH-20's word alarm is weak and stays unanswerable. | Step 2 ingest is already built and waiting to be marked done | Judge is Qwen, not Mistral |
| 2026-11-22 | Cursor | Step 1: setup, configs, and Say OK on both Groq models | Step 2 ingest is already built and waiting for approval | Judge is Qwen, not Mistral |

## Known issues and workarounds

| Issue | Workaround | Permanent fix? |
| --- | --- | --- |
| Mistral free plan allows 0 requests/minute (code 1300). Phone verification is not available. | Judge switched to Groq `qwen/qwen3.8-27b`, a different family from the generator. Both IDs are in `src/settings.py`. | Resolved 2026-11-22. |
