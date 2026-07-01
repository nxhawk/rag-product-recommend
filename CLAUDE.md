# CLAUDE.md

## Language Rules

- **Code comments**: English only.
- **Docstrings**: English only.
- **Variable/function/class names**: English only.
- **Documentation files** (`docs/**/*.md`, `README.md`, `CLAUDE.md`): English only.
- **Git commit messages**: English only.
- **User-facing text** (LLM prompts, API responses shown to end users): Vietnamese.

## Code Style

- Use Python 3.11+ features (type unions with `|`, `match` statements, etc.).
- Use type hints on all function signatures.
- Use `uv` for package management (not pip). Add deps via `uv add <package>`.
- Documentation site: MkDocs Material (`docs/` folder, config in `mkdocs.yml`).

## Project Overview

RAG-based product recommendation & comparison system. Users ask natural language queries in Vietnamese, the system retrieves product data from a vector DB, then an LLM generates contextual answers.

Two main pipelines:
- **Recommend**: Query → Intent Parser → Filter → Retrieve → Rerank → Score → LLM → Response
- **Compare**: Query → Extract Products → Retrieve Specs → Align → Compare → LLM → Response

## Project Structure

```
rag-product-recommend/
├── pyproject.toml              # Dependencies & project metadata
├── uv.lock                     # Lockfile
│
├── src/                        # Core business logic
│   ├── crawler/                # Web crawling (raw data collection)
│   │   ├── config.py           #   CrawlerConfig / SourceConfig (crawler.yaml)
│   │   ├── http_client.py      #   httpx client: retry + rate limit + robots
│   │   ├── rate_limiter.py     #   Polite delay between requests
│   │   ├── robots.py           #   robots.txt checker
│   │   ├── parser.py           #   BeautifulSoup helpers (price/rating/text)
│   │   ├── models.py           #   CrawledProduct / CrawlResult dataclasses
│   │   ├── storage.py          #   Save raw results to data/raw/crawled
│   │   ├── pipeline.py         #   CrawlPipeline: spider → product → store
│   │   └── spiders/            #   One spider per source
│   │       ├── base_spider.py  #     BaseSpider (list + detail hooks)
│   │       ├── tgdd_spider.py  #     thegioididong.com
│   │       └── cellphones_spider.py # cellphones.com.vn
│   │
│   ├── ingestion/              # Data loading & normalization
│   │   ├── product_loader.py   #   Load from JSON/CSV
│   │   ├── review_loader.py    #   Load user reviews
│   │   ├── data_cleaner.py     #   Clean & normalize data
│   │   ├── spec_parser.py      #   Parse product specs
│   │   ├── chunker.py          #   Field-based chunking
│   │   └── price_tracker.py    #   Price history tracking
│   │
│   ├── embedding/              # Embedding & Vector DB
│   │   ├── product_embedder.py #   Text → vector (OpenAI)
│   │   ├── multi_field_embedder.py
│   │   └── vector_store.py     #   ChromaDB/Qdrant operations
│   │
│   ├── retrieval/              # Product retrieval
│   │   ├── product_retriever.py #  Combine filter + search
│   │   ├── hybrid_search.py    #   Semantic + keyword search
│   │   ├── filter_engine.py    #   Extract filters from NL query
│   │   ├── similarity_scorer.py #  Composite scoring
│   │   └── reranker.py         #   Cross-encoder reranking
│   │
│   ├── generation/             # LLM generation
│   │   ├── llm_client.py       #   Multi-provider (Anthropic, OpenAI)
│   │   ├── response_parser.py  #   Parse JSON from LLM output
│   │   ├── guardrails.py       #   Input/output validation
│   │   └── prompt_templates/
│   │       ├── recommend_prompt.py
│   │       ├── compare_prompt.py
│   │       └── review_summary_prompt.py
│   │
│   ├── pipeline/               # Orchestration layer
│   │   ├── rag_router.py       #   Classify query → pipeline
│   │   ├── config.py           #   PipelineConfig dataclass
│   │   ├── recommend_pipeline.py
│   │   ├── compare_pipeline.py
│   │   ├── recommend/          #   Recommendation domain logic
│   │   │   ├── engine.py       #     Main recommend engine
│   │   │   ├── user_intent_parser.py
│   │   │   ├── scoring.py      #     Multi-criteria scoring
│   │   │   └── personalization.py
│   │   └── compare/            #   Comparison domain logic
│   │       ├── comparator.py
│   │       ├── spec_aligner.py
│   │       ├── formatter.py
│   │       └── pros_cons_extractor.py
│   │
│   └── utils/
│       ├── logger.py
│       ├── cache.py
│       └── helpers.py
│
├── api/                        # FastAPI layer
│   ├── app.py                  #   Entry point
│   ├── schemas.py              #   Pydantic request/response models
│   ├── deps.py                 #   Dependency injection
│   ├── routes/
│   │   ├── recommend.py        #   POST /api/recommend
│   │   ├── compare.py          #   POST /api/compare
│   │   └── search.py           #   POST /api/search
│   └── middleware/
│       ├── rate_limit.py
│       └── error_handler.py
│
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── unit/
│   └── integration/
│
├── evaluation/                 # RAG quality evaluation
│   ├── eval_recommend.py
│   ├── eval_compare.py
│   └── test_cases.json
│
├── scripts/                    # CLI scripts
│   ├── crawl.py                #   Crawl raw data into data/raw/crawled
│   ├── ingest.py               #   Ingest data into vector store
│   └── seed.py                 #   Seed sample data
│
├── configs/
│   ├── settings.yaml
│   ├── crawler.yaml            #   Crawler sources & politeness settings
│   ├── product_categories.yaml
│   └── scoring_weights.yaml
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── data/
    ├── raw/products/
    ├── raw/crawled/            #   Raw crawler output (gitignored)
    ├── processed/
    └── embeddings/             # ChromaDB persist (gitignored)
```

## Key Patterns

- **Imports**: Always use absolute imports from project root, e.g. `from src.retrieval.filter_engine import FilterEngine`.
- **Config**: `PipelineConfig` dataclass loaded from `configs/settings.yaml`. Access via `api/deps.py` factory functions.
- **LLM calls**: Go through `src/generation/llm_client.py` (supports Anthropic + OpenAI). Never call LLM APIs directly.
- **Vector DB**: Go through `src/embedding/vector_store.py`. Currently ChromaDB with cosine similarity.
- **Prompt templates**: Stored as module-level constants (`SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE`) in `src/generation/prompt_templates/`.
- **API dependencies**: Use factory functions in `api/deps.py` (e.g. `get_retriever()`, `get_llm_client()`).
- **User-facing text**: Vietnamese. Code/comments/docstrings: English.
