# Chi tiết Pipeline

## RAG Router

`RAGRouter` phân loại truy vấn người dùng thành bốn loại bằng cách so khớp regex trên các từ khóa tiếng Việt:

| Loại        | Từ khóa kích hoạt                                    | Pipeline             |
| ----------- | --------------------------------------------------- | -------------------- |
| `RECOMMEND` | "gợi ý", "nên mua", "tư vấn", "recommend"         | RecommendPipeline    |
| `COMPARE`   | "so sánh", "compare", "vs", "tốt hơn"              | ComparePipeline      |
| `INFO`      | "thông số", "giá", "specs", "chi tiết"              | Truy xuất trực tiếp  |
| `HYBRID`    | Khớp cả pattern recommend + compare                  | RecommendPipeline    |

## Recommend Pipeline

```
Query
  → UserIntentParser (trích xuất use_case, budget, priorities)
  → FilterEngine (trích xuất brand, category, price range)
  → ProductRetriever (hybrid search + metadata filter)
  → CrossEncoderReranker (tùy chọn, rerank theo độ liên quan)
  → ProductScorer (đa tiêu chí: relevance, review, value, popularity)
  → LLM (sinh giải thích bằng template recommend_prompt)
  → ResponseParser (trích xuất JSON có cấu trúc)
  → Response
```

### Trọng số Scoring

Có thể cấu hình theo từng use case trong `configs/scoring_weights.yaml`:

| Tiêu chí    | Mặc định | Gaming | Photography | Budget |
| ----------- | ------- | ------ | ----------- | ------ |
| Relevance   | 0.35    | 0.40   | 0.40        | 0.25   |
| Review      | 0.25    | 0.20   | 0.30        | 0.20   |
| Value       | 0.25    | 0.20   | 0.15        | 0.40   |
| Popularity  | 0.15    | 0.20   | 0.15        | 0.15   |

## Compare Pipeline

```
Query
  → Trích xuất tên sản phẩm từ query (hoặc nhận product_ids)
  → ProductRetriever (lấy đầy đủ dữ liệu sản phẩm)
  → SpecAligner (chuẩn hóa tên trường, đối chiếu thông số giữa các sản phẩm)
  → ProductComparator (so sánh theo từng tiêu chí, tìm điểm nổi bật)
  → ComparisonFormatter (sinh bảng markdown)
  → LLM (sinh phân tích bằng template compare_prompt)
  → ResponseParser (trích xuất JSON có cấu trúc)
  → Response
```

## Cấu hình

Toàn bộ cài đặt pipeline được tập trung trong `PipelineConfig` (nạp từ `configs/settings.yaml`):

```yaml
llm_provider: "anthropic"
llm_model: "claude-sonnet-4-6"
embedding_model: "text-embedding-3-small"
vector_db: "chroma"
top_k_retrieve: 20
top_k_recommend: 5
```
