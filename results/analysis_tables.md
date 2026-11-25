# RAGBench Step 10 — Evidence Tables

> **Source files:** All aggregate metrics come from `results/results.json`. All per-question examples, snippets, answers, and failure stages come from `results/runs/{config}__{doc}__*.jsonl`, `cache/chunks/{doc}__{chunk_sig}.jsonl`, and `data/golden_set.csv`.
> **Rule:** Differences under 10 percentage points are flagged as `not conclusive (n=20 per doc)` per `GUARDRAILS.md` §5. No diagnoses or winner selections are made here.

---

## 1. Hypothesis Evidence (H1–H7)

### H1 — Ingestion: Layout-aware parsing gives the biggest single gain on the annual report
- **Comparison (`results/results.json`):** `C1 → C2` on `annual_report` (and other docs for context)

| Document | C1 Correctness | C2 Correctness | Δ Correctness | Flag | C1 Hit@5 | C2 Hit@5 | Δ Hit@5 | Flag |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :--- |
| `annual_report` | 72.5% | 65.0% | -7.5 pts | not conclusive (n=20 per doc) | 55.6% | 44.4% | -11.1 pts | ≥ 10 pts |
| `fund_doc` | 32.5% | 32.5% | +0.0 pts | not conclusive (n=20 per doc) | 5.6% | 5.6% | +0.0 pts | not conclusive (n=20 per doc) |
| `ghg_scope3` | 87.5% | 80.0% | -7.5 pts | not conclusive (n=20 per doc) | 61.1% | 44.4% | -16.7 pts | ≥ 10 pts |

### H2 — Indexing: Splitting by headings reduces answers cut across chunks, most on the guidance doc
- **Comparison (`results/results.json`):** `C2 → C3`, `failures_by_stage["indexing"]` (check-2 failures) and `correctness`

| Document | C2 Indexing Failures | C3 Indexing Failures | Δ Indexing Failures | C2 Correctness | C3 Correctness | Δ Correctness | Flag |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `annual_report` | 2 | 2 | 0 | 65.0% | 55.0% | -10.0 pts | 10.0 pts |
| `fund_doc` | 2 | 2 | 0 | 32.5% | 22.5% | -10.0 pts | 10.0 pts |
| `ghg_scope3` | 2 | 0 | -2 | 80.0% | 80.0% | +0.0 pts | not conclusive (n=20 per doc) |

### H3 — Retrieval: Hybrid search helps most on the fund document
- **Comparison (`results/results.json`):** `C4 → C5`, `fund_doc` (and other docs for context)

| Document | C4 Correctness | C5 Correctness | Δ Correctness | Flag | C4 Hit@5 | C5 Hit@5 | Δ Hit@5 | Flag |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :--- |
| `annual_report` | 57.9% | 72.5% | +14.6 pts | ≥ 10 pts | 33.3% | 44.4% | +11.1 pts | ≥ 10 pts |
| `fund_doc` | 37.5% | 47.5% | +10.0 pts | 10.0 pts | 11.1% | 27.8% | +16.7 pts | ≥ 10 pts |
| `ghg_scope3` | 77.5% | 85.0% | +7.5 pts | not conclusive (n=20 per doc) | 55.6% | 55.6% | +0.0 pts | not conclusive (n=20 per doc) |

### H4 — Retrieval: Re-ranking helps most on the guidance doc but adds the most latency
- **Comparison (`results/results.json`):** `C5 → C6`, `correctness` vs `latency_p95_ms` (and retrieval median latency from Step 8A `scripts/compare_retrieval.py`)

| Document | C5 Correctness | C6 Correctness | Δ Correctness | Flag | C5 p95 (ms) | C6 p95 (ms) | Δ p95 (ms) |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: |
| `annual_report` | 72.5% | 80.0% | +7.5 pts | not conclusive (n=20 per doc) | 1091 | 1842 | +751 |
| `fund_doc` | 47.5% | 42.5% | -5.0 pts | not conclusive (n=20 per doc) | 868 | 1089 | +221 |
| `ghg_scope3` | 85.0% | 87.5% | +2.5 pts | not conclusive (n=20 per doc) | 1668 | 740 | -928 |

*Note: From Step 8A retrieval-only timing (`scripts/compare_retrieval.py`), median retrieval latency changed from 275.4 ms (C5) to 1218.0 ms (C6) across the 54 answerable queries.*

### H5 — Indexing: Context headers still help after re-ranking, where chunks look alike
- **Comparison (`results/results.json`):** `C6 → C7` on `fund_doc` and `ghg_scope3` (plus `annual_report`)

| Document | C6 Correctness | C7 Correctness | Δ Correctness | Flag | C6 Hit@5 | C7 Hit@5 |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: |
| `annual_report` | 80.0% | 75.0% | -5.0 pts | not conclusive (n=20 per doc) | 50.0% | 50.0% |
| `fund_doc` | 42.5% | 50.0% | +7.5 pts | not conclusive (n=20 per doc) | 27.8% | 27.8% |
| `ghg_scope3` | 87.5% | 87.5% | +0.0 pts | not conclusive (n=20 per doc) | 55.6% | 50.0% |

### H6 — All: Most baseline failures happen before generation
- **Comparison (`results/results.json`):** `failures_by_stage` on `C1`

| Document | Ingestion | Indexing | Retrieval | Generation | Total Failures | Pre-Generation Failures |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `annual_report` | 0 | 3 | 2 | 1 | 6 | 5 (83.3%) |
| `fund_doc` | 0 | 2 | 12 | 0 | 14 | 14 (100.0%) |
| `ghg_scope3` | 0 | 1 | 2 | 0 | 3 | 3 (100.0%) |
| **Total (C1)** | **0** | **6** | **16** | **1** | **23** | **22 (95.7%)** |

### H7 — All: No single config wins on all three documents
- **Comparison (`results/results.json`):** Highest `correctness` config per document

| Document | Highest Correctness Config(s) | Top Correctness | Runner-Up Correctness | Gap | Flag |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `annual_report` | `C6` | 80.0% | `C7` (75.0%) | +5.0 pts | not conclusive (n=20 per doc) |
| `fund_doc` | `C7` | 50.0% | `C5` (47.5%) | +2.5 pts | not conclusive (n=20 per doc) |
| `ghg_scope3` | `C1`, `C6`, `C7` (3-way tie) | 87.5% | `C5` (85.0%) | +2.5 pts | not conclusive (n=20 per doc) |

---

## 2. Candidate Failure Examples (by Stage)

*(Includes cases from top-performing configs `C6` and `C7` on each document, plus the single `generation` failure across all 420 runs from `C1`.)*

### Stage: `ingestion` (up to 3 cases)
1. **`[C6 | annual_report | AR-08]`** (`correctness: 0.0`, `results/runs/C6__annual_report__*.jsonl`)
   - **Question:** What was Infosys's standalone profit after tax for fiscal 2026?
   - **Retrieved snippet (200 chars):** `includes profit on sale of property plant and equipment amounting to \` 165 crore on standalone and consolidated basis during the year ended march 31, 2026. - ( 2 ) excluding the effect of income tax o`
   - **Model answer:** `Not found in the documents.`
   - **Gold answer:** `₹29,211 crore`
2. **`[C6 | annual_report | AR-12]`** (`correctness: 0.0`, `results/runs/C6__annual_report__*.jsonl`)
   - **Question:** How large was the fiscal 2026 buyback, and by how much did it reduce standalone retained earnings?
   - **Retrieved snippet (200 chars):** `capital allocation policy the buyback involved the purchase of 10, 00, 00, 000 equity shares, representing approximately 2. 41 % of the company ’ s paid - up equity share capital ( standalone ) as of `
   - **Model answer:** `Not found in the documents.`
   - **Gold answer:** `₹18,000 crore buyback at ₹1,800 per share; standalone retained earnings reduced by ₹16,346 crore`
3. **`[C6 | fund_doc | FD-03]`** (`correctness: 0.0`, `results/runs/C6__fund_doc__*.jsonl`)
   - **Question:** What is the benchmark index of HDFC Large Cap Fund?
   - **Retrieved snippet (200 chars):** `* * hdfc multi - asset allocation fund * * performance has been computed using values of the concerned benchmarks. from inception till december 31, 2017, the benchmark was crisil mip blended index. it`
   - **Model answer:** `Not found in the documents. [fund_doc p.124]`
   - **Gold answer:** `NIFTY 100 Total Returns Index (TRI)`

### Stage: `indexing` (up to 3 cases)
1. **`[C6 | annual_report | AR-11]`** (`correctness: 0.0`, `results/runs/C6__annual_report__*.jsonl`)
   - **Question:** What was Infosys's consolidated total equity as at March 31, 2026?
   - **Retrieved snippet (200 chars):** `* * distribution of shareholding as on march 31, 2026 * * # # 4 | 1. 16 < br > 1. 59 | 6, 43, 28, 426 | | 5, 001 - 10, 000 | 4, 330 | 0. 16 < br > 0. 74 | 3, 01, 87, 900 | | 10, 001 and above | 6, 290`
   - **Model answer:** `Not found in the documents. [annual_report p.94]`
   - **Gold answer:** `₹93,297 crore`
2. **`[C7 | fund_doc | FD-02]`** (`correctness: 0.0`, `results/runs/C7__fund_doc__*.jsonl`)
   - **Question:** When was HDFC Mid Cap Fund launched?
   - **Retrieved snippet (200 chars):** `* * hdfc mid cap fund * * a < br > | s of | | redington ltd. | commercial services < br > & supplies | 0. 84 | july 31, 2026 unless other < br > | wise specified. < br > | | | icici lombard general | `
   - **Model answer:** `Not found in the documents. [fund_doc p.13]`
   - **Gold answer:** `June 25, 2007`
3. **`[C6 | fund_doc | FD-07]`** (`correctness: 0.0`, `results/runs/C6__fund_doc__*.jsonl`)
   - **Question:** What are the Regular and Direct plan expense ratios of HDFC Flexi Cap Fund?
   - **Retrieved snippet (200 chars):** `* * hdfc multi cap fund * * <! - - start of picture text - - > expense ratio < br > ( as on july 31, 2026 ) < br > base expense ratio including statutory levies on < br > expenses part of ber, excludi`
   - **Model answer:** `Not found in the documents. [fund_doc p.9]`
   - **Gold answer:** `Regular 1.27%, Direct 0.65%`

### Stage: `retrieval` (up to 3 cases)
1. **`[C6 | annual_report | AR-13]`** (`correctness: 0.5`, `results/runs/C6__annual_report__*.jsonl`)
   - **Question:** How many times did the Audit Committee and the ESG Committee each meet in fiscal 2026?
   - **Retrieved snippet (200 chars):** `* * committee governance * * the main responsibility of the esg committee is to guide the esg journey of the company embarked from 2011. the esg committee charter can be accessed at https : / / www. i`
   - **Model answer:** `The ESG Committee met four times during fiscal 2026. The annual report does not state how many times the Audit Committee met in fiscal 2026.    Source: [annual_report p.77] and No information on Audit Committee meetings found.`
   - **Gold answer:** `Audit Committee: ten times; ESG Committee: four times`
2. **`[C6 | fund_doc | FD-16]`** (`correctness: 0.0`, `results/runs/C6__fund_doc__*.jsonl`)
   - **Question:** How long is my money locked in if I invest in HDFC's tax-saving fund?
   - **Retrieved snippet (200 chars):** `* * hdfc elss tax saver * * * * ^ past performance may or may not be sustained in future and is not a guarantee of any future returns. * * load is not taken into consideration for computation of perfo`
   - **Model answer:** `Not found in the documents. [fund_doc p.63] [fund_doc p.65]`
   - **Gold answer:** `3 years from the date of allotment (statutory lock-in)`
3. **`[C6 | ghg_scope3 | GH-13]`** (`correctness: 0.0`, `results/runs/C6__ghg_scope3__*.jsonl`)
   - **Question:** Which calculation method is offered for business travel but not for employee commuting, and which is offered for commuting but not business travel?
   - **Retrieved snippet (200 chars):** `* * _ calculating emissions from employee commuting _ * * figure 7. 1 offers a decision tree for selecting a calculation method for scope 3 emissions from employee commuting. companies may use one of `
   - **Model answer:** `Not found in the documents.`
   - **Gold answer:** `Spend-based is offered for business travel only; average-data is offered for employee commuting only (both offer fuel-based and distance-based)`

### Stage: `generation` (up to 3 cases — only 1 case exists across all 420 runs)
1. **`[C1 | annual_report | AR-10]`** (`correctness: 0.0`, `results/runs/C1__annual_report__*.jsonl`)
   - **Question:** What were Infosys's total Scope 2 emissions in fiscal 2026?
   - **Retrieved snippet (200 chars):** `yes, name of the external agency. yes, deloitte haskins & sells llp ( 1 ) scope 1 emissions cover all owned offices ( india, us and china ) and leased offices in india ; leased space in overseas locat`
   - **Model answer:** `Infosys reported total Scope 2 emissions for fiscal 2026 as **1,45,604 tCO₂e**[annual_report p.146].`
   - **Gold answer:** `34,351 tCO2e (market-based)`

---

## 3. Config Rankings per Document (from `results/results.json`)

### `annual_report`
| Rank | Config | Correctness | Hit@5 | Faithfulness | p50 (ms) | p95 (ms) | Tokens / Query |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `C6` | 80.0% | 50.0% | 100.0% | 632 | 1842 | 1141.2 |
| 2 | `C7` | 75.0% | 50.0% | 100.0% | 671 | 2541 | 1135.7 |
| 3 | `C1` | 72.5% | 55.6% | 100.0% | 655 | 1031 | 1569.5 |
| 4 | `C5` | 72.5% | 44.4% | 100.0% | 665 | 1091 | 1092.1 |
| 5 | `C2` | 65.0% | 44.4% | 100.0% | 626 | 1217 | 1503.7 |
| 6 | `C4` | 57.9% | 33.3% | 94.1% | 576 | 838 | 1101.4 |
| 7 | `C3` | 55.0% | 38.9% | 94.4% | 528 | 1054 | 989.1 |

### `fund_doc`
| Rank | Config | Correctness | Hit@5 | Faithfulness | p50 (ms) | p95 (ms) | Tokens / Query |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `C7` | 50.0% | 27.8% | 88.9% | 835 | 993065* | 1144.8 |
| 2 | `C5` | 47.5% | 27.8% | 100.0% | 603 | 868 | 1026.2 |
| 3 | `C6` | 42.5% | 27.8% | 100.0% | 713 | 1089 | 1213.2 |
| 4 | `C4` | 37.5% | 11.1% | 100.0% | 547 | 879 | 1139.7 |
| 5 | `C2` | 32.5% | 5.6% | 100.0% | 565 | 980 | 1296.8 |
| 6 | `C1` | 32.5% | 5.6% | 94.4% | 558 | 1834 | 1404.2 |
| 7 | `C3` | 22.5% | 5.6% | 100.0% | 489 | 795 | 877.0 |

### `ghg_scope3`
| Rank | Config | Correctness | Hit@5 | Faithfulness | p50 (ms) | p95 (ms) | Tokens / Query |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `C6` | 87.5% | 55.6% | 100.0% | 623 | 740 | 1090.5 |
| 2 | `C1` | 87.5% | 61.1% | 100.0% | 759 | 7737 | 1543.8 |
| 3 | `C7` | 87.5% | 50.0% | 94.4% | 442727* | 1792683* | 1046.2 |
| 4 | `C5` | 85.0% | 55.6% | 94.4% | 690 | 1668 | 1069.2 |
| 5 | `C3` | 80.0% | 50.0% | 100.0% | 568 | 791 | 963.2 |
| 6 | `C2` | 80.0% | 44.4% | 100.0% | 978 | 12952 | 1532.3 |
| 7 | `C4` | 77.5% | 55.6% | 100.0% | 585 | 959 | 1026.3 |

*\*Note: C7 `fund_doc` and `ghg_scope3` latency values include Groq daily quota rate-limit backoff sleep time.*
