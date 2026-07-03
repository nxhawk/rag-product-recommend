# Bắt đầu nhanh

## 1. Khởi động Postgres (pgvector)

Vector store chạy trên Postgres với extension pgvector. Cách dễ nhất là dùng Docker:

```bash
cd docker
docker compose up -d postgres
```

Mặc định app kết nối tới `postgresql://postgres:postgres@localhost:5432/rag_products`. Có thể override bằng biến môi trường `DATABASE_URL` hoặc `vector_db_url` trong `configs/settings.yaml`.

## 2. Nạp dữ liệu mẫu

Nạp dữ liệu sản phẩm mẫu vào vector store:

```bash
uv run python scripts/ingest.py
```

Lệnh này đọc sản phẩm từ `data/raw/products/`, chia nhỏ theo từng trường (mô tả, thông số, ưu/nhược điểm, đánh giá), sinh embedding, rồi lưu toàn bộ vào Postgres (pgvector).

## 3. Khởi động API Server

```bash
uv run uvicorn api.app:app --reload
```

Server chạy tại `http://localhost:8000`. Tài liệu tương tác có sẵn tại `http://localhost:8000/docs`.

## 4. Thử gợi ý sản phẩm

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"query": "Phone with great camera under 15 million VND", "top_k": 3}'
```

## 5. Thử so sánh sản phẩm

```bash
curl -X POST http://localhost:8000/api/compare \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare iPhone 15 Pro Max vs Samsung Galaxy S24 Ultra"}'
```

## 6. Chạy Tests

```bash
uv run pytest tests/
```

## Sử dụng Docker

```bash
cd docker
docker compose up --build
```

Lệnh này khởi động API server, Postgres (pgvector) cho vector store, cùng một instance Redis để caching.
