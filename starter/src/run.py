"""Run ingestion and the three controlled retrieval strategies end to end."""
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .chunking import by_paragraph, fixed_size
from .embeddings import LocalFastEmbedder
from .evaluation import evaluate_query, summarize
from .models import DocumentPage
from .store import ChromaVectorStore

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "starter"
PAGES_FILE = STARTER / "data" / "pages.jsonl"
QUESTIONS_FILE = ROOT / "benchmark" / "questions.json"
RESULTS = STARTER / "results"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIMENSIONS = 384


def read_pages() -> list[DocumentPage]:
    pages = []
    for line in PAGES_FILE.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        pages.append(DocumentPage(row["document_id"], row["source"], row["page"],
                                   row["text"], {"chapter": row["chapter"],
                                                 "language": row["language"],
                                                 "attribution": row["attribution"]},
                                   row["char_count"]))
    if len(pages) < 30 or any(len(page.text) < 1500 for page in pages):
        raise ValueError("Corpus must contain at least 30 useful PDF pages (>=1,500 normalized chars each)")
    return pages


def chunk_stats(chunks: list, strategy: str) -> dict:
    sizes = [len(c.text) for c in chunks]
    return {"strategy": strategy, "chunk_count": len(chunks),
            "total_chars": sum(sizes), "mean_chars": statistics.mean(sizes),
            "median_chars": statistics.median(sizes),
            "p90_chars": sorted(sizes)[int(0.9 * (len(sizes) - 1))],
            "min_chars": min(sizes), "max_chars": max(sizes)}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    started_all = time.perf_counter()
    pages = read_pages()
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if len(questions) < 20 or sum(q["split"] == "dev" for q in questions) < 15 or sum(q["split"] == "test" for q in questions) < 5:
        raise ValueError("Benchmark requires >=20 questions and >=15 dev / >=5 test")
    for q in questions:
        if q["gold_source_id"] != pages[0].document_id:
            raise ValueError(f"Unknown gold source in {q['id']}")
        if not q.get("evidence_quote") or q["gold_page"] not in q.get("gold_pages", [q["gold_page"]]):
            raise ValueError(f"Missing or inconsistent gold evidence in {q['id']}")
        source_page = next((p for p in pages if p.page == q["gold_page"]), None)
        if not source_page or q["evidence_quote"].casefold() not in source_page.text.casefold():
            raise ValueError(f"Gold evidence was not found verbatim on source page for {q['id']} / p.{q['gold_page']}")
        for key, value in q.get("filter", {}).items():
            if not any(str(p.metadata.get(key)) == str(value) for p in pages):
                raise ValueError(f"Filter value {key}={value!r} does not exist in corpus metadata ({q['id']})")

    embedder = LocalFastEmbedder(MODEL)
    store = ChromaVectorStore(RESULTS / "chroma", embedder.dimensions)
    store.create_schema()
    strategies = {
        "A": {"description": "Fixed-size 500 characters, overlap 50; no metadata filter", "chunks": []},
        "B": {"description": "Sentence/paragraph-boundary chunks up to 800 characters; no metadata filter", "chunks": []},
        "C": {"description": "Same sentence/paragraph chunks as B; apply chapter filter only when supplied", "chunks": []},
    }
    strategies["A"]["chunks"] = [c for page in pages for c in fixed_size(page, 500, 50)]
    paragraph_chunks = [c for page in pages for c in by_paragraph(page, 800)]
    strategies["B"]["chunks"] = paragraph_chunks
    strategies["C"]["chunks"] = paragraph_chunks

    vector_cache: dict[str, list[float]] = {}
    stats, traces = [], []
    query_vectors = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    for strategy, details in strategies.items():
        chunks = details["chunks"]
        t0 = time.perf_counter()
        missing = [c for c in chunks if c.chunk_id not in vector_cache]
        if missing:
            new_vectors = embedder.embed_documents([c.text for c in missing])
            vector_cache.update({c.chunk_id: v for c, v in zip(missing, new_vectors)})
        vectors = [vector_cache[c.chunk_id] for c in chunks]
        embedding_elapsed = time.perf_counter() - t0
        t1 = time.perf_counter()
        store.upsert(strategy, chunks, vectors)
        ingest_elapsed = time.perf_counter() - t1
        current = chunk_stats(chunks, strategy)
        current.update({"description": details["description"],
                        "embedding_seconds_first_seen": embedding_elapsed,
                        "store_upsert_seconds": ingest_elapsed,
                        "model": MODEL, "dimensions": embedder.dimensions,
                        "metric": "cosine", "vector_store": "Chroma PersistentClient 1.3.5"})
        stats.append(current)
        for q in questions:
            filters = q.get("filter", {}) if strategy == "C" else {}
            hits = store.search(strategy, query_vectors[q["id"]], top_k=3, filters=filters)
            traces.append({"strategy": strategy, "split": q["split"], "question_id": q["id"],
                           "question": q["question"], "query_filter": filters,
                           "gold_source_id": q["gold_source_id"], "gold_page": q["gold_page"],
                           "evidence_quote": q["evidence_quote"], "expected_answer": q["expected_answer"],
                           "hits": hits, "evaluation": evaluate_query(q, hits)})
        print(f"Strategy {strategy}: {len(chunks)} chunks, ingest {ingest_elapsed:.2f}s")

    summary = summarize(traces)
    run_info = {"run_at_utc": datetime.now(timezone.utc).isoformat(),
                "python": sys.version.split()[0], "pages": len(pages), "questions": len(questions),
                "model": MODEL, "dimensions": DIMENSIONS,
                "vector_store": "Chroma PersistentClient 1.3.5", "metric": "cosine",
                "search_mode": "Chroma HNSW approximate nearest-neighbor index; persistent local storage",
                "total_seconds": time.perf_counter() - started_all,
                "api_cost_usd": 0, "notes": "Local ONNX embedding inference; first run downloads the model."}
    write_json(RESULTS / "summary.json", {"run": run_info, "retrieval": summary, "strategies": stats})
    (RESULTS / "retrieval_traces.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8")
    snapshots = []
    for strategy, details in strategies.items():
        for c in details["chunks"]:
            snapshots.append({"strategy": strategy, "chunk_id": c.chunk_id,
                              "document_id": c.document_id, "source": c.source, "page": c.page,
                              "char_start": c.metadata["char_start"], "char_end": c.metadata["char_end"],
                              "chapter": c.metadata["chapter"], "text": c.text,
                              "attribution": c.metadata["attribution"]})
    (RESULTS / "chunk_snapshots.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in snapshots) + "\n", encoding="utf-8")
    with (RESULTS / "chunk_stats.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(stats[0]))
        writer.writeheader()
        writer.writerows(stats)
    print(json.dumps({"retrieval": summary, "run": run_info}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
