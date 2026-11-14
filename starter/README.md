# Pipeline đã hiện thực · Chroma + FastEmbed

Repo này hiện dùng Chroma PersistentClient làm vector store cục bộ; Docker/PostgreSQL + pgvector trong starter cũ vẫn là lựa chọn khác nhưng không cần để chạy pipeline này. Chroma lưu bền vững trên đĩa, tìm cosine gần đúng và hỗ trợ lọc metadata.

## Cấu trúc

```text
starter/
├── data/pages.jsonl       # 30 trang đã trích, chuẩn hóa và có attribution
├── scripts/prepare_corpus.py
├── src/                   # ingestion, chunking, embeddings, Chroma và evaluation
└── results/               # summary, trace top-3 và thống kê chunk
```

## 1. Cài đặt và dựng corpus

Cần Python **3.11–3.14** và mạng cho lần cài package/tải model đầu tiên. Chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
python scripts/prepare_corpus.py
```

PDF nguồn được ghi tại manifest root. Script chỉ tính các PDF page IDs được chọn; kiểm tra đủ 30 trang và ghi manifest `data/manifest.json`.

## 2. Embedding và vector store

Embedding dùng FastEmbed 0.7.3 với `sentence-transformers/all-MiniLM-L6-v2` (384 chiều, Apache-2.0, tiếng Anh, ONNX CPU). Không gửi tài liệu ra API. Chroma 1.3.5 lưu trong `results/chroma/`, metric cosine. Model và store được giữ nguyên giữa A/B/C. Model cache nằm ngoài repo trên máy người chạy.

## 3. Chạy pipeline và benchmark

1. A: fixed-size 500 ký tự, overlap 50, không filter.
2. B: ghép câu/đoạn theo ranh giới cấu trúc, tối đa 800 ký tự, không filter.
3. C: đúng chunk B, thêm filter `chapter` khi câu hỏi cung cấp phạm vi.
4. Bộ câu hỏi cố định trước lần chạy cuối ở `benchmark/questions.json` (20 dev / 5 test; xem `SPLIT_CHANGELOG.md` về lần thay test sau khi tune).
5. Chạy `python -m src.run`; mỗi lần chạy thay snapshot theo strategy, không nhân đôi chunk cũ.

Trace đầy đủ, summary, thời gian, số chunk và metric nằm dưới `results/`. Thư mục Chroma bị ignore khỏi git; chạy lại lệnh trên để tái tạo.

Không có API key. Không dùng số ví dụ làm số đo; benchmark và kết quả báo cáo lấy từ artifacts thực tế.
