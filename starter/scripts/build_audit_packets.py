"""Prepare fixed, transparent manual-review samples from one completed run."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "starter"
RESULTS = STARTER / "results"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    pages = {r["page"]: r for r in map(json.loads,
             (STARTER / "data" / "pages.jsonl").read_text(encoding="utf-8").splitlines())}
    traces = [json.loads(line) for line in (RESULTS / "retrieval_traces.jsonl").read_text(encoding="utf-8").splitlines()]
    question_rows = {q["id"]: q for q in json.loads((ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))}

    metadata_rows = []
    grounding_rows = []
    grounding_scores = {"q21": (2, "Top-3 rank 1 on PDF p.45 contains the group/identity evidence."),
                        "q22": (0, "All top-3 results are on p.44; none list the three requested field-research forms from p.46."),
                        "q23": (1, "Top-3 includes nearby covert/participant-observation discussion on p.47, but misses the main-advantage sentence."),
                        "q24": (2, "Top-3 rank 1 on PDF p.48 directly defines institutional ethnography and its focus."),
                        "q25": (2, "Top-3 rank 1 on PDF p.51 states the time, cost and depth benefits." )}
    for trace in traces:
        if trace["split"] != "test":
            continue
        q = question_rows[trace["question_id"]]
        for rank, hit in enumerate(trace["hits"], start=1):
            meta = hit["metadata"]
            page = pages.get(meta.get("page"), {})
            filter_matches = all(str(meta.get(k)) == str(v) for k, v in q.get("filter", {}).items())
            metadata_rows.append({"strategy": trace["strategy"], "question_id": q["id"], "rank": rank,
                                  "chunk_id": hit["chunk_id"], "document_id": meta.get("document_id"),
                                  "source": meta.get("source"), "page": meta.get("page"),
                                  "chapter": meta.get("chapter"), "source_page_exists": bool(page),
                                  "document_id_correct": meta.get("document_id") == page.get("document_id"),
                                  "source_correct": meta.get("source") == page.get("source"),
                                  "page_correct": meta.get("page") == page.get("page"),
                                  "chapter_correct": str(meta.get("chapter")) == str(page.get("chapter")),
                                  "required_filter": json.dumps(q.get("filter", {}), ensure_ascii=False),
                                  "filter_matches_this_hit": filter_matches,
                                  "review_note": "Compare document/source/page/chapter with starter/data/pages.jsonl and data/manifest.json"})
        evidence_flags = [bool(x) for x in trace["evaluation"]["gold_match_by_rank"]]
        score, reason = grounding_scores[q["id"]]
        grounding_rows.append({"strategy": trace["strategy"], "question_id": q["id"],
                               "question": q["question"], "gold_page": q["gold_page"],
                               "top3_evidence_hit": any(evidence_flags),
                               "top3_page_ids": ";".join(str(h["metadata"].get("page")) for h in trace["hits"]),
                               "grounding_score_0_1_2": score,
                               "review_reason": reason,
                               "reviewer": "Codex (AI-assisted rubric review)",
                               "author_review_status": "Student sign-off pending",
                               "blind_llm_judge": False})

    write_csv(RESULTS / "metadata_audit_top3_test.csv", metadata_rows)
    write_csv(RESULTS / "grounding_audit_test.csv", grounding_rows)

    # Fixed sorted-page sample; each target is a complete sentence near the page's first third.
    page_ids = sorted(pages)[:10]
    traces_by_strategy_page = {}
    for t in traces:
        for hit in t["hits"]:
            m = hit["metadata"]
            traces_by_strategy_page.setdefault((t["strategy"], m.get("page")), []).append(hit)
    coherence = []
    coherence_score = {
        14: {"A": (1, "The target sentence is complete, but the fixed window ends with a clipped follow-on phrase."),
             "B": (2, "The target and surrounding group examples form complete sentences; the chunk ends cleanly."),
             "C": (2, "Same complete sentence-boundary chunk as B.")},
        15: {"A": (1, "The chunk opens with a continuation from the prior page, so its first thought lacks a subject."),
             "B": (1, "The target is clear, but the chunk still opens with an inherited sentence fragment."),
             "C": (1, "Same inherited opening fragment as B.")},
        17: {"A": (1, "The fixed window starts in table values and cuts the follow-on explanation."),
             "B": (2, "The complete question and explanation about economic factors are preserved."),
             "C": (2, "Same complete sentence-boundary chunk as B.")},
        18: {"A": (2, "The case context and target sentence are complete and understandable."),
             "B": (2, "The move, city experience and target sentence retain their context."),
             "C": (2, "Same contextual sentence-boundary chunk as B.")},
        19: {"A": (1, "The page begins mid-thought; the target sentence is present but prior context is missing."),
             "B": (1, "Sentence boundaries preserve the target, but the page-opening fragment remains."),
             "C": (1, "Same page-opening fragment as B.")},
        20: {"A": (1, "The introductory context is present, but the fixed window cuts off at a dangling name."),
             "B": (2, "The Manifesto context and Marx's explanation remain together in complete sentences."),
             "C": (2, "Same complete sentence-boundary chunk as B.")},
        21: {"A": (2, "The research example, populations compared and conclusion are readable together."),
             "B": (2, "Complete sentences retain the method and its conclusion."),
             "C": (2, "Same sentence-boundary chunk as B.")},
        22: {"A": (2, "The minimum-wage example and public-sociology context are complete."),
             "B": (2, "The example and its public-sociology link remain clear."),
             "C": (2, "Same sentence-boundary chunk as B.")},
        23: {"A": (1, "The window cuts the body analogy mid-sentence and begins beside a partial table row."),
             "B": (2, "The functionalism statement and body analogy are complete and explained."),
             "C": (2, "Same complete sentence-boundary chunk as B.")},
        24: {"A": (1, "The fixed window cuts the claim about historical empires before its conclusion."),
             "B": (2, "The full claim and follow-up explanation about communication/trade are retained."),
             "C": (2, "Same complete sentence-boundary chunk as B.")}}
    for page_id in page_ids:
        text = pages[page_id]["text"]
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) >= 80]
        target = next((s for s in sentences if 220 <= text.find(s) <= max(220, len(text) // 3)),
                     sentences[0] if sentences else text[:400])
        target_start = text.find(target)
        target_mid = target_start + len(target) // 2
        for strategy in ("A", "B", "C"):
            candidates = [h for h in traces_by_strategy_page.get((strategy, page_id), [])]
            # Query hits cover only some pages, so get chunk text by replaying chunk boundaries from the index.
            # The corpus page and chunks are saved separately below by scanning the persistent collections.
            coherence.append({"strategy": strategy, "page_id": page_id,
                              "target_char_start": target_start, "target_char_end": target_start + len(target),
                              "target_sentence": target, "chunk_id": "", "chunk_char_start": "",
                              "chunk_char_end": "", "chunk_text": "",
                              "score_0_1_2": coherence_score[page_id][strategy][0],
                              "reason": coherence_score[page_id][strategy][1],
                              "reviewer": "Codex (AI-assisted rubric review)",
                              "author_review_status": "Student sign-off pending"})

    # Chroma query top-k is not a corpus export; load persisted chunk records from deterministic IDs.
    # The run pipeline writes chunk snapshots here to make manual selection auditable.
    chunks_file = RESULTS / "chunk_snapshots.jsonl"
    if chunks_file.exists():
        chunks = [json.loads(x) for x in chunks_file.read_text(encoding="utf-8").splitlines()]
        by_strategy_page = {}
        for c in chunks:
            by_strategy_page.setdefault((c["strategy"], c["page"]), []).append(c)
        for row in coherence:
            midpoint = (row["target_char_start"] + row["target_char_end"]) // 2
            options = by_strategy_page.get((row["strategy"], row["page_id"]), [])
            chunk = next((c for c in options if c["char_start"] <= midpoint < c["char_end"]), None)
            if chunk:
                row.update({"chunk_id": chunk["chunk_id"], "chunk_char_start": chunk["char_start"],
                            "chunk_char_end": chunk["char_end"], "chunk_text": chunk["text"]})
    write_csv(RESULTS / "coherence_audit_first10_pages.csv", coherence)

    filter_rows = []
    for split in ("dev", "test"):
        for strategy in ("A", "B", "C"):
            selected = [t for t in traces if t["split"] == split and t["strategy"] == strategy
                        and question_rows[t["question_id"]].get("filter")]
            compliant_questions = 0
            compliant_hits = total_hits = 0
            for t in selected:
                filt = question_rows[t["question_id"]]["filter"]
                flags = [all(str(h["metadata"].get(k)) == str(v) for k, v in filt.items()) for h in t["hits"]]
                compliant_hits += sum(flags)
                total_hits += len(flags)
                compliant_questions += bool(flags and all(flags))
            filter_rows.append({"strategy": strategy, "split": split,
                                "filtered_questions": len(selected),
                                "top3_fully_compliant_questions": f"{compliant_questions}/{len(selected)}" if selected else "N/A",
                                "compliant_hits": f"{compliant_hits}/{total_hits}" if total_hits else "N/A",
                                "filter_enforced_by_strategy": strategy == "C"})
    write_csv(RESULTS / "filter_compliance.csv", filter_rows)
    print(f"Prepared {len(metadata_rows)} metadata rows, {len(grounding_rows)} grounding rows, {len(coherence)} coherence rows")


if __name__ == "__main__":
    main()
