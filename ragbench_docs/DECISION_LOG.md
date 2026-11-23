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
| H3 | Retrieval | Hybrid search helps most on the fund document | C4 → C5, fund doc | confirmed (retrieval) | On fund_doc, hit@5 surged from 0.111 to 0.278 (+16.7 pts) and retrieval failures collapsed to 1. |
| H4 | Retrieval | Re-ranking helps most on the guidance doc but adds the most latency | C5 → C6, accuracy vs p95 | confirmed (retrieval) | Re-ranking lifted overall MRR to 0.375 (fund MRR +0.165, AR MRR +0.056), while adding ~950ms median latency (275ms to 1218ms). |
| H5 | Indexing | Context headers still help after re-ranking, where chunks look alike | C6 → C7, fund + guidance | | |
| H6 | All | Most baseline failures happen before generation | Attribution on C1 | confirmed | 22 of 23 C1 failures (95.7%) occurred at indexing (6) or retrieval (16); only 1 occurred at generation. |
| H7 | All | No single config wins on all three documents | Winner per doc | | |

## 3. Config-by-config notes (Step 8)

| Config | What I expected | What happened (hit@5, correctness, p95) | Surprise? |
| --- | --- | --- | --- |
| C1 | Baseline: simple dense retrieval with basic parsing and fixed chunking | Overall correctness 64.2% (AR: 72.5%, FD: 32.5%, GH: 87.5%). Hit@5: 40.7% (AR: 55.6%, FD: 5.6%, GH: 61.1%). P95 latency 1.0s (AR) to 7.7s (GH). Failures: 0 ingestion, 6 indexing, 16 retrieval, 1 generation. | Dense retrieval failed catastrophically on the fund document (hit@5 of 5.6% and 12 retrieval failures), while narrative guidance (GHG Scope 3) scored 87.5% even with basic dense search. |
| C2 | Layout-aware parsing alone (dense search) | Mean hit@5: 0.315 (AR: 0.444, FD: 0.056, GH: 0.444), mean MRR 0.241, median latency 258ms. | PyMuPDF4LLM markdown table syntax (<br>, |) changed token flows; dense search alone didn't overcome table representation. |
| C3 | Structure-aware chunking (split by headings) | Mean hit@5: 0.315 (AR: 0.389, FD: 0.056, GH: 0.500), mean MRR 0.220, median latency 256ms. | Cut indexing failures from 6 down to 4 across docs. |
| C4 | Stronger embedding model (BGE-small) | Mean hit@5: 0.333 (AR: 0.333, FD: 0.111, GH: 0.556), mean MRR 0.260, median latency 272ms. | Improved hit@5 on both fund_doc and ghg_scope3 over C3. |
| C5 | Hybrid search (Dense + BM25 with RRF) | Mean hit@5: 0.426 (AR: 0.444, FD: 0.278, GH: 0.556), mean MRR 0.294, median latency 275ms. | Massive breakthrough on fund_doc (+16.7 pts hit@5); keyword matching found specific fund schemes where dense vectors confused them. |
| C6 | Cross-encoder re-ranking (top 20 to 5) | Mean hit@5: 0.444 (AR: 0.500, FD: 0.278, GH: 0.556), mean MRR 0.375, median latency 1218ms. | Best overall retrieval precision (MRR 0.375, total retrieval failures down to 6), with a ~950ms latency cost. |
| C7 | Hybrid + re-ranking + contextual headers | Mean hit@5: 0.426 (AR: 0.500, FD: 0.278, GH: 0.500), mean MRR 0.371, median latency 1183ms. | Contextual headers dropped indexing failures to 2 (lowest of all configs). |

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
