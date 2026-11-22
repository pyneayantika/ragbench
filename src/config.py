"""
What it does: Loads one YAML config and rejects missing fields or values the brief does not allow.
Why it exists: Only the config file may change between runs, so a typo must fail before any benchmark starts.
What breaks without it: A bad config would silently make two setups incomparable.
Failure stage: evaluation.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"

ALLOWED_PARSING = {"basic", "layout"}
ALLOWED_STRATEGY = {"fixed", "structure"}
ALLOWED_EMBEDDING = {
    "sentence-transformers/all-MiniLM-L6-v2",
    "BAAI/bge-small-en-v1.5",
}
ALLOWED_MODE = {"dense", "hybrid"}
ALLOWED_STAGE = {None, "ingestion", "indexing", "retrieval"}
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_KEYS = (
    "config_id",
    "version",
    "description",
    "stage_changed",
    "parsing",
    "chunking",
    "embedding_model",
    "retrieval",
    "rerank",
    "final_k",
    "min_relevance",
)
CHUNK_KEYS = ("strategy", "max_tokens", "overlap_tokens", "contextual_headers")
RETRIEVAL_KEYS = ("mode", "candidate_k", "rrf_k")
RERANK_KEYS = ("enabled", "model")
TABLE_HEADERS = (
    "config",
    "stage_changed",
    "parsing",
    "chunking",
    "embedding",
    "retrieval",
    "rerank",
    "headers",
    "candidate_k",
    "final_k",
)


def _require_keys(data: dict[str, Any], keys: tuple[str, ...], label: str, errors: list[str]) -> None:
    missing = [key for key in keys if key not in data]
    extra = [key for key in data if key not in keys]
    if missing:
        errors.append(f"{label} missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"{label} unknown keys: {', '.join(extra)}")


def _check_choices(cfg: dict[str, Any], errors: list[str]) -> None:
    if cfg.get("parsing") not in ALLOWED_PARSING:
        errors.append(f"parsing must be one of {sorted(ALLOWED_PARSING)}")
    if cfg.get("embedding_model") not in ALLOWED_EMBEDDING:
        errors.append(f"embedding_model must be one of {sorted(ALLOWED_EMBEDDING)}")
    if cfg.get("stage_changed") not in ALLOWED_STAGE:
        errors.append("stage_changed must be null, ingestion, indexing, or retrieval")
    chunking = cfg.get("chunking")
    if isinstance(chunking, dict) and chunking.get("strategy") not in ALLOWED_STRATEGY:
        errors.append(f"chunking.strategy must be one of {sorted(ALLOWED_STRATEGY)}")
    retrieval = cfg.get("retrieval")
    if isinstance(retrieval, dict) and retrieval.get("mode") not in ALLOWED_MODE:
        errors.append(f"retrieval.mode must be one of {sorted(ALLOWED_MODE)}")


def _check_constants(cfg: dict[str, Any], errors: list[str]) -> None:
    chunking = cfg.get("chunking") if isinstance(cfg.get("chunking"), dict) else {}
    retrieval = cfg.get("retrieval") if isinstance(cfg.get("retrieval"), dict) else {}
    rerank = cfg.get("rerank") if isinstance(cfg.get("rerank"), dict) else {}
    if cfg.get("version") != 1:
        errors.append("version must be 1")
    if cfg.get("final_k") != 5:
        errors.append("final_k must be 5")
    if chunking.get("max_tokens") != 256:
        errors.append("chunking.max_tokens must be 256")
    if chunking.get("overlap_tokens") != 30:
        errors.append("chunking.overlap_tokens must be 30")
    if not isinstance(chunking.get("contextual_headers"), bool):
        errors.append("chunking.contextual_headers must be true or false")
    if retrieval.get("rrf_k") != 60:
        errors.append("retrieval.rrf_k must be 60")
    if not isinstance(rerank.get("enabled"), bool):
        errors.append("rerank.enabled must be true or false")
    expected_k = 20 if rerank.get("enabled") is True else 5
    if retrieval.get("candidate_k") != expected_k:
        errors.append(f"retrieval.candidate_k must be {expected_k} when rerank.enabled is {rerank.get('enabled')}")
    if rerank.get("enabled") is True and rerank.get("model") != RERANK_MODEL:
        errors.append(f"rerank.model must be {RERANK_MODEL} when rerank is enabled")
    if rerank.get("enabled") is False and rerank.get("model") is not None:
        errors.append("rerank.model must be null when rerank is disabled")
    relevance = cfg.get("min_relevance")
    if relevance is not None and not isinstance(relevance, (int, float)):
        errors.append("min_relevance must be null or a number")
    if not isinstance(cfg.get("description"), str) or not cfg.get("description", "").strip():
        errors.append("description must be a non-empty string")
    config_id = cfg.get("config_id")
    if not isinstance(config_id, str) or config_id not in {f"C{i}" for i in range(1, 8)}:
        errors.append("config_id must be C1 through C7")


def validate_config(cfg: dict[str, Any], filename: str) -> None:
    errors: list[str] = []
    _require_keys(cfg, TOP_KEYS, filename, errors)
    if isinstance(cfg.get("chunking"), dict):
        _require_keys(cfg["chunking"], CHUNK_KEYS, f"{filename} chunking", errors)
    else:
        errors.append(f"{filename} chunking must be a mapping")
    if isinstance(cfg.get("retrieval"), dict):
        _require_keys(cfg["retrieval"], RETRIEVAL_KEYS, f"{filename} retrieval", errors)
    else:
        errors.append(f"{filename} retrieval must be a mapping")
    if isinstance(cfg.get("rerank"), dict):
        _require_keys(cfg["rerank"], RERANK_KEYS, f"{filename} rerank", errors)
    else:
        errors.append(f"{filename} rerank must be a mapping")
    _check_choices(cfg, errors)
    _check_constants(cfg, errors)
    expected_id = filename.removesuffix(".yaml").upper()
    if cfg.get("config_id") != expected_id:
        errors.append(f"{filename} config_id must be {expected_id}")
    if errors:
        raise ValueError("; ".join(errors))


def load_config(name: str) -> dict[str, Any]:
    key = name.strip().lower()
    path = CONFIG_DIR / f"{key}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"No config file at {path.relative_to(ROOT)}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.name} must contain a YAML mapping")
    validate_config(loaded, path.name)
    return loaded


def _table_row(cfg: dict[str, Any]) -> list[str]:
    stage = cfg["stage_changed"] if cfg["stage_changed"] is not None else "none"
    return [
        str(cfg["config_id"]),
        stage,
        str(cfg["parsing"]),
        str(cfg["chunking"]["strategy"]),
        str(cfg["embedding_model"]),
        str(cfg["retrieval"]["mode"]),
        "yes" if cfg["rerank"]["enabled"] else "no",
        "yes" if cfg["chunking"]["contextual_headers"] else "no",
        str(cfg["retrieval"]["candidate_k"]),
        str(cfg["final_k"]),
    ]


def format_table(configs: list[dict[str, Any]]) -> str:
    rows = [_table_row(cfg) for cfg in configs]
    widths = [len(header) for header in TABLE_HEADERS]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    lines = ["  ".join(header.ljust(width) for header, width in zip(TABLE_HEADERS, widths))]
    lines.append("  ".join("-" * width for width in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(width) for cell, width in zip(row, widths)))
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(argv) != 1 or argv[0].lower() not in {f"c{i}" for i in range(1, 8)} | {"all"}:
        raise SystemExit("Usage: python -m src.config <c1|c2|c3|c4|c5|c6|c7|all>")
    names = [f"c{i}" for i in range(1, 8)] if argv[0].lower() == "all" else [argv[0].lower()]
    configs = [load_config(name) for name in names]
    logger.info(format_table(configs))
    for cfg in configs:
        logger.info("validated %s (%s)", cfg["config_id"], cfg["description"])


if __name__ == "__main__":
    main(sys.argv[1:])
