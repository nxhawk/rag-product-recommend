# Quick Start

## 1. Start Postgres (pgvector)

The vector store runs on Postgres with the pgvector extension. Easiest way is Docker:

```bash
cd docker
docker compose up -d postgres
```

By default the app connects to `postgresql://postgres:postgres@localhost:5432/rag_products`. Override with the `DATABASE_URL` environment variable or `vector_db_url` in `configs/settings.yaml`.

## 2. Ingest Sample Data

Load the sample product data into the vector store:

```bash
uv run python scripts/ingest.py
```

This reads products from `data/raw/products/`, chunks them by field (description, specs, pros/cons, reviews), generates embeddings, and stores everything in Postgres (pgvector).

## 3. Start the API Server

```bash
uv run uvicorn api.app:app --reload
```

The server runs at `http://localhost:8000`. Interactive docs available at `http://localhost:8000/docs`.

## 4. Try a Recommendation

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"query": "Phone with great camera under 15 million VND", "top_k": 3}'
```

## 5. Try a Comparison

```bash
curl -X POST http://localhost:8000/api/compare \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare iPhone 15 Pro Max vs Samsung Galaxy S24 Ultra"}'
```

## 6. Run Tests

```bash
uv run pytest tests/
```

## Using Docker

```bash
cd docker
docker compose up --build
```

This starts the API server, Postgres (pgvector) for the vector store, and a Redis instance for caching.
