# Sửa ranh giới lời thoại cho tài liệu video

> **For agentic workers:** dùng kiểm thử trước khi sửa logic và kiểm chứng lại trên dữ liệu thật.

**Mục tiêu:** Không biến hai nửa của một câu ASR thành hai fact/đoạn tài liệu; không trộn lời của các video trong chunk RAG.

**Phạm vi cập nhật theo user:** Làm lại từ đầu, chỉ giữ raw. Mặc định raw là `data/raw/`; đã hỏi liệu có giữ thêm ASR gốc trong `data/analysis/transcripts/`, đang chờ trả lời. Source code/config/model là công cụ chạy lại, không phải dữ liệu phân tích. Trước khi xóa phải xác nhận ranh giới raw và khả năng chạy lại từ raw.

**Hiện trạng đã đọc:** `master` sạch; 223 `source.md`, 16 `article.json`, 16 `facts.jsonl`. Ví dụ `5pSF6K2g-KA` tách giữa “ok hơn là / mình thì”. Mô phỏng source hiện tại: 2.726 chunk, 208 chunk chứa hơn một video. Đây là kiểm tra dữ liệu/source, chưa phải nghe audio.

**Quyết định:** Tạo đơn vị lời thoại theo dấu kết câu trên chuỗi các segment cùng video, giữ timestamp từ segment đầu/cuối. Không tự tách đoạn thiếu dấu câu vì không có bằng chứng về ranh giới ý; đánh dấu đoạn dài để người duyệt. Theo chỉ dẫn mới, bỏ cả 16 bài biên tập cũ trong đợt reset dữ liệu, sau đó tái tạo bài từ nguồn mới khi pipeline và chất lượng được chứng minh.

## Kế hoạch / checkpoint

- [x] Thêm test tái hiện câu qua nhiều segment, giữ toàn bộ text và nguồn/timestamp trong fact và `source.md`; đã thấy test đỏ đúng lỗi cũ.
- [x] Sửa helper ghép lời và caller của fact/source; test tập trung xanh.
- [x] Sửa chunk RAG và test ranh giới câu/video; agent phụ trách phần đầu, agent chính đã đọc diff, dùng chung helper và chạy 17 test guardrails xanh.
- [x] Bổ sung lệnh `cnga restore-catalog` lấy snapshot mới nhất từ `data/raw/catalog` khi `data/analysis/state` đã xóa; test red-green.
- [x] Kiểm kê: `data/analysis` gồm frames 215 MB, OCR 205 MB, transcripts 37 MB, transcript_quality 142 MB, knowledge 11 MB, index 38 MB, state 1.3 MB và chunks 9.2 MB; `docs` 24 file (~112 KB). `data/raw` có 225 thư mục video, 226 audio (~4.02 GB), 224 video (~12.88 GB), 2 catalog đầy đủ mỗi bản 225 video. Không backup bản phân tích cũ theo chỉ dẫn user.
- [ ] Reset dữ liệu phân tích rồi tái tạo từ raw; kiểm tra số lượng, nội dung ví dụ, tính toàn vẹn và các đoạn còn cần nghe lại.
- [ ] Chạy test toàn repo, review diff, commit từng bước đã kiểm chứng. Push branch làm việc khi remote cho phép; không ghi đè nhánh khác.

**Chưa làm:** chưa xóa/ghi đè dữ liệu thật, chưa chạy lại toàn bộ ASR/OCR. Đã `uv sync --extra asr --extra ocr --extra youtube --extra dev`; bổ sung runtime CUDA 12/cuDNN 9 vào extra ASR vì smoke ban đầu báo thiếu `cublas64_12.dll`. Smoke mới dùng `configure_cuda_runtime()` + large-v3 GPU trên 15 giây audio raw: 4 segment, exit 0; không ghi file. `uv run --offline python -m unittest discover -s tests`: 50/50 xanh. Lượt review độc lập phát hiện snapshot catalog giới hạn và câu có dấu nháy/ngoặc; đã thêm test đỏ rồi sửa xanh. Chưa chứng minh chất lượng transcript sau ASR toàn bộ video.
