# Quick Start

## 1. Ingest Sample Data

Load the sample product data into the vector store:

```bash
uv run python scripts/ingest.py
```

This reads products from `data/raw/products/`, chunks them by field (description, specs, pros/cons, reviews), generates embeddings, and stores everything in ChromaDB.

## 2. Start the API Server

```bash
uv run uvicorn api.app:app --reload
```

The server runs at `http://localhost:8000`. Interactive docs available at `http://localhost:8000/docs`.

## 3. Try a Recommendation

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"query": "Phone with great camera under 15 million VND", "top_k": 3}'
```

## 4. Try a Comparison

```bash
curl -X POST http://localhost:8000/api/compare \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare iPhone 15 Pro Max vs Samsung Galaxy S24 Ultra"}'
```

## 5. Run Tests

```bash
uv run pytest tests/
```

## Using Docker

```bash
cd docker
docker compose up --build
```

This starts the API server and a Redis instance for caching.
