# Báo cáo cá nhân — Day 6 Data Ingestion

**Học viên:** Bùi Ngọc Hùng · **MSSV:** 2A202603770 · **Lớp:** L3B  
**Chạy cuối:** 2026-11-14 09:38 ICT · **Repo:** [GitHub repo](https://github.com/Ngochung1772k4/K5-L3B-DAY06-BuiNgocHung-2A202603770-DataIngestion) · **Commit:** xem HEAD của nhánh hiện tại.

## Dữ liệu và pipeline

- **Corpus:** *Introduction to Sociology 2e*, Paul Peter Urone và Roger Hinrichs, OpenStax/Rice University. Tài liệu gốc có giấy phép **CC BY 4.0**; PDF nguồn và từng bản ghi trang/chunk giữ thông tin attribution. Nguồn: [trang sách OpenStax](https://openstax.org/details/books/introduction-sociology-2e), [PDF chính thức](https://assets.openstax.org/oscms-prodcms/media/documents/IntroductionToSociology2e-OP_tbTLqMj.pdf). Manifest: `data/manifest.json`.
- **Phạm vi:** 30 trang PDF vật lý: 14, 15, 17–28, 38–53; gồm Chương 1 (14 trang) và Chương 2 (16 trang). Trang bìa, front matter, bài tập và tài liệu tham khảo không tính. Đã trích 117.404 ký tự chuẩn hóa; trang ít ký tự nhất 2.149. Dữ liệu đã trích ở `starter/data/pages.jsonl`.
- **Đọc/chuẩn hóa:** pypdf 6.21.4; trích text, không cần OCR; Unicode NFKC, sửa nối từ bị ngắt dòng, chuẩn hóa khoảng trắng và giữ ranh giới câu/đoạn suy ra từ PDF. `starter/results/ingestion_errors.json` ghi không có trang rỗng/ngắn. `starter/results/extraction_audit.json` ghi không có U+FFFD; dấu nháy cong được giữ dưới dạng Unicode.
- **Embedding:** FastEmbed 0.7.3, model thật `sentence-transformers/all-MiniLM-L6-v2` (384 chiều, ONNX CPU, tiếng Anh; model Apache-2.0). Query/document dùng cùng model, không cần API key. Chi phí API: **$0**.
- **Vector store:** Chroma 1.3.5 PersistentClient tại `starter/results/chroma/`, cosine distance, HNSW approximate search. Metadata mỗi chunk: `document_id`, `source`, `page`, `chapter`, `language`, vị trí/ký tự chunk và attribution. `chapter` lấy từ ranh giới chương trong PDF; không suy đoán.
- **Nạp lại:** ID chunk ổn định theo document/page/configuration/offset/text. Mỗi lần chạy thay snapshot của collection chiến lược trước khi ghi dữ liệu mới; không giữ chunk cũ hoặc nhân đôi. Chroma database bị ignore khỏi git và có thể tái tạo bằng lệnh chạy.

## Cấu hình và benchmark

- **A:** cửa sổ 500 ký tự, overlap 50, không lọc.
- **B:** gom các câu/đoạn liền kề theo ranh giới câu, tối đa 800 ký tự, không lọc. PDF extraction không giữ được blank paragraph markers nhất quán, nên ranh giới câu là fallback cấu trúc; câu quá dài được tách tại khoảng trắng gần giới hạn.
- **C:** cùng chunk với B, chỉ thêm điều kiện lọc bằng `chapter` khi câu hỏi cung cấp phạm vi. B–C chỉ thay lọc.
- **Gold:** `benchmark/questions.json`; 25 câu, **20 dev / 5 test**, 8 câu có filter (3 câu test). Evidence được kiểm tra nguyên văn trên đúng trang sau chuẩn hóa. Filter xuất phát từ phạm vi nêu trong câu hỏi và giá trị tồn tại trong corpus.
- **Split:** lần chạy thăm dò ban đầu đã xem q16–q20. Để không coi chúng là holdout, chuyển chúng sang dev, tạo q21–q25 làm test từ các trang gold chưa dùng rồi cố định pipeline trước lần chạy cuối. Chi tiết trong `benchmark/SPLIT_CHANGELOG.md`. Bộ test cuối chỉ có 5 câu và đều lấy từ Chương 2; kết luận không đại diện cho mọi chủ đề.
- **Chọn cấu hình:** so sánh trên dev, ưu tiên Evidence Hit@3, sau đó coherence/grounding, số chunk và khả năng lọc/truy vết. Quy tắc này được ghi khi phân tích kết quả nhưng chưa được preregister trước khi xem lần chạy cuối; không điều chỉnh code sau lần test cuối. Vì vậy test là so sánh mô tả có giới hạn, không phải đánh giá độc lập mạnh.

## Kết quả retrieval

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunks | Upsert store (s) | Chi phí API |
|---|---|---:|---:|---:|---:|---:|
| A | Dev | 13/20 | 17/20 | 277 | 0,63 | $0 |
| A | Test | 3/5 | 3/5 | 277 | 0,63 | $0 |
| B | Dev | 11/20 | 17/20 | 176 | 0,40 | $0 |
| B | Test | 3/5 | 3/5 | 176 | 0,40 | $0 |
| C | Dev | 11/20 | 17/20 | 176 | 0,30 | $0 |
| C | Test | 3/5 | 3/5 | 176 | 0,30 | $0 |

Lần chạy cuối mất 10,13 giây khi model đã có cache; lần chạy đầu mất khoảng 63 giây, gồm tải model. B/C dùng lại vector đã tính cho cùng chunk nên thời gian embedding của C gần 0; thời gian upsert được đo riêng cho mỗi collection. Thống kê đầy đủ ở `starter/results/summary.json` và `chunk_stats.csv`; 75 truy vấn top-3 ở `retrieval_traces.jsonl`. B có mục tiêu 800 ký tự; độ dài quan sát tối đa là 805 do dấu phân cách câu được thêm khi ghép đơn vị.

## Audit thủ công có hỗ trợ AI

Các nhãn dưới đây do Codex rà từng chunk/evidence theo rubric, đối chiếu với trang nguồn và được đánh dấu rõ là **chờ học viên xác nhận** trong CSV. Chưa có xác nhận độc lập của học viên; không xem đây là nhãn của người dùng.

| Strategy | Coherence /2 (n=10) | Metadata đúng/đủ (n=15 test hits) | Filter tuân thủ dev | Filter tuân thủ test | Grounding 0/1/2 (n=5), trung bình /2 |
|---|---:|---:|---:|---:|---|
| A | 1,3 | 15/15 | 4/5 | 3/3 | 0:1, 1:1, 2:3 · 1,4 |
| B | 1,8 | 15/15 | 4/5 | 3/3 | 0:1, 1:1, 2:3 · 1,4 |
| C | 1,8 | 15/15 | 5/5 | 3/3 | 0:1, 1:1, 2:3 · 1,4 |

Metadata được so từng top-3 record với page record/manifest: tổng **45/45** record có `document_id`, `source`, `page`, `chapter` đúng. Trong test, A/B có 3/3 truy vấn filter tình cờ trả về toàn kết quả Chương 2; chỉ C thực thi filter. Trên dev, C tăng tuân thủ 4/5 lên 5/5 và loại kết quả khác chương ở q16. Điều này cho thấy filter có ích cho bảo đảm phạm vi; test hiện tại chưa đo được khác biệt vì mọi câu filter test đều yêu cầu Chương 2.

Mẫu coherence cố định theo 10 page ID đầu đã sắp xếp (14, 15, 17–24); chọn câu đầu tiên ở khoảng một phần ba đầu trang rồi chấm chunk chứa vị trí đó. B/C cải thiện rõ ở các trường hợp A cắt câu giữa chừng; page 15/19 vẫn mở bằng mảnh câu do nội dung PDF nối qua trang. Mẫu được chọn theo thứ tự trang, không theo điểm retrieval; tuy nhiên việc rà chunker trong vòng thăm dò làm mẫu này không phải audit mù hoàn toàn.

## Phân tích và kết luận

- **A–B:** Evidence Hit@3 bằng nhau (17/20 dev; 3/5 test), nhưng B giảm Hit@1 dev từ 13/20 xuống 11/20. B giảm số chunk 277→176 (−36,5%) và tăng coherence 1,3→1,8. Chunk lớn, giữ nguyên câu có vẻ phù hợp khi ưu tiên ngữ cảnh; A giữ nguyên một số bằng chứng cục bộ ở rank đầu tốt hơn.
- **B–C:** chunking, số chunk, Hit@1/Hit@3 và grounding giống nhau. C thêm lọc chương: tuân thủ dev 5/5 so với 4/5 của A/B. Trên test, tuân thủ 3/3 ở cả ba vì tất cả câu filter đều thuộc chương 2; không thể suy ra test chứng minh filter cải thiện retrieval.
- **Lỗi q22:** hỏi ba loại field research ở p.46; cả ba cấu hình lấy top-3 từ p.44 về field research nói chung, không lấy danh sách participant observation / ethnography / case study. Grounding 0/2.
- **Lỗi q23:** hỏi lợi thế chính của covert participant observation ở p.47; top-3 liên quan đến participant observation nhưng bỏ mất câu nêu lợi thế “authentic, natural behaviors”. Grounding 1/2.
- **Lựa chọn:** C là cấu hình cân bằng theo tiêu chí trên: Hit@3 dev ngang A, coherence ngang B, ít chunk hơn A và thực thi filter. Đánh đổi: Hit@1 dev thấp hơn A 2 câu; filter không cải thiện Hit@3 trên tập nhỏ này.
- **Giới hạn:** chỉ 30 trang của một sách tiếng Anh; test 5 câu đều ở Chương 2; đánh giá approximate HNSW; embedding model tiếng Anh; nhãn coherence/grounding do AI hỗ trợ và cần học viên xác nhận; lần thay test và tiêu chí chọn chưa preregister hoàn hảo. Không tuyên bố cấu hình C tốt nhất ngoài corpus này.
- **Mở rộng:** kiểm tra thủ công nhãn audit, cải thiện trích xuất Unicode, tạo test cân bằng chương/loại câu lớn hơn và giữ nguyên test mới khi tinh chỉnh.

## Tái lập

Từ PowerShell tại `starter/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/prepare_corpus.py
.\.venv\Scripts\python.exe -m src.run
.\.venv\Scripts\python.exe scripts/build_audit_packets.py
```

Không cần Docker hoặc API key. Model tải ở lần chạy đầu. Hệ thống dùng cùng corpus, model, vector store và bộ câu hỏi cho A/B/C. Công cụ AI được dùng để viết/kiểm tra code và hỗ trợ audit; evidence benchmark được xác minh với page text, không dùng LLM để chấm câu trả lời.
