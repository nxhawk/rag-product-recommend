# Project Structure

```
rag-product-recommend/
├── pyproject.toml              # Dependencies & project metadata
├── uv.lock                     # Lockfile (like package-lock.json)
│
├── src/                        # Core business logic
│   ├── ingestion/              # Data loading & normalization
│   │   ├── product_loader.py   #   Load from JSON/CSV
│   │   ├── review_loader.py    #   Load user reviews
│   │   ├── data_cleaner.py     #   Clean & normalize data
│   │   ├── spec_parser.py      #   Parse product specifications
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
│   │   │   ├── engine.py
│   │   │   ├── user_intent_parser.py
│   │   │   ├── scoring.py
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
│   ├── ingest.py               #   Ingest data into vector store
│   └── seed.py                 #   Seed sample data
│
├── configs/
│   ├── settings.yaml
│   ├── product_categories.yaml
│   └── scoring_weights.yaml
│
├── docs/                       # MkDocs documentation source
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── data/
    ├── raw/products/
    ├── processed/
    └── embeddings/             # ChromaDB persist (gitignored)
```

## Key Conventions

| Convention         | Rule                                                                 |
| ------------------ | -------------------------------------------------------------------- |
| Imports            | Always absolute from project root: `from src.retrieval.x import X`   |
| Config             | `PipelineConfig` dataclass from `configs/settings.yaml`              |
| LLM calls          | Always through `src/generation/llm_client.py`, never direct          |
| Vector DB          | Always through `src/embedding/vector_store.py`                       |
| Prompt templates   | Module-level constants: `SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE`      |
| API dependencies   | Factory functions in `api/deps.py`                                   |
| User-facing text   | Vietnamese                                                           |
| Code / comments    | English                                                              |
| Package management | `uv` (not pip)                                                       |
