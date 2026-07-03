# RAG Product Recommendation & Comparison

A product recommendation and comparison system powered by **RAG (Retrieval-Augmented Generation)**. Users ask natural language queries, the system retrieves relevant product data from a vector database, then an LLM generates contextual answers.

## Key Features

- **Product Recommendation** — Analyzes user intent (budget, purpose, priorities) → retrieves matching products → scores and ranks → LLM explains why each product fits.
- **Product Comparison** — Aligns specifications across products → compares each criterion → LLM produces detailed analysis with pros/cons and conclusions.
- **Smart Search** — Hybrid search (semantic + keyword + metadata filter) with optional cross-encoder reranking.
- **Web Crawling** — Collects live specs and reviews from e-commerce sites (thegioididong.com, cellphones.com.vn) to seed the vector store.
- **Vietnamese NLP** — Full support for Vietnamese queries and responses.
- **Multi-provider LLM** — Anthropic Claude, OpenAI GPT, or Google Gemini, selectable via config.

## Tech Stack

| Component    | Choice                                              |
| ------------ | ---------------------------------------------------- |
| Language     | Python 3.11+                                          |
| Package Mgr  | [uv](https://docs.astral.sh/uv/)                      |
| API          | FastAPI + uvicorn                                     |
| LLM          | Anthropic Claude / OpenAI GPT / Google Gemini         |
| Embedding    | OpenAI `text-embedding-3-small`                       |
| Vector DB    | ChromaDB (embedded) → Qdrant (swap-in for production) |
| Crawling     | httpx + BeautifulSoup + lxml (tenacity for retries)   |
| Cache        | Redis (provisioned in Docker Compose)                 |
| Container    | Docker + Docker Compose                               |
| Testing      | pytest                                                |
| Docs         | MkDocs Material (bilingual EN/VI)                     |

## Quick Start

```bash
# 1. Install uv (if not installed)
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install dependencies
git clone <repo-url>
cd rag-product-recommend
uv sync

# 3. Configure API keys
# Create a .env file at the project root with:
#   ANTHROPIC_API_KEY=...
#   OPENAI_API_KEY=...
#   GEMINI_API_KEY=...
#   ENVIRONMENT=development
#   LOG_LEVEL=INFO

# 4. (Optional) Crawl fresh product data
uv run python scripts/crawl.py --all

# 5. Ingest product data into the vector store
uv run python scripts/ingest.py

# 6. Start API server
uv run uvicorn api.app:app --reload

# 7. Run tests
uv run pytest tests/
```

## API Endpoints

| Method | Endpoint         | Description             |
| ------ | ---------------- | ------------------------ |
| POST   | `/api/recommend` | Product recommendation   |
| POST   | `/api/compare`   | Product comparison       |
| POST   | `/api/search`    | Product search            |
| GET    | `/health`        | Health check               |

**Example request:**

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"query": "Phone with great camera under 15 million VND", "top_k": 3}'
```

> **Status:** the route handlers in `api/routes/` are scaffolded with their final request/response schemas (`api/schemas.py`); wiring them to the pipeline factories in `api/deps.py` is in progress — see [PLAN.md](./PLAN.md) for the current phase.

## Project Structure

```
rag-product-recommend/
├── pyproject.toml       # Dependencies & project metadata
├── uv.lock              # Lockfile
├── CLAUDE.md            # AI coding rules + exhaustive per-file structure reference
├── .env                 # API keys (not committed)
│
├── src/                 # Core business logic
│   ├── crawler/         #   Web crawling → data/raw/crawled/ (spiders/ per source)
│   ├── ingestion/       #   Load, clean, parse specs, chunk raw product data
│   ├── embedding/       #   Text → vector (OpenAI) + vector store CRUD (ChromaDB/Qdrant)
│   ├── retrieval/       #   Hybrid search, filter extraction, scoring, reranking
│   ├── generation/      #   Multi-provider LLM client, prompt templates, guardrails
│   ├── pipeline/        #   Orchestration: RAG router + recommend/compare pipelines
│   └── utils/           #   Logger, cache, helpers
│
├── api/                 # FastAPI layer
│   ├── app.py           #   Entry point
│   ├── schemas.py       #   Request/response models
│   ├── deps.py          #   Dependency injection factories
│   ├── routes/          #   recommend.py, compare.py, search.py
│   └── middleware/      #   rate_limit.py, error_handler.py
│
├── tests/               # pytest suite (unit/, integration/)
├── evaluation/          # RAG quality evaluation scripts + test cases
├── scripts/             # CLI entry points: crawl.py, ingest.py, seed.py
│
├── configs/             # settings.yaml, crawler.yaml, product_categories.yaml, scoring_weights.yaml
├── docs/                # MkDocs Material documentation (EN + VI)
├── docker/              # Dockerfile, docker-compose.yml (app + redis)
│
└── data/
    ├── raw/products/    # Curated sample data (tracked)
    ├── raw/crawled/     # Raw crawler output (gitignored)
    ├── processed/       # Cleaned/chunked data (gitignored)
    └── embeddings/      # ChromaDB persist directory (gitignored)
```

## RAG Pipeline Flow

```
User Query
    │
    ▼
┌─────────────┐
│  RAG Router  │ ── Classify: RECOMMEND / COMPARE / INFO / HYBRID
└─────┬───────┘
      │
      ├── RECOMMEND ──────────────────────────┐
      │   Intent Parser → Filter → Retrieve   │
      │   → Rerank → Score → LLM → Response   │
      │                                        │
      └── COMPARE ────────────────────────────┐│
          Extract Products → Retrieve Specs   ││
          → Align → Compare → LLM → Response  ││
                                               ▼▼
                                          JSON Response
```

See the [C4 Model](https://nxhawk.github.io/rag-product-recommend/architecture/c4-model/) and [Data Flow](https://nxhawk.github.io/rag-product-recommend/architecture/data-flow/) docs pages for a deeper architectural view.

## Development

```bash
# Add a dependency
uv add <package>

# Add a dev dependency
uv add --group dev <package>

# Run any command inside the venv
uv run <command>

# Crawl a specific source/category
uv run python scripts/crawl.py --source tgdd --category smartphone

# Serve docs locally
uv sync --group docs
uv run mkdocs serve

# Docker
cd docker
docker compose up --build
```

## Documentation

Full documentation (English + Vietnamese) is available at the [project docs site](https://nxhawk.github.io/rag-product-recommend/) (deployed via GitHub Pages, see `.github/workflows/docs.yml`).

To serve locally:

```bash
uv sync --group docs
uv run mkdocs serve
```

## Roadmap

See [PLAN.md](./PLAN.md) for the detailed phase-by-phase roadmap.

## License

MIT
