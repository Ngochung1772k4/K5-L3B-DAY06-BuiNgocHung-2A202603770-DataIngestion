"""Evidence-based retrieval evaluation and transparent aggregation."""
import re
import unicodedata
from typing import Any


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _hit(question: dict[str, Any], item: dict[str, Any]) -> bool:
    meta = item.get("metadata", {})
    source_ok = meta.get("document_id") == question["gold_source_id"]
    page_ok = meta.get("page") in question.get("gold_pages", [question["gold_page"]])
    quote = _norm(question["evidence_quote"])
    return source_ok and page_ok and quote in _norm(item.get("text", ""))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Exact evidence matching; this is not a replacement for the manual audits."""
    flags = [_hit(question, hit) for hit in hits]
    return {"hit_at_1": bool(flags and flags[0]), "evidence_hit_at_3": any(flags),
            "gold_match_by_rank": flags}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate n/N and rate by strategy/split without mixing dev and test."""
    summary = {}
    for strategy in sorted({t["strategy"] for t in traces}):
        summary[strategy] = {}
        for split in ("dev", "test"):
            rows = [t for t in traces if t["strategy"] == strategy and t["split"] == split]
            if not rows:
                continue
            h1 = sum(t["evaluation"]["hit_at_1"] for t in rows)
            h3 = sum(t["evaluation"]["evidence_hit_at_3"] for t in rows)
            summary[strategy][split] = {"n": len(rows), "hit_at_1": f"{h1}/{len(rows)}",
                                        "hit_at_1_rate": h1 / len(rows),
                                        "evidence_hit_at_3": f"{h3}/{len(rows)}",
                                        "evidence_hit_at_3_rate": h3 / len(rows)}
    return summary
