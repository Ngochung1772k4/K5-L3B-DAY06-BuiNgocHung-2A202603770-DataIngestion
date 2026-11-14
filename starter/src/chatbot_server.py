"""Run a local, retrieval-only chatbot with page-level source citations."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .embeddings import LocalFastEmbedder
from .store import ChromaVectorStore


ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "starter"
WEB_DIR = STARTER / "chatbot"
STORE_PATH = STARTER / "results" / "chroma"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIMENSIONS = 384
HOST = "127.0.0.1"
PORT = 8000
MAX_REQUEST_BYTES = 8_192


def build_handler(store: ChromaVectorStore, embedder: LocalFastEmbedder):
    class ChatHandler(BaseHTTPRequestHandler):
        server_version = "LocalSourceChat/1.0"

        def _send_json(self, status: int, value: dict) -> None:
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlparse(self.path).path
            if path == "/api/health":
                try:
                    collection = store.client.get_collection("day6_c")
                    count = collection.count()
                except Exception:
                    self._send_json(503, {"status": "not_ready", "message":
                                          "Chưa có index C. Hãy chạy `python -m src.run` trong starter trước."})
                    return
                self._send_json(200, {"status": "ready", "collection": "day6_c",
                                      "chunks": count, "model": MODEL})
                return
            if path != "/":
                self._send_json(404, {"error": "Không tìm thấy đường dẫn."})
                return
            page = WEB_DIR / "index.html"
            try:
                payload = page.read_bytes()
            except OSError:
                self._send_json(500, {"error": "Thiếu starter/chatbot/index.html."})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if urlparse(self.path).path != "/api/chat":
                self._send_json(404, {"error": "Không tìm thấy đường dẫn."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "Content-Length không hợp lệ."})
                return
            if length <= 0 or length > MAX_REQUEST_BYTES:
                self._send_json(413, {"error": "Câu hỏi trống hoặc vượt quá giới hạn 8 KB."})
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "Nội dung yêu cầu phải là JSON UTF-8 hợp lệ."})
                return
            if not isinstance(body, dict):
                self._send_json(400, {"error": "Nội dung yêu cầu phải là một JSON object."})
                return

            question = str(body.get("question", "")).strip()
            chapter = body.get("chapter")
            if not question:
                self._send_json(400, {"error": "Bạn hãy nhập câu hỏi."})
                return
            if len(question) > 1_000:
                self._send_json(400, {"error": "Câu hỏi tối đa 1.000 ký tự."})
                return
            if chapter not in (None, "1", "2"):
                self._send_json(400, {"error": "Chương chỉ nhận giá trị 1, 2 hoặc tất cả."})
                return

            try:
                vector = embedder.embed_query(question)
                filters = {"chapter": chapter} if chapter else None
                hits = store.search("C", vector, top_k=3, filters=filters)
            except Exception as exc:
                self._send_json(503, {"error": f"Không truy xuất được index Chroma: {exc}"})
                return

            results = []
            for rank, hit in enumerate(hits, start=1):
                metadata = hit["metadata"]
                page_number = int(metadata["page"])
                results.append({
                    "rank": rank,
                    "text": hit["text"],
                    "page": page_number,
                    "chapter": str(metadata.get("chapter", "")),
                    "similarity": round(float(hit["score"]), 4),
                    "source": metadata["source"],
                    "source_title": "Introduction to Sociology 2e — OpenStax",
                    "source_url": f"{metadata['source']}#page={page_number}",
                })
            self._send_json(200, {
                "message": (f"Tìm thấy {len(results)} đoạn liên quan trong tài liệu. "
                            "Mình trích nguyên văn để bạn kiểm tra; đây không phải câu trả lời được AI suy diễn."),
                "strategy": "C — sentence-boundary chunks, cosine retrieval, chapter filter when selected",
                "chapter_filter": chapter,
                "results": results,
            })

        def log_message(self, fmt: str, *args) -> None:
            # Keep the local demo terminal concise while retaining request errors.
            if args and str(args[1]).startswith("5"):
                super().log_message(fmt, *args)

    return ChatHandler


def main() -> None:
    embedder = LocalFastEmbedder(MODEL)
    store = ChromaVectorStore(STORE_PATH, DIMENSIONS)
    try:
        collection = store.client.get_collection("day6_c")
    except Exception as exc:
        raise SystemExit("Chưa có Chroma index C. Chạy `python -m src.run` trong starter trước.") from exc
    if collection.count() == 0:
        raise SystemExit("Collection C đang rỗng. Chạy `python -m src.run` trong starter trước.")

    server = ThreadingHTTPServer((HOST, PORT), build_handler(store, embedder))
    print(f"Chatbot local sẵn sàng: http://{HOST}:{PORT}")
    print(f"Nguồn: {collection.count()} chunks trong Chroma / day6_c; Ctrl+C để dừng.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng chatbot.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
