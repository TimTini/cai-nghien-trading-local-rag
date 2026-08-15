# Cai Nghien Trading Local RAG

Dự án local thu thập transcript kênh YouTube
`https://www.youtube.com/@cainghientrading`
rồi **viết lại kiến thức thành sách theo chủ đề**.

**Cách đọc:** `data/analysis/knowledge/playbook/00-index.md` hoặc site tĩnh `docs/index.html`.

Sách public **đã lọc theo Nghị quyết 05/2025/NQ-CP**: không hướng dẫn bot / đòn bẩy / sàn nước ngoài / tín hiệu mua bán. Không phải tư vấn pháp lý.

```powershell
uv run cnga ask "Quỹ khẩn cấp trước khi đầu tư?"
uv run cnga ask "Sàn crypto Việt Nam cấp phép thế nào?"
```

## GitHub Pages (public)

Site tĩnh trong `docs/`: mục lục, từng chương, ô hỏi (cùng kiểu `cnga ask`). Không chạy Python/ASR trên Pages.

```powershell
uv run cnga export-pages
```

Rồi commit thư mục `docs/`, push, bật Pages:

1. GitHub repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch `main`, folder `/docs` → Save

URL dạng `https://<user>.github.io/cai-nghien-trading-local-rag/`

`data/` vẫn gitignore (transcript/model). Chỉ sách trong `docs/` là public.

## Nguyên tắc

- Mọi dữ liệu nằm trong thư mục dự án: `data/`, `models/`, `logs/`, `.cache/`.
- Không lưu đường dẫn tuyệt đối vào dữ liệu phân tích.
- Tách dữ liệu gốc (`data/raw`) và dữ liệu phân tích (`data/analysis`).
- **Deliverable chính:** `data/analysis/knowledge/playbook/` — sách theo chủ đề.
- Bài từng video: `data/analysis/knowledge/videos/{video_id}/article.md`.
- Transcript: raw → ai_cleaned → approved (review UI).

## Cấu trúc

```text
config/project.toml
src/cai_nghien_assistant/
tests/
data/raw/
data/analysis/
  knowledge/
    playbook/           # sách đọc / hỏi
    videos/{id}/source.md
    videos/{id}/article.md
models/
logs/
.cache/
```

## Cài đặt bằng uv

```powershell
uv sync --extra youtube --extra asr --extra ocr --extra dev
```

## Luồng chính

```powershell
uv run cnga init
uv run cnga doctor

uv run cnga collect --limit 20 --fetch-sidecars
uv run cnga fetch-audio --limit 5 --content-type regular
uv run cnga asr --limit 5 --content-type regular --model-size large-v3 --device cuda

uv run cnga normalize-transcripts
uv run cnga clean-transcripts --limit 10
uv run cnga review-ui --port 8765

uv run cnga assemble-playbook-source
uv run cnga ask "Stop loss / ký quỹ bot thì sao?"
```

Video mới sau khi đã duyệt lời:

```powershell
uv run cnga compile-playbook
# Máy local tự viết bài (chất lượng tùy model):
uv run cnga compile-playbook --endpoint http://127.0.0.1:8080/completion
```

`compile-playbook` không xóa chương đã viết; chỉ gắn thêm mục cập nhật.

## Chạy theo lớp

| Lớp | Lệnh | Việc làm |
|-----|------|----------|
| **A** | `scripts/run_layer_a.py` | audio, ASR, frames, OCR |
| **B** | `scripts/run_layer_b.py` | normalize + conservative-refine |
| **D** | `scripts/run_layer_d.py` | extract-knowledge (cũ, cắt câu — không dùng để trả lời) |
| **C** | `scripts/run_layer_c.py` | *(tùy chọn)* build-index FTS |

PowerShell: `.\scripts\run_layer_a.ps1`, `run_layer_b.ps1`, `run_layer_d.ps1`.

## Transcript quality

Chất lượng sách phụ thuộc transcript đã clean/approve.

## Tùy chọn (không dùng để trả lời)

| Lệnh | Ghi chú |
|------|---------|
| `cnga extract-knowledge` | Cắt câu thành fact — giữ để đối chiếu, không phải sách |
| `cnga build-index` | FTS search local |
| `cnga chat` | Chat local — deprecated |
| `cnga analyze-local` | LLM batch extract — tùy model |

## Kiểm thử

```powershell
uv run python -m unittest discover -s tests
```

## Lưu ý pháp lý / vận hành

Pipeline chỉ tải metadata/subtitle mặc định. Audio/video chỉ khi hợp pháp và cần ASR/OCR. Không push dữ liệu, model, cache hoặc log.
