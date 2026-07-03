# Testing

## Chạy Test

```bash
# Chạy toàn bộ test
uv run pytest tests/

# Chỉ chạy unit test
uv run pytest tests/unit/

# Chỉ chạy integration test
uv run pytest tests/integration/

# Chạy với output verbose
uv run pytest tests/ -v

# Chạy một file test cụ thể
uv run pytest tests/unit/test_filter_engine.py
```

## Cấu trúc Test

```
tests/
├── conftest.py           # Fixture dùng chung (sample_product, sample_products)
├── unit/                 # Test nhanh, độc lập
│   ├── test_router.py    # Phân loại truy vấn của RAGRouter
│   ├── test_chunker.py   # Output của ProductChunker
│   └── test_filter_engine.py  # Trích xuất của FilterEngine
└── integration/          # Test cần dịch vụ bên ngoài
```

## Viết Test

Dùng fixture pytest từ `conftest.py` cho dữ liệu mẫu:

```python
def test_chunker_output(sample_product):
    from src.ingestion.chunker import ProductChunker

    chunker = ProductChunker()
    chunks = chunker.chunk_product(sample_product)

    assert len(chunks) >= 2
    assert all("product_id" in c for c in chunks)
```

## Đánh giá (Evaluation)

Các script đánh giá chất lượng RAG nằm trong `evaluation/`:

```bash
# Chạy đánh giá gợi ý
uv run python evaluation/eval_recommend.py

# Chạy đánh giá so sánh
uv run python evaluation/eval_compare.py
```

Test case được định nghĩa trong `evaluation/test_cases.json`.
