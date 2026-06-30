# Testing

## Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run unit tests only
uv run pytest tests/unit/

# Run integration tests only
uv run pytest tests/integration/

# Run with verbose output
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/unit/test_filter_engine.py
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures (sample_product, sample_products)
├── unit/                 # Fast, isolated tests
│   ├── test_router.py    # RAGRouter query classification
│   ├── test_chunker.py   # ProductChunker output
│   └── test_filter_engine.py  # FilterEngine extraction
└── integration/          # Tests requiring external services
```

## Writing Tests

Use pytest fixtures from `conftest.py` for sample data:

```python
def test_chunker_output(sample_product):
    from src.ingestion.chunker import ProductChunker

    chunker = ProductChunker()
    chunks = chunker.chunk_product(sample_product)

    assert len(chunks) >= 2
    assert all("product_id" in c for c in chunks)
```

## Evaluation

RAG quality evaluation scripts are in `evaluation/`:

```bash
# Run recommendation evaluation
uv run python evaluation/eval_recommend.py

# Run comparison evaluation
uv run python evaluation/eval_compare.py
```

Test cases are defined in `evaluation/test_cases.json`.
