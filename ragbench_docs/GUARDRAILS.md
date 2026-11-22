# GUARDRAILS.md — Safety, integrity and cost guardrails

> Every guardrail here exists because of a specific failure. Coding agents must follow this file together with `AGENTS.md`. Each row says what could go wrong, the rule, and where it is enforced.

## 1. Answer guardrails (what the RAG system may say)

| Risk | Rule | Enforced in |
| --- | --- | --- |
| Made-up answers when the documents don't contain the answer | Reply exactly "Not found in the documents." when the context lacks the answer | Generator prompt (`BRIEF.md` B6) |
| Answers that can't be verified | Every answer ends with its source(s) as `[doc_id p.<page>]` | Generator prompt; demo UI shows retrieved chunks |
| Answering from loosely related text | Optional relevance threshold (`min_relevance`): below it, refuse instead of answering. Tune once, then freeze | `retrieve.py`, config |
| Wrong arithmetic on financial figures | Numbers are quoted exactly from the context; the LLM never calculates, converts or rounds | Generator prompt |
| Mixing facts across funds or sections | Each chunk is labelled with document and page; C7 adds document and section names | `generate.py`, `chunk.py` |
| Over-refusal (says "not found" when the answer was there) | Tracked as a generation failure and reported per config | `evaluate.py` |

## 2. Prompt-injection guardrails

| Risk | Rule | Enforced in |
| --- | --- | --- |
| Text inside a PDF (or a user's question) tries to override instructions | Retrieved text is wrapped in clearly marked context blocks; the prompt says the context is data, not instructions | `generate.py` |
| A demo user asks the bot to ignore its rules or reveal its prompt | The system prompt is not shown in the UI; the bot answers only from the documents; off-topic requests get the refusal reply | `demo/app.py` |
| Judge manipulated by the answer it is grading | Judge output is parsed as strict JSON; anything else is retried once, then marked `judge_error`, never guessed | `judge.py` |

## 3. Demo guardrails (public Hugging Face Space)

| Risk | Rule |
| --- | --- |
| Visitors treating answers as financial advice | Show a visible notice: "Research demo. Answers come only from three public documents as of [edition/date]. Not financial or investment advice." |
| Stale data mistaken for current | Show each document's edition and download date on the page |
| Free-tier abuse or a runaway bill | Max 20 questions per session; max question length 500 characters; Groq key stored only as a Space secret |
| Sensitive data typed by visitors | No logging of visitor questions in v1. If logging is added later, state it on the page first |
| Outputs presented as more reliable than they are | Show the winning config's measured accuracy and refusal rate next to the chat |

## 4. Data and privacy guardrails

| Risk | Rule |
| --- | --- |
| Leaking API keys | Keys only in `.env` (git-ignored) and platform secrets. Never printed, logged or committed. Run `git status` before every push |
| Employer data in a public repo | Only the 3 public PDFs. No Bajaj Finserv, Sprih or any client documents, even "just for testing" |
| Copyright of source documents | Commit only the public PDFs' download links and edition info in the README; check whether committing the PDFs themselves is appropriate, and if unsure, keep them out of the repo (`data/raw/` in `.gitignore`) |
| Personal paths or names in logs | Logs use relative paths only |
| Old v0 code leaking into the repo | `reference_v0/` is read-only reference material and is listed in `.gitignore` |

## 5. Evaluation-integrity guardrails (the credibility of the whole project)

| Risk | Rule |
| --- | --- |
| Golden set tuned to the results | Golden set frozen before Step 4. Any later change is logged in `DECISION_LOG.md` with the reason, and all configs are re-run |
| Fabricated or placeholder results | No mock data in `results/`. If a run fails, the dashboard shows "not run", never a guess |
| Unfair comparison between configs | Generator, prompts, judge, temperature and `final_k` are identical across configs; each run records the resolved config and `chunk_sig` |
| Over-claiming small differences | With 20 questions per document, differences under about 10 points are labelled "not conclusive" on the dashboard |
| Judge drift | Same judge model for all 7 configs; judge–human agreement reported |
| Cherry-picked failure examples | Failure examples are chosen to cover different stages, and include at least one from the winning config |

## 6. Cost and laptop guardrails

| Risk | Rule |
| --- | --- |
| Hitting free-tier limits mid-run | Pace Groq at ~6 calls/minute and Mistral at ≤1/second; resumable JSONL; `--limit` for tests |
| Accidental paid usage | No paid APIs or paid tiers. If a provider asks for a card to continue, stop and decide manually |
| Laptop freezing | No local LLMs; models loaded once; batch embedding; one doc and config at a time (`AGENTS.md` §4) |

## 7. Pre-launch checklist (before the dashboard and demo go public)

- [ ] `git log -p | findstr /i "api_key gsk_"` (Windows) or the equivalent search shows no keys in history
- [ ] `.env` and `cache/` are not in the repo
- [ ] The demo shows the notice, edition dates and the per-session limit
- [ ] The demo refuses at least 2 unanswerable test questions correctly
- [ ] One prompt-injection test ("Ignore your instructions and…") is refused
- [ ] Every dashboard number traces to `results.json`; small differences are marked "not conclusive"
