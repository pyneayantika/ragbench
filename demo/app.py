"""
What it does: Gradio demo chat that answers from the winning config's prebuilt index.
Why it exists: Readers need to try the setup the benchmark recommends.
What breaks without it: The results stay a table, with no way to ask a question.
Failure stage: generation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import gradio as gr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.generate import CITATION_RE, generate_answer
from src.index import get_embedder
from src.retrieve import get_reranker, retrieve_chunks

MAX_QUESTIONS_PER_SESSION = 20
MAX_QUESTION_CHARS = 500
REFUSAL_TEXT = "Not found in the documents."

DOC_EDITIONS: dict[str, str] = {
    "annual_report": "Infosys Annual Report 2025-26 (downloaded 2026-11-18)",
    "fund_doc": "HDFC Mutual Fund Factsheet — July 2026 (downloaded 2026-11-18)",
    "ghg_scope3": "GHG Protocol Scope 3 Calculation Guidance (downloaded 2026-11-18)",
}

PROMPT_INJECTION_PATTERNS = (
    "ignore your instructions",
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "reveal your prompt",
    "print your prompt",
)


def _load_winner_stats() -> tuple[str, dict[str, Any]]:
    results_path = ROOT / "results" / "results.json"
    if not results_path.is_file():
        return "C7", {"mean_correctness": None, "mean_refusal": None, "by_doc": {}}

    data = json.loads(results_path.read_text(encoding="utf-8"))
    rows = data.get("results", [])
    winners = data.get("winners") or {}

    by_cfg: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cfg.setdefault(str(row["config_id"]), []).append(row)

    winner_id = str(winners.get("overall") or "")
    if not winner_id and by_cfg:
        winner_id = max(
            by_cfg.keys(),
            key=lambda cid: sum(float(r["correctness"]) for r in by_cfg[cid]) / len(by_cfg[cid]),
        )
    if not winner_id:
        winner_id = "C7"

    cfg_rows = by_cfg.get(winner_id, [])
    mean_corr = (
        sum(float(r["correctness"]) for r in cfg_rows) / len(cfg_rows) if cfg_rows else None
    )
    mean_refusal = (
        sum(float(r["refusal_accuracy"]) for r in cfg_rows) / len(cfg_rows) if cfg_rows else None
    )
    by_doc = {str(r["doc_id"]): r for r in cfg_rows}
    return winner_id, {
        "mean_correctness": mean_corr,
        "mean_refusal": mean_refusal,
        "by_doc": by_doc,
    }


WINNING_CONFIG_ID, WINNER_STATS = _load_winner_stats()
WINNING_CONFIG = load_config(WINNING_CONFIG_ID)


def preload_models() -> None:
    """Load embedding and reranker models once at startup (never per question)."""
    get_embedder(str(WINNING_CONFIG["embedding_model"]))
    rerank_cfg = WINNING_CONFIG.get("rerank") or {}
    if rerank_cfg.get("enabled") and rerank_cfg.get("model"):
        get_reranker(str(rerank_cfg["model"]))


def _format_chunks_markdown(doc_id: str, hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "_No chunks retrieved._"
    blocks: list[str] = []
    for idx, hit in enumerate(hits, start=1):
        blocks.append(
            f"### {idx}. `[{doc_id} p.{hit['page_start']}]` "
            f"(chunk `{hit['chunk_id']}`, score `{float(hit['score']):.4f}`)\n\n"
            f"{hit['text']}"
        )
    return "\n\n---\n\n".join(blocks)


def answer_question(
    doc_id: str,
    question: str,
    session_count: int,
) -> tuple[str, str, str, int, str]:
    """Run retrieval + grounded generation with GUARDRAILS §3 enforcement. No question logging."""
    if doc_id not in DOC_EDITIONS:
        return (
            "Please select a valid document.",
            "None",
            "_No chunks retrieved._",
            session_count,
            f"Session questions used: {session_count} / {MAX_QUESTIONS_PER_SESSION}",
        )

    cleaned = (question or "").strip()
    if not cleaned:
        return (
            "Please enter a question.",
            "None",
            "_No chunks retrieved._",
            session_count,
            f"Session questions used: {session_count} / {MAX_QUESTIONS_PER_SESSION}",
        )

    if len(cleaned) > MAX_QUESTION_CHARS:
        return (
            f"Question exceeds the {MAX_QUESTION_CHARS}-character limit ({len(cleaned)} chars). Please shorten your question.",
            "None",
            "_No chunks retrieved._",
            session_count,
            f"Session questions used: {session_count} / {MAX_QUESTIONS_PER_SESSION}",
        )

    if session_count >= MAX_QUESTIONS_PER_SESSION:
        return (
            f"Session limit reached ({MAX_QUESTIONS_PER_SESSION} questions per session). Refresh to start a new session.",
            "None",
            "_No chunks retrieved._",
            session_count,
            f"Session questions used: {session_count} / {MAX_QUESTIONS_PER_SESSION}",
        )

    next_count = session_count + 1
    status_text = f"Session questions used: {next_count} / {MAX_QUESTIONS_PER_SESSION}"

    lowered = cleaned.lower()
    if any(pattern in lowered for pattern in PROMPT_INJECTION_PATTERNS):
        return (
            REFUSAL_TEXT,
            "None (refused)",
            "_Prompt-injection / off-topic instruction rejected before retrieval._",
            next_count,
            status_text,
        )

    if not os.environ.get("GROQ_API_KEY", "").strip():
        # Allow local .env loading inside src.generate.get_client()
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        if not os.environ.get("GROQ_API_KEY", "").strip():
            return (
                "GROQ_API_KEY is not configured in the environment.",
                "None",
                "_No chunks retrieved._",
                session_count,
                f"Session questions used: {session_count} / {MAX_QUESTIONS_PER_SESSION}",
            )

    hits = retrieve_chunks(doc_id, WINNING_CONFIG, cleaned)
    passages = [(int(hit["page_start"]), str(hit["text"])) for hit in hits]
    result = generate_answer(cleaned, doc_id, passages, calls_per_minute=30.0)
    answer_text = str(result["answer"])

    found_citations = sorted(set(CITATION_RE.findall(answer_text)))
    citations_text = ", ".join(found_citations) if found_citations else "None"
    chunks_md = _format_chunks_markdown(doc_id, hits)

    return answer_text, citations_text, chunks_md, next_count, status_text


def build_demo() -> gr.Blocks:
    mean_corr = WINNER_STATS["mean_correctness"]
    mean_ref = WINNER_STATS["mean_refusal"]
    corr_str = f"{mean_corr * 100:.1f}%" if mean_corr is not None else "N/A"
    ref_str = f"{mean_ref * 100:.1f}%" if mean_ref is not None else "N/A"

    editions_md = "\n".join(f"- **`{k}`**: {v}" for k, v in DOC_EDITIONS.items())

    with gr.Blocks(title="RAGBench Live Demo") as demo:
        session_state = gr.State(0)

        gr.Markdown("# RAGBench — Grounded Document Q&A Demo")
        gr.Markdown(
            "> **Research demo.** Answers come only from three public documents as of **2026-11-18**. "
            "**Not financial or investment advice.** Visitor questions are **not logged**."
        )

        with gr.Row():
            with gr.Column(scale=2):
                doc_dropdown = gr.Dropdown(
                    choices=[(v, k) for k, v in DOC_EDITIONS.items()],
                    value="annual_report",
                    label="Select Document",
                )
                question_box = gr.Textbox(
                    label=f"Ask a question (max {MAX_QUESTION_CHARS} characters)",
                    placeholder="e.g. What share of Infosys's office space is certified as green buildings?",
                    max_length=MAX_QUESTION_CHARS,
                    lines=2,
                )
                with gr.Row():
                    ask_btn = gr.Button("Ask", variant="primary")
                    session_label = gr.Markdown(
                        f"Session questions used: 0 / {MAX_QUESTIONS_PER_SESSION}"
                    )

                answer_out = gr.Textbox(label="Answer", lines=4, interactive=False)
                citations_out = gr.Textbox(label="Citations", lines=1, interactive=False)

                with gr.Accordion("Retrieved Chunks (Top 5)", open=False):
                    chunks_out = gr.Markdown("_Submit a question to inspect retrieved chunks._")

            with gr.Column(scale=1):
                gr.Markdown(
                    f"### Active Configuration: `{WINNING_CONFIG_ID}`\n"
                    f"- **Description:** {WINNING_CONFIG.get('description', '')}\n"
                    f"- **Measured Mean Correctness:** **{corr_str}**\n"
                    f"- **Measured Refusal Accuracy:** **{ref_str}**\n\n"
                    f"### Document Editions & Dates\n"
                    f"{editions_md}\n\n"
                    f"### Session Guardrails\n"
                    f"- Max **{MAX_QUESTIONS_PER_SESSION}** questions per session\n"
                    f"- Max **{MAX_QUESTION_CHARS}** characters per question\n"
                    f"- Strictly grounded: replies *\"{REFUSAL_TEXT}\"* when unsupported\n"
                    f"- Zero logging of visitor questions"
                )

        ask_btn.click(
            fn=answer_question,
            inputs=[doc_dropdown, question_box, session_state],
            outputs=[answer_out, citations_out, chunks_out, session_state, session_label],
        )

    return demo


if __name__ == "__main__":
    preload_models()
    app = build_demo()
    app.launch()
