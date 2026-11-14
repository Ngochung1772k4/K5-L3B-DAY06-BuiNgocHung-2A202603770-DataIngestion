"""Read-only dependency and Chroma persistence setup check."""
from importlib.metadata import version
from pathlib import Path

import chromadb
from fastembed import TextEmbedding

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[1] / "results"

for package in ("chromadb", "fastembed", "pypdf"):
    print(f"{package}: {version(package)}")

client = chromadb.PersistentClient(path=str(RESULTS / "chroma"))
print(f"Chroma persistent path: {RESULTS / 'chroma'}")
print(f"Collections available: {[c.name for c in client.list_collections()]}")
model = "sentence-transformers/all-MiniLM-L6-v2"
supported = {m["model"]: m for m in TextEmbedding.list_supported_models()}
if model not in supported or supported[model]["dim"] != 384:
    raise RuntimeError("Pinned FastEmbed model or expected 384 dimensions is unavailable")
print(f"Embedding model available: {model} ({supported[model]['dim']} dimensions)")
print("Setup OK. Run scripts/prepare_corpus.py, then python -m src.run.")
