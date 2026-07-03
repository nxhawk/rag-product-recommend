# Hướng dẫn phát triển

Hướng dẫn này giúp bạn thiết lập dự án để phát triển cục bộ, chạy server, thực thi test, và làm việc với Docker.

## Yêu cầu

- **Python 3.11+** — bắt buộc cho dự án
- **[uv](https://docs.astral.sh/uv/)** — trình quản lý gói Python nhanh (thay thế pip)
- **Git**
- **Docker + Docker Compose** (tùy chọn, cho thiết lập containerized)

### Cài đặt uv

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

## Clone & Cài đặt

```bash
git clone https://github.com/nxhawk/rag-product-recommend.git
cd rag-product-recommend

# Cài đặt toàn bộ dependencies (bao gồm nhóm dev + docs)
uv sync --group dev --group docs
```

`uv sync` đọc `pyproject.toml`, resolve version từ `uv.lock`, và tự động tạo virtual environment. Không cần tạo venv thủ công.

## Biến môi trường

Sao chép file mẫu và điền API key của bạn:

```bash
cp .env.example .env
```

Chỉnh sửa `.env`:

```dotenv
# Cần ít nhất một LLM key
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...

# Môi trường
ENVIRONMENT=development
LOG_LEVEL=INFO
```

!!! tip "Tôi cần key nào?"
    Bạn chỉ cần key cho provider được cấu hình trong `configs/settings.yaml`. Mặc định dự án dùng **Anthropic** cho LLM và **OpenAI** cho embedding, nên tối thiểu bạn cần `ANTHROPIC_API_KEY` và `OPENAI_API_KEY`.

## Cấu hình

Toàn bộ cài đặt pipeline nằm trong `configs/settings.yaml`:

```yaml
# LLM provider: "anthropic" | "openai" | "gemini"
llm_provider: "anthropic"
llm_model: "claude-sonnet-4-6"

# Embedding (hiện chỉ hỗ trợ OpenAI)
embedding_provider: "openai"
embedding_model: "text-embedding-3-small"

# Vector DB
vector_db: "chroma"
vector_db_path: "./data/embeddings"

# Retrieval
top_k_retrieve: 20
top_k_recommend: 5
top_k_compare: 3
```

Cấu hình được nạp thành dataclass `PipelineConfig` qua `PipelineConfig.from_yaml()` và được inject vào các component thông qua các factory function trong `api/deps.py`.

## Nạp dữ liệu (Data Ingestion)

Trước khi chạy server, cần nạp dữ liệu sản phẩm vào vector store:

```bash
# Sinh dữ liệu mẫu (tạo các file JSON trong data/raw/products/)
uv run python scripts/seed.py

# Nạp vào ChromaDB
uv run python scripts/ingest.py
```

Các bước này sẽ:

1. Load dữ liệu sản phẩm từ `data/raw/products/`
2. Làm sạch và chuẩn hóa dữ liệu
3. Chia nhỏ các trường sản phẩm (chunk)
4. Sinh embedding qua OpenAI
5. Lưu vector vào ChromaDB tại `data/embeddings/`

## Chạy API Server

```bash
uv run uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

Server khởi động tại `http://localhost:8000`. Các endpoint chính:

| Method | Endpoint         | Mô tả                   |
| ------ | ---------------- | ------------------------ |
| POST   | `/api/recommend` | Gợi ý sản phẩm            |
| POST   | `/api/compare`   | So sánh sản phẩm          |
| POST   | `/api/search`    | Tìm kiếm sản phẩm         |
| GET    | `/health`        | Kiểm tra tình trạng (health check) |

Tài liệu API tương tác có sẵn tại `http://localhost:8000/docs` (Swagger UI).

### Ví dụ Request

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"query": "Điện thoại chụp ảnh đẹp dưới 15 triệu", "top_k": 3}'
```

## Chạy Tests

```bash
# Chạy toàn bộ test
uv run pytest tests/ -v

# Chỉ chạy unit test
uv run pytest tests/unit/ -v

# Chỉ chạy integration test
uv run pytest tests/integration/ -v

# Chạy kèm coverage
uv run pytest tests/ --cov=src --cov=api
```

!!! note
    Để dùng `--cov`, cần cài `pytest-cov` trước: `uv add --group dev pytest-cov`

## Docker

Dự án bao gồm cấu hình Docker Compose với API server và Redis:

```bash
cd docker
docker compose up --build
```

Lệnh này khởi động:

- **app** — FastAPI server trên cổng `8000`
- **redis** — Redis cache trên cổng `6379`

Thư mục `data/` được mount như một volume nên vector store vẫn được giữ lại sau khi container restart.

### Chỉ Build Image

```bash
docker build -f docker/Dockerfile -t rag-product-recommend .
```

## Chạy Docs cục bộ

```bash
uv run mkdocs serve
```

Mở tại `http://localhost:8000` (hoặc `8001` nếu `8000` đã được dùng). Các thay đổi trong `docs/` sẽ tự động hot-reload.

## Tổng hợp các lệnh thường dùng

| Lệnh | Mô tả |
| ------- | ----------- |
| `uv sync` | Cài đặt/cập nhật toàn bộ dependencies |
| `uv add <pkg>` | Thêm một production dependency |
| `uv add --group dev <pkg>` | Thêm một dev dependency |
| `uv run <cmd>` | Chạy lệnh bên trong venv |
| `uv run pytest tests/ -v` | Chạy test |
| `uv run uvicorn api.app:app --reload` | Khởi động dev server |
| `uv run mkdocs serve` | Chạy docs cục bộ |
| `uv run mkdocs build --strict` | Build docs (chế độ CI) |

## Quản lý Dependencies

Dự án này dùng **uv** với `pyproject.toml` (tương tự `package.json` trong Node.js). File lockfile `uv.lock` ghim chính xác version (tương tự `package-lock.json`).

- **Production deps** — liệt kê dưới `[project] dependencies`
- **Dev deps** — dưới `[dependency-groups] dev` (pytest, ...)
- **Docs deps** — dưới `[dependency-groups] docs` (mkdocs-material, ...)

Không bao giờ cài package bằng `pip install` trực tiếp. Luôn dùng `uv add`.
