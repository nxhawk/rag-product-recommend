# Pipeline Details

## RAG Router

The `RAGRouter` classifies user queries into four types using regex pattern matching on Vietnamese keywords:

| Type        | Trigger Keywords                                    | Pipeline             |
| ----------- | --------------------------------------------------- | -------------------- |
| `RECOMMEND` | "gợi ý", "nên mua", "tư vấn", "recommend"         | RecommendPipeline    |
| `COMPARE`   | "so sánh", "compare", "vs", "tốt hơn"              | ComparePipeline      |
| `INFO`      | "thông số", "giá", "specs", "chi tiết"              | Direct retrieval     |
| `HYBRID`    | Both recommend + compare patterns                   | RecommendPipeline    |

## Recommend Pipeline

```
Query
  → UserIntentParser (extract use_case, budget, priorities)
  → FilterEngine (extract brand, category, price range)
  → ProductRetriever (hybrid search + metadata filter)
  → CrossEncoderReranker (optional, rerank by relevance)
  → ProductScorer (multi-criteria: relevance, review, value, popularity)
  → LLM (generate explanation with recommend_prompt template)
  → ResponseParser (extract structured JSON)
  → Response
```

### Scoring Weights

Configurable per use case in `configs/scoring_weights.yaml`:

| Criterion   | Default | Gaming | Photography | Budget |
| ----------- | ------- | ------ | ----------- | ------ |
| Relevance   | 0.35    | 0.40   | 0.40        | 0.25   |
| Review      | 0.25    | 0.20   | 0.30        | 0.20   |
| Value       | 0.25    | 0.20   | 0.15        | 0.40   |
| Popularity  | 0.15    | 0.20   | 0.15        | 0.15   |

## Compare Pipeline

```
Query
  → Extract product names from query (or accept product_ids)
  → ProductRetriever (fetch full product data)
  → SpecAligner (normalize field names, align specs across products)
  → ProductComparator (compare per criterion, find highlights)
  → ComparisonFormatter (generate markdown table)
  → LLM (generate analysis with compare_prompt template)
  → ResponseParser (extract structured JSON)
  → Response
```

## Configuration

All pipeline settings are centralized in `PipelineConfig` (loaded from `configs/settings.yaml`):

```yaml
llm_provider: "anthropic"
llm_model: "claude-sonnet-4-6"
embedding_model: "text-embedding-3-small"
vector_db: "pgvector"
vector_db_url: "postgresql://postgres:postgres@localhost:5432/rag_products"
top_k_retrieve: 20
top_k_recommend: 5
```
