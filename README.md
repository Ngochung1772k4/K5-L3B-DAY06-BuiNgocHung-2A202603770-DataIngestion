# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Repo này đã hiện thực pipeline và benchmark trong `starter/src/`. Bài dùng Chroma PersistentClient + FastEmbed local; Docker/PostgreSQL + pgvector trong [starter/README.md](starter/README.md) là lựa chọn khác, không cần để chạy kết quả hiện tại.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách tối thiểu **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup và cách chạy pipeline hiện tại; tùy chọn PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Lab không bắt buộc xây chatbot.

## Bản triển khai trong repo này

Pipeline đang dùng `Introduction to Sociology 2e` của OpenStax (CC BY 4.0), trích 30 trang nội dung thuộc Chương 1–2. Chi tiết giấy phép, URL, trang vật lý, số ký tự và quy tắc tính trang nằm ở [data/manifest.json](data/manifest.json). Benchmark hiện có 25 câu tiếng Anh (20 dev / 5 test) với evidence đã xác minh ở [benchmark/questions.json](benchmark/questions.json).

Để cài và chạy trên Windows PowerShell:

```powershell
cd starter
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/prepare_corpus.py
.\.venv\Scripts\python.exe -m src.run
```

PDF nguồn hiện đã nằm tại `data/OpenStax_Introduction_to_Sociology_2e.download.pdf`; nếu cần tải lại từ PowerShell ở thư mục `starter/`, chạy:

```powershell
curl.exe -L -o ..\data\OpenStax_Introduction_to_Sociology_2e.download.pdf "https://assets.openstax.org/oscms-prodcms/media/documents/IntroductionToSociology2e-OP_tbTLqMj.pdf"
```

Pipeline dùng FastEmbed/ONNX local (`sentence-transformers/all-MiniLM-L6-v2`, 384 chiều) và Chroma PersistentClient với cosine search, nên không cần API key hay Docker daemon. Lần đầu sẽ tải model embedding. Kết quả thực chạy được lưu trong `starter/results/`; báo cáo cá nhân ở [report/individual/2A202603770_BuiNgocHung.md](report/individual/2A202603770_BuiNgocHung.md).

## Chatbot demo

Repo có chatbot local để trình bày truy xuất trên corpus. Khởi chạy index trước, sau đó mở server tại `http://127.0.0.1:8000` theo hướng dẫn trong [starter/README.md](starter/README.md). Bot hiện trích nguyên văn tối đa ba đoạn kèm trang PDF và liên kết nguồn; nó không sinh câu trả lời bằng LLM nên nội dung phản hồi luôn minh bạch để người demo tự giải thích.
