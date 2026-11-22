# PROGRESS.md — Where the build stands

> **For the coding agent:** read this first in every new session, and update it at the end of every step. It lets work continue across sessions and tools (Cursor → Antigravity → Claude Code) without losing context.
> **For the human:** a quick view of what's done, what's next, and what's blocked.

## Current status

- **Current step:** Step 2 (ingest)
- **Last updated:** 2026-11-22, Cursor
- **Blocked on:** nothing

## Step tracker

| Step | Name | Status | Done-when check passed | Commit | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Archive v0, PDFs ready | ✅ Done | 3 PDFs in `data/raw/` (152, 153, 140 pages) | — | Infosys = original pages 30–182 |
| G | Golden set (60 questions) + G-check | ✅ Done | Validated and frozen 2026-11-22. Structure passed. Checker did not change the file. | — | Human kept AR-20 and GH-20 unanswerable. 45 fuzzy flags are layout wording or a second passage on the next page. |
| 1 | Setup + API check | ✅ Done | venv, 7 configs, both Groq models replied OK, `.env` git-ignored | — | Generator `openai/gpt-oss-120b`. Judge `qwen/qwen3.8-27b`. |
| 2 | Ingest | ⬜ Not started | | | |
| 3 | Chunk | ⬜ Not started | | | |
| 4 | Index + dense retrieval | ⬜ Not started | | | Needs golden set |
| 5 | Text match + retrieval metrics | ⬜ Not started | | | |
| 6 | Generation | ⬜ Not started | | | |
| 7 | Judge + attribution + aggregate | ⬜ Not started | | | |
| 8A | C2–C7 retrieval-only comparison | ⬜ Not started | | | |
| 8B | C2–C7 generate + judge + aggregate | ⬜ Not started | | | |
| 9 | Hand-score + judge agreement | ⬜ Not started | | | |
| 10 | Analysis | ⬜ Not started | | | |
| 11 | Dashboard | ⬜ Not started | | | |
| 12 | Demo chat | ⬜ Not started | | | |
| 12B | Pre-launch guardrail check | ⬜ Not started | | | |
| 13 | Story (case study, Loom, post) | ⬜ Not started | | | |

Status values: ⬜ Not started · 🟡 In progress · ✅ Done · 🔴 Blocked

## Session log (newest first)

| Date | Tool | What was done | What's next | Open issues |
| --- | --- | --- | --- | --- | --- |
| 2026-11-22 | Cursor | Golden set validated and frozen. Page 150 of the annual report is BRSR water-stress guidance, not revenue guidance, so AR-20 stays unanswerable. GH-20's word alarm is weak and stays unanswerable. | Step 2 ingest is already built and waiting to be marked done | Judge is Qwen, not Mistral |
| 2026-11-22 | Cursor | Step 1: setup, configs, and Say OK on both Groq models | Step 2 ingest is already built and waiting for approval | Judge is Qwen, not Mistral |

## Known issues and workarounds

| Issue | Workaround | Permanent fix? |
| --- | --- | --- |
| Mistral free plan allows 0 requests/minute (code 1300). Phone verification is not available. | Judge switched to Groq `qwen/qwen3.8-27b`, a different family from the generator. Both IDs are in `src/settings.py`. | Resolved 2026-11-22. |
