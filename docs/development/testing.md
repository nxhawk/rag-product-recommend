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
├── conftest.py                     # Shared fixtures (sample_product, sample_products)
├── unit/                           # Fast, isolated tests (no network / secrets)
│   ├── test_router.py              # RAGRouter query classification
│   ├── test_chunker.py             # ProductChunker output
│   ├── test_filter_engine.py       # FilterEngine extraction
│   ├── test_es_keyword_search.py   # Elasticsearch keyword query building
│   ├── test_hybrid_search.py       # HybridSearch RRF fusion + filter enforcement
│   ├── test_vector_store_filters.py # Vector store SQL metadata filters
│   ├── test_products_api.py        # /api/products CRUD route
│   ├── test_recommend_route.py     # /api/recommend route
│   ├── test_sync_events.py         # Debezium event parsing + change detection
│   └── test_sync_workers.py        # CDC sync workers (SearchIndexer, EmbeddingSyncer)
└── integration/                    # For services-backed tests (no tests yet)
```

The tests group into: **routing/chunking/filters** (`test_router`, `test_chunker`,
`test_filter_engine`); **retrieval** (`test_es_keyword_search`, `test_hybrid_search`,
`test_vector_store_filters`); **API** (`test_products_api`, `test_recommend_route`);
and **CDC sync** (`test_sync_events`, `test_sync_workers`). `tests/integration/` is
reserved for tests that need real external services and currently holds no tests.

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

### Testing the CDC sync workers

The CDC layer is tested entirely offline so it runs in CI with **no Kafka, ES, DB,
secrets, or network**:

- **`test_sync_events.py`** covers Debezium event handling — `parse_debezium_message`,
  the `content_hash` of the text-bearing fields, `text_changed` detection, and the
  `metadata_fields` that trigger a metadata-only update rather than a re-embed.
- **`test_sync_workers.py`** exercises the two workers (`SearchIndexer` and
  `EmbeddingSyncer`) against **in-memory fakes** (`FakeES`, `FakeVectorStore`,
  `FakeEmbedder`). No real Kafka/ES/DB is involved, so the change-detection logic
  is verified without any live service.

## Evaluation

RAG quality evaluation scripts are in `evaluation/`. Unlike `tests/`, they run
against the **real** pipeline (embedder + vector store + LLM) instead of mocks,
so they are run manually and are intentionally excluded from the pytest suite
(see `TEST_PLAN.md`). They need the same `.env` (LLM + embedding provider keys)
and a reachable Postgres/pgvector as the API — the pipeline is built the same
way `api/deps.py` builds it for a request.

```bash
# Run recommendation evaluation (uses evaluation/test_case/test_cases_recommend.json by default)
uv run python evaluation/eval_recommend.py

# Run comparison evaluation (not implemented yet — TODO stub)
uv run python evaluation/eval_compare.py
```

Test cases live in `evaluation/test_case/`, split by pipeline into
`test_cases_recommend.json` and `test_cases_compare.json`; each is still
tagged by `type` (`recommend` or `compare`) so each script only picks up
its own cases.

### `eval_recommend.py`

`RecommendEvaluator` runs every `type: "recommend"` case through the live
`RecommendPipeline` and scores it on four metrics. Each metric is computed
against the pipeline's **retrieved candidates** rather than the LLM's
free-form prose, so a low score points at a specific stage:

| Metric | What it measures | Computed from |
| ------ | ----------------- | -------------- |
| `relevance` | Fraction of retrieved candidates whose category matches `expected_category` | Retrieved candidate metadata |
| `budget_fit` | Fraction of retrieved candidates priced inside `expected_price_range` | Retrieved candidate metadata |
| `intent_recall` | Fraction of `expected_features` that `UserIntentParser` detects in the query | Parsed query intent (`priorities` + `use_case`) |
| `faithfulness` | 1.0 when the LLM output parses as structured JSON, is non-empty, and every recommended product name matches a retrieved candidate; penalizes hallucinated products | LLM response vs. retrieved candidates |

A case **passes** when the average of its four scores is ≥ `--pass-threshold`
(default `0.7`). The script prints a per-case breakdown and the aggregate
metrics across all cases:

```
[PASS] rec_01 (score=0.917) - Tôi muốn mua điện thoại chụp ảnh đẹp, tầm 15 triệu
  relevance     : 1.0
  budget_fit    : 1.0
  intent_recall : 1.0
  faithfulness  : 0.667

------------------------------------------------------------------
Total: 2  Passed: 2  Pass rate: 1.0
Average metrics:
  relevance     : 1.0
  budget_fit    : 0.85
  intent_recall : 1.0
  faithfulness  : 0.75
```

#### Interpreting the scores

Every metric is a 0.0–1.0 fraction; a case's `score` is the average of its
four metrics, and the `Average metrics` block at the bottom is the mean of
each metric across every case in the run. A metric lands on `0.0` when the
stage it measures produced *nothing usable* for that case — not merely
"below average":

| Metric | 1.0 means | Low / 0.0 usually means | Look at |
| ------ | --------- | ------------------------ | ------- |
| `relevance` | Every retrieved candidate belongs to `expected_category` | Retrieval pulled products from the wrong category — either the catalog has few/no products in that category yet, or the query's category isn't being detected | `src/retrieval/filter_engine.py` (category extraction), `configs/settings.yaml` (`use_bm25`, `top_k_retrieve`), or the seeded catalog itself (`data/raw/products`) |
| `budget_fit` | Every retrieved candidate is priced inside `expected_price_range` | The vector store has no products in that price band, or the price filter isn't reaching the query | `src/retrieval/filter_engine.py` (price extraction), `src/retrieval/product_retriever.py` (`_build_where_clause`) |
| `intent_recall` | The parser detected every `expected_features` entry from the query wording | `UserIntentParser` is pure keyword matching (no LLM) — the query's phrasing isn't in its keyword lists, or a test case's `expected_features` uses a label the parser never produces | `src/pipeline/recommend/user_intent_parser.py` (`USE_CASE_KEYWORDS`, `PRIORITY_KEYWORDS`) |
| `faithfulness` | LLM output parsed as JSON, non-empty, and every recommended name matches a retrieved candidate | Either (a) the LLM call didn't return valid JSON (`response_parser` fell back to `{"structured": False, "text": ...}`), (b) `recommendations` came back empty, or (c) the LLM renamed/invented a product that doesn't exactly match a retrieved candidate's `name` | `src/generation/response_parser.py`, `src/generation/prompt_templates/recommend_prompt.py`, and whether the LLM call is even succeeding (API key, provider, rate limits) |

`faithfulness` pinned at exactly `0.0` across *every* case (rather than a
partial value like `0.5`) is the strongest signal to check first — it means
the generation stage isn't producing usable output at all, not that a few
product names were mismatched. Re-run with `--output evaluation/report.json`
and check each case's `"error"` field in the JSON: if `pipeline.run()`
raised (auth failure, quota, network), the exception message is recorded
there instead of a partial score.

Conversely, `relevance`/`budget_fit`/`intent_recall` sitting around `0.5`
on a freshly seeded or small catalog is often just thin test data — the
catalog may not yet have enough products in that category/price band —
rather than a retrieval bug. Check `data/raw/products` and run
`scripts/seed.py` / `scripts/ingest.py` before assuming the logic is wrong.

CLI flags:

| Flag | Default | Description |
| ---- | ------- | ------------ |
| `--test-cases` | `evaluation/test_case/test_cases_recommend.json` | Path to the JSON test case file |
| `--top-k` | `5` | `top_k` passed to the pipeline |
| `--pass-threshold` | `0.7` | Average score a case needs to be marked as passed |
| `--config` | `configs/settings.yaml` | Pipeline config YAML |
| `--output` | *(none)* | Optional path to write the full JSON report to |

```bash
# Custom top_k / pass bar, save the full report as JSON
uv run python evaluation/eval_recommend.py \
  --top-k 3 \
  --pass-threshold 0.6 \
  --output evaluation/report.json
```

If a case's pipeline run raises (e.g. LLM quota, DB down), the evaluator
catches it, scores all four metrics `0.0`, records the error message on the
case, and continues with the remaining cases instead of aborting the run.

`eval_compare.py` is still a TODO stub — `ComparePipeline` isn't wired into
it yet.
