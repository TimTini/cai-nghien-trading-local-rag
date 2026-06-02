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

## Cài đặt đề xuất

Chạy từ thư mục project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

Nếu cần thu thập YouTube:

```powershell
python -m pip install yt-dlp youtube-transcript-api
```

Nếu cần tác vụ nặng sau này:

```powershell
python -m pip install -e ".[ml]"
```

## Luồng MVP

```powershell
# Tạo cây thư mục local và ép cache thư viện vào project
cnga init
cnga doctor

# Thu catalog metadata, sort từ video cũ nhất tới mới nhất
cnga collect --limit 20 --fetch-sidecars

# Chuẩn hóa subtitle có sẵn từ YouTube/yt-dlp thành transcript có provenance
cnga normalize-transcripts

# Build index local từ transcript/OCR/analysis đã có (SQLite FTS MVP)
cnga build-index

# Optional: build Chroma persistent index trong data/analysis/index/chroma
cnga build-chroma

# Chat có bằng chứng
cnga chat "Kênh này giải thích quản trị rủi ro như thế nào?"
```

## Model local

Không dùng cloud mặc định.

- Chat: đặt GGUF Qwen3 nhỏ trong `models/chat/`, chạy `llama.cpp` server local, rồi dùng `cnga analyze-local --endpoint http://127.0.0.1:8080/completion`.
- Vision: đặt Qwen3-VL GGUF trong `models/vision/`; MVP chỉ trích frame/OCR trước, chưa gọi vision tràn lan.
- Embedding: `cnga build-chroma` dùng hash embedding local không tải model để tránh cache ngoài project. Khi chuyển sang BGE-M3/sentence-transformers, cache phải nằm trong `.cache/huggingface` và model trong `models/embeddings`.
- Ollama không được bật mặc định. Chỉ dùng nếu `OLLAMA_MODELS` đã trỏ vào `models/ollama` và `cnga doctor` xác nhận không phát sinh file ngoài project.

## Kiểm thử

```powershell
python -m unittest discover -s tests
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
