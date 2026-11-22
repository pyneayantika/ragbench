# DECISION_LOG.md — Decisions, hypotheses and findings

> Fill this **as you build**, not at the end. This file becomes the core of the case study. Write in your own words.

## 1. Decisions

| # | Date | Decision | Options considered | What I chose | What I gave up | What happened | Would I choose it again? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | | Restart vs continue v0 | Continue the half-built v0 vs start fresh with v0 archived | Start fresh, archive v0 | Some reusable code | | |
| D2 | | Config design | Full grid of 128 vs a one-change ladder of 7 | Ladder of 7 | Interaction effects between upgrades | | |
| D3 | | What to measure | Accuracy only vs accuracy + stage-level failure attribution | Attribution on every wrong answer | Some extra analysis time | | |
| D4 | | Test data | Synthetic questions vs hand-written golden set | Hand-written, 60 | Speed and volume | | |
| D4b | | Corpus size | ~40-page excerpts vs full documents (~150-page cap) | Full documents | Faster setup, easier unanswerable checks | | |
| D5 | | Chunk size | 512 vs 256 tokens | 256 (MiniLM's input limit) | Fewer, larger chunks | | |
| D6 | | Indexing experiment | Contextual headers vs parent-child | Contextual headers (C7) | Parent-child's gain on multi-part questions | | |
| D7 | | Vector index type | Test flat vs HNSW vs IVF, or keep default | Keep default | Nothing at this corpus size | | |
| D8 | | Judge | Hand-score all vs LLM judge | LLM judge, checked on 20 by hand | Some judge error | | |
| D9 | | Judge model | Same family as generator vs different | Mistral (different family) | One more provider | | |
| D10 | 2026-11-21 | Generator | Best model vs fixed free model | GPT-OSS 120B on Groq (`openai/gpt-oss-120b`), temperature 0, low reasoning effort. Llama 3.3 70B was planned but is not available on this account | Peak answer quality; reasoning models use extra tokens | | |
| D10b | 2026-11-21 | Judge model ID | mistral-small vs mistral-medium | `mistral-medium-latest` (no "large" model on the free account) | Some grading quality vs a large model | | |
| D10c | 2026-11-22 | Judge model | Keep Mistral vs move the judge to Groq | Groq `qwen/qwen3.8-27b` | A separate judge provider | Judge switched from Mistral to Groq Qwen because the Mistral free plan allowed 0 requests/minute. | |
| D11 | | Hosting | All on Vercel vs local pipeline + static outputs | Local pipeline, static dashboard, HF Spaces demo | A live re-runnable benchmark | | |
| D12 | | Fuzzy-match threshold | Exact match vs fuzzy at threshold N | _[fill after Step 5]_ | | | |
| D13 | 2026-11-22 | Citation brackets | Change the generator prompt vs clean the brackets in code | Clean fullwidth brackets in code. The prompt stays exactly as written. | A stored answer that matches the model's raw punctuation | GPT-OSS returns fullwidth citation brackets; normalised in code, prompt unchanged. | |

## 2. Hypotheses (write before running; fill after Step 10)

| # | Stage | Hypothesis | Tested by | Result (confirmed / rejected / inconclusive) | One line why |
| --- | --- | --- | --- | --- | --- |
| H1 | Ingestion | Layout-aware parsing gives the biggest single gain on the annual report | C1 → C2, annual report | | |
| H2 | Indexing | Splitting by headings reduces answers cut across chunks, most on the guidance doc | C2 → C3, check-2 failures | | |
| H3 | Retrieval | Hybrid search helps most on the fund document | C4 → C5, fund doc | | |
| H4 | Retrieval | Re-ranking helps most on the guidance doc but adds the most latency | C5 → C6, accuracy vs p95 | | |
| H5 | Indexing | Context headers still help after re-ranking, where chunks look alike | C6 → C7, fund + guidance | | |
| H6 | All | Most baseline failures happen before generation | Attribution on C1 | | |
| H7 | All | No single config wins on all three documents | Winner per doc | | |

## 3. Config-by-config notes (Step 8)

| Config | What I expected | What happened (hit@5, correctness, p95) | Surprise? |
| --- | --- | --- | --- |
| C1 | | Test run (FD-01 to FD-03): all three failed at retrieval; summary/hub pages (p.6, p.107, p.140) dominate the top 5 for fund questions. FD-03 answered correctly from an alternative page (p.123): known limitation — golden set lists one supporting passage, so hit@5 can undercount. | |
| C2 | | | |
| C3 | | | |
| C4 | | | |
| C5 | | | |
| C6 | | | |
| C7 | | | |

## 4. Failure examples (Step 10)

### Example 1
- **Question / config / document:**
- **Stage that broke:**
- **What was retrieved vs what was needed:**
- **Diagnosis (my words):**
- **Fix that would address it:**

### Example 2
- **Question / config / document:**
- **Stage that broke:**
- **What was retrieved vs what was needed:**
- **Diagnosis (my words):**
- **Fix that would address it:**

## 5. Caveats to state openly

- 20 questions per document: differences under about 10 points are not conclusive.
- One generator and one judge model; results may differ with other models.
- Documents capped at ~150 pages; questions come from sections I read closely.
