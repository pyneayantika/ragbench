# GOLDEN_SET_GUIDE.md — How to write the 60 test questions

> The golden set is the most important artifact in RAGBench. Every number in the project is only as trustworthy as these 60 rows. **Every row is human-verified, and all rows are written before you see any retrieval results.**

## 1. Why hand-written, and why first

- **You define "correct".** That's a product decision, not an engineering one.
- **Writing before building avoids bias.** If you write questions after seeing retrieval results, you'll unconsciously favour what already works.
- **It's your strongest interview story:** "I wrote 60 test cases across 5 question types to find where RAG breaks."

## 2. Preparing the documents

1. Choose 3 public PDFs (see `BRIEF.md`, Corpus).
2. **The pipeline indexes each document in full, up to about 150 pages.** If a document is longer, keep the most relevant 150 pages (ask the agent: *"Write scripts/trim_pdf.py that keeps pages X–Y of a PDF using PyMuPDF."*).
3. **You write questions only from sections you read closely**, about 30–40 pages per document:
   - Annual report: at least 5 two-column pages and 5 pages of financial tables.
   - Fund document: the scheme summary, expense ratios, fund manager and benchmark tables.
   - GHG Scope 3 guidance: 2–3 category chapters (e.g. Category 1, 6, 7).
   The rest of the document still matters: it is the "competition" the right passage must beat during retrieval.
4. **Page numbers = the page index in the PDF file you indexed, starting at 1.** Not the printed page number in the footer. This is the most common golden-set mistake. Check it in a PDF viewer.

## 2b. The workflow: start from the answer, not the question

1. Read a section of the PDF and find a fact worth testing.
2. **Copy that sentence** into `supporting_text`. This is your citation.
3. Note the page number from the PDF viewer.
4. Write the short `gold_answer`.
5. Now write the question a real user would ask to get that answer.

You never search for answers or citations; they are where you start. Expect about 4–6 minutes per question, so about 5 hours for 60.
Exceptions: **unanswerable** (write a plausible question, then Ctrl+F the full PDF to confirm it isn't there) and **multi** (pick two facts on different pages, copy both sentences, write one question needing both).

## 3. The mix (per document, 20 questions)

| `qtype` | Count | What makes a good one |
| --- | --- | --- |
| `fact` | 6 | One clear fact stated in prose. |
| `table` | 5 | The answer is a number in a table; the question names the row and column (e.g. plan and metric). |
| `multi` | 4 | Needs 2 passages, ideally on different pages. |
| `paraphrase` | 3 | Uses different words from the document ("travel emissions" for "Category 6: Business travel"). |
| `unanswerable` | 2 | Plausible for this document, but genuinely not anywhere in the indexed PDF (confirm with Ctrl+F on key terms). |

Total: 60 (20 × 3). Question IDs: `AR-01…AR-20`, `FD-01…FD-20`, `GH-01…GH-20`.

## 4. CSV format (`data/golden_set.csv`)

```csv
qid,doc_id,question,qtype,gold_answer,source_page,supporting_text,source
FD-01,fund_doc,"<question>",fact,"<short answer>",3,"<exact sentence copied from the PDF>",human
FD-06,fund_doc,"<question>",table,"<number with unit>",5,"<the table row as it appears>",ai_assisted
FD-12,fund_doc,"<question>",multi,"<answer combining both>",4,"<passage 1> ||| <passage 2>",human
FD-19,fund_doc,"<question>",unanswerable,,,,human
```

Rules for each column:

- **`question`:** natural, the way a real user would ask. One question per row.
- **`gold_answer`:** short and checkable. Include units ("0.65%", "₹2,340 crore"). No explanations.
- **`source_page`:** page in the trimmed PDF. For `multi`, use the first passage's page.
- **`supporting_text`:** **copy-paste** from the PDF viewer, don't retype. Keep it to the shortest span that proves the answer (1–2 sentences, or one table row). For `multi`, separate passages with ` ||| `.
- **`unanswerable`:** leave `gold_answer`, `source_page` and `supporting_text` empty.
- **`source`:** `human` or `ai_assisted` (see §7).

## 5. Examples of the patterns (adapt to your actual documents)

These show the *shape* of a good question. They are not real answers; write yours from your PDFs.

| Type | Weak question | Strong question | Why stronger |
| --- | --- | --- | --- |
| fact | "Tell me about the fund." | "Who is the fund manager of the scheme?" | One checkable answer |
| table | "What are the charges?" | "What is the total expense ratio of the Direct plan?" | Names row and column |
| multi | "How did the company do?" | "How did revenue and net profit each change from last year?" | Needs 2 specific passages |
| paraphrase | "What is Category 6?" | "How should a company account for emissions from employees' flights?" | Different words, same meaning |
| unanswerable | "What is the meaning of life?" | "What was the fund's return in 2015?" (when the doc covers later years only) | Plausible, so it really tests refusal |

## 6. Quality checklist (run before saving)

- [ ] 20 rows per document, with the exact type counts above.
- [ ] Every answerable row has `gold_answer`, `source_page` and `supporting_text`.
- [ ] Every `supporting_text` was copy-pasted and actually contains the answer.
- [ ] Page numbers checked in the **trimmed** PDF.
- [ ] No question can be answered from general knowledge alone (otherwise you're testing the LLM's memory, not retrieval).
- [ ] At least 3 table questions per document involve numbers that appear more than once in the document (these are hard cases for retrieval).
- [ ] At least 2 questions target two-column pages in the annual report.
- [ ] Unanswerable questions are plausible for the document, not absurd.
- [ ] No two questions have the same supporting text.

## 7. How this compares with industry practice

Companies build golden sets from three sources: **expert-written** rows (most trusted), **AI-drafted rows reviewed by humans** (fast, but biased toward easy questions phrased like the source text), and **real user questions from production logs**, especially thumbs-down ones, which grow into a regression set. RAGBench has no production users yet, so the author plays the expert.

**Optional AI-assisted drafting:** for `fact` and `table` questions only, an AI may *suggest* questions from a page you pick. You verify every answer in the PDF and copy the supporting sentence yourself. Always write `paraphrase`, `multi` and `unanswerable` yourself: these are the hard cases AI-drafted sets miss. Record it in a `source` column (`human` or `ai_assisted`) and state it in the case study, e.g. "30 rows AI-assisted, all 60 human-verified".

## 8. Hand-scoring protocol (Step 9)

- Pick 20 answers: about 7 per document, mixed configs and question types, including at least 4 the judge marked wrong.
- Score them **before** looking at the judge's score: 1 = fully correct, 0.5 = partly correct or missing a unit, 0 = wrong or unsupported.
- Record them in `results/hand_scores.csv`: `qid, config_id, my_score, note`.
- Agreement = same score. Report it as "the judge agreed with me on X of 20" and read every disagreement.
