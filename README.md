# Cai Nghien Trading Local RAG

Dự án local để thu thập, phân tích và chat dựa trên dữ liệu của kênh YouTube:
`https://www.youtube.com/@cainghientrading`.

Mục tiêu: trợ lý trả lời bằng tiếng Việt, có thể dùng phong cách diễn đạt của kênh, nhưng **chỉ dùng kiến thức có bằng chứng trong dữ liệu đã phân tích từ kênh**. Nếu không có bằng chứng đủ rõ, trợ lý trả lời:

> Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này.

## Nguyên tắc thiết kế

- Mọi dữ liệu do dự án tạo ra nằm trong thư mục dự án: `data/`, `models/`, `logs/`, `.cache/`.
- Không lưu đường dẫn tuyệt đối vào dữ liệu phân tích; chỉ lưu đường dẫn tương đối theo project root.
- Tách dữ liệu gốc bất biến (`data/raw`) và dữ liệu phân tích tái tạo được (`data/analysis`).
- Pipeline chạy lại được, có state/cache, bỏ qua phần đã xử lý thành công.
- Chatbot luôn truy hồi bằng chứng trước khi trả lời.
- Lớp `content` là bằng chứng kiến thức; lớp `style` chỉ ảnh hưởng cách diễn đạt, không được dùng làm bằng chứng sự thật.
- Phiên bản MVP dùng SQLite FTS cục bộ để dễ kiểm chứng. Có thể bật Chroma/BGE-M3 sau, nhưng vẫn phải trỏ toàn bộ model/cache/index vào thư mục dự án.

## Cấu trúc

```text
config/project.toml              # cấu hình tương đối, portable
src/cai_nghien_assistant/        # package pipeline
tests/                           # unit test guardrail
data/raw/                        # dữ liệu gốc, write-once
data/analysis/                   # transcript chuẩn hóa, chunk, index, cache
models/                          # model local GGUF / embedding / OCR
logs/                            # log chạy pipeline
.cache/                          # cache thư viện được ép nằm trong project
```

## Cài đặt bằng uv

Chạy từ thư mục project:

```powershell
uv sync --extra youtube --extra asr --extra ocr --extra dev
```

`uv.toml` ép `uv` dùng cache `.cache/uv` và copy package vào `.venv` để project portable hơn.

Nếu cần tác vụ nặng sau này:

```powershell
uv sync --extra youtube --extra ml --extra asr --extra ocr --extra dev
```

## Luồng MVP

```powershell
# Tạo cây thư mục local và ép cache thư viện vào project
uv run cnga init
uv run cnga doctor

# Thu catalog metadata, sort từ video cũ nhất tới mới nhất
uv run cnga collect --limit 20 --fetch-sidecars

# Tải media khi cần ASR/OCR local (oldest-first)
uv run cnga fetch-audio --limit 5 --content-type regular
uv run cnga fetch-video-light --limit 5 --content-type regular

# Subtitle chất lượng cao hơn: chạy Whisper large-v3 local trên audio
uv run cnga asr --limit 5 --content-type regular --model-size large-v3 --device cuda --compute-type float16

# Frame/OCR: trích frame thưa rồi chạy PaddleOCR project-local
uv run cnga extract-frames --limit 5 --content-type regular
uv run cnga ocr-frames --limit 5 --content-type regular

# Chuẩn hóa subtitle có sẵn từ YouTube/yt-dlp thành transcript có provenance
uv run cnga normalize-transcripts

# Build index local từ transcript/OCR/analysis đã có (SQLite FTS MVP)
uv run cnga build-index

# Optional: build Chroma persistent index trong data/analysis/index/chroma
uv run cnga build-chroma

# Chat có bằng chứng
uv run cnga chat "Kênh này giải thích quản trị rủi ro như thế nào?"
```

## Chạy full pipeline có log/resume

Runner dưới đây chạy từng video theo thứ tự cũ nhất, ghi log/state trong project
và tự bỏ qua artifact đã có:

```powershell
uv run python scripts/run_full_pipeline.py --root H:\test --content-type regular --status
uv run python scripts/run_full_pipeline.py --root H:\test --content-type regular
```

File chính:

- State resume: `data/analysis/state/full_pipeline_regular.json`
- Log mỗi lần chạy: `logs/full-pipeline/*.log`

Nếu bị dừng giữa chừng, chạy lại đúng lệnh trên. Runner sẽ kiểm tra artifact
`audio`, `video-light`, `asr`, `frames`, `ocr` trước khi chạy stage tiếp theo.

## Model local

Không dùng cloud mặc định.

- Chat: đặt GGUF Qwen3 nhỏ trong `models/chat/`, chạy `llama.cpp` server local, rồi dùng `cnga analyze-local --endpoint http://127.0.0.1:8080/completion`.
- Vision: đặt Qwen3-VL GGUF trong `models/vision/`; MVP chỉ trích frame/OCR trước, chưa gọi vision tràn lan.
- Embedding: `cnga build-chroma` dùng hash embedding local không tải model để tránh cache ngoài project. Khi chuyển sang BGE-M3/sentence-transformers, cache phải nằm trong `.cache/huggingface` và model trong `models/embeddings`.
- Ollama không được bật mặc định. Chỉ dùng nếu `OLLAMA_MODELS` đã trỏ vào `models/ollama` và `cnga doctor` xác nhận không phát sinh file ngoài project.

## Kiểm thử

```powershell
uv run python -m unittest discover -s tests
```

Các test chính:

- không ghi đè dữ liệu gốc write-once;
- cache/env path nằm trong project;
- build index chạy lại không tạo trùng;
- chatbot từ chối khi không có content evidence;
- style evidence không được dùng làm bằng chứng factual;
- evidence mới hơn được ưu tiên khi điểm truy hồi ngang nhau.

## Lưu ý pháp lý / vận hành

Pipeline chỉ tải metadata/subtitle mặc định. Audio/video chỉ nên tải khi hợp pháp, cần thiết cho ASR/OCR, và vẫn lưu trong `data/raw` với hash/provenance. Không push dữ liệu, model, cache hoặc log.
