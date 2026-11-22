# AGENTS.md — Rules for any AI coding agent working on RAGBench

> Cursor and Antigravity read this file from the repo root. For Claude Code, copy it to `CLAUDE.md`.
> If anything here conflicts with a prompt, **this file wins** unless the human explicitly overrides it.

## 1. What this project is

RAGBench benchmarks 7 RAG configurations on 3 public PDFs using a 60-question hand-written golden set. It measures accuracy, latency and cost, and traces every wrong answer to the stage that broke: ingestion, indexing, retrieval or generation.

**Source of truth, in order:**

0. `PROGRESS.md`: **read first in every session**; it says which step you are on. Update it at the end of every step.
1. `BRIEF.md`: product brief (Part A) and build spec (Part B)
2. `ARCHITECTURE.md`: components, data flow, caching, run modes
3. `BUILD_PLAN.md`: the step you are on and its "done when" check
4. `GUARDRAILS.md`: safety, integrity and cost rules (binding, like this file)
5. `GOLDEN_SET_GUIDE.md`: the format of `data/golden_set.csv`
6. `PROMPTS.md`: the step prompts the human pastes; follow their report format exactly

## 2. Who you are working with

The owner, Ayantika, is a product manager, not a software engineer. She directs the build and must be able to explain every design decision in an interview.

- **Before each step:** explain in plain English what you will build, and why, in 3–5 lines.
- **After each step:** say what was built, how to verify it, and what could break.
- **Every module** starts with a comment block: *what it does · why it exists · what breaks without it · which failure stage it relates to*.
- Prefer simple, readable code over clever code. No unexplained abstractions.
- Never say "done" without showing the verification output.

## 3. Non-negotiable rules

1. **Free tools only.** Remote APIs: Groq (generator) and Mistral (judge). No OpenAI, Cohere, or any paid API.
2. **No local LLMs.** Do not use Ollama or run any LLM on the laptop. Only small embedding and re-ranker models run locally.
3. **Never change the constants:** generator model, generator prompt, judge model, judge prompt, temperature 0, `final_k = 5`, and the golden set. Only fields in `configs/*.yaml` differ between configs.
4. **Config-driven.** No config values hard-coded in Python. One YAML per config.
5. **Never fabricate.** No synthetic questions, mock results or placeholder numbers in `results/`. If something can't run, stop and say so.
6. **Never silently swallow errors.** Log them, and fail loudly on anything that would corrupt results.
7. **Do not add dependencies** beyond `requirements.txt` without asking.
8. **Do not modify `data/golden_set.csv`.** It is written by the human only.
9. **One step at a time.** Follow `BUILD_PLAN.md`. Do not start the next step until the current "done when" check passes and the human confirms.

## 4. Laptop protection rules (the v0 attempt froze the machine)

1. Load each model **once per process**, never inside a per-question loop.
2. Embed in batches (`batch_size=32`), with a `tqdm` progress bar.
3. **Cache everything** to disk (parsed text, chunks, embeddings, retrieval results) and reuse it. Re-running must skip finished work.
4. Process **one document and one config at a time** by default.
5. Every command supports `--limit N`. Always test with `--limit 3` before a full run.
6. Retrieval-only runs (`--stage retrieve`) make **no LLM calls**. Use them to debug.
7. The cross-encoder only re-ranks the `candidate_k` (20) chunks, never the whole collection.
8. Throttle APIs: Groq ~6 calls/minute; Mistral ≤ 1 call/second. On HTTP 429, back off exponentially and resume.
9. Write results row by row (JSONL) so a crash never loses completed work.

## 5. Code conventions

- Python 3.11, type hints, functions under ~40 lines, `logging` (not `print`) in `src/`.
- All paths relative to the repo root, using `pathlib`.
- Secrets only in `.env` (git-ignored). Never print or log API keys.
- CLI entry point: `python -m src.run_benchmark --config C1 --doc fund_doc --stage retrieve --limit 3`.
- Commit after each completed step: `git commit -m "Step N: <what>"`.
- After each step, update `PROGRESS.md` (status, check passed, commit, notes, session log).

## 6. When stuck

If something fails twice in the same way, **stop**, explain the error in plain English, list 2–3 likely causes, and ask before trying a third approach.
