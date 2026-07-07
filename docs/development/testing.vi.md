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
├── conftest.py                     # Fixture dùng chung (sample_product, sample_products)
├── unit/                           # Test nhanh, độc lập (không cần network / secrets)
│   ├── test_router.py              # Phân loại truy vấn của RAGRouter
│   ├── test_chunker.py             # Output của ProductChunker
│   ├── test_filter_engine.py       # Trích xuất của FilterEngine
│   ├── test_es_keyword_search.py   # Dựng truy vấn keyword Elasticsearch
│   ├── test_hybrid_search.py       # Fusion RRF + áp filter của HybridSearch
│   ├── test_vector_store_filters.py # Filter metadata SQL của vector store
│   ├── test_products_api.py        # Route CRUD /api/products
│   ├── test_recommend_route.py     # Route /api/recommend
│   ├── test_sync_events.py         # Parse event Debezium + phát hiện thay đổi
│   └── test_sync_workers.py        # Các CDC sync worker (SearchIndexer, EmbeddingSyncer)
└── integration/                    # Dành cho test cần dịch vụ ngoài (chưa có test)
```

Các test được nhóm thành: **routing/chunking/filter** (`test_router`, `test_chunker`,
`test_filter_engine`); **retrieval** (`test_es_keyword_search`, `test_hybrid_search`,
`test_vector_store_filters`); **API** (`test_products_api`, `test_recommend_route`);
và **CDC sync** (`test_sync_events`, `test_sync_workers`). `tests/integration/` dành
cho các test cần dịch vụ ngoài thật và hiện chưa có test nào.

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

### Test các CDC sync worker

Tầng CDC được test hoàn toàn offline nên chạy được trong CI mà **không cần Kafka,
ES, DB, secrets hay network**:

- **`test_sync_events.py`** phủ phần xử lý event Debezium — `parse_debezium_message`,
  `content_hash` của các trường chứa văn bản, phát hiện `text_changed`, và các
  `metadata_fields` kích hoạt cập nhật metadata-only thay vì re-embed.
- **`test_sync_workers.py`** kiểm thử hai worker (`SearchIndexer` và
  `EmbeddingSyncer`) dựa trên **fakes trong bộ nhớ** (`FakeES`, `FakeVectorStore`,
  `FakeEmbedder`). Không dùng Kafka/ES/DB thật, nên logic phát hiện thay đổi được
  kiểm chứng mà không cần dịch vụ chạy thật.

## Đánh giá (Evaluation)

Các script đánh giá chất lượng RAG nằm trong `evaluation/`. Khác với
`tests/`, các script này chạy trên pipeline **thật** (embedder + vector
store + LLM) thay vì mock, nên được chạy thủ công và chủ đích không nằm
trong bộ pytest (xem `TEST_PLAN.md`). Chúng cần cùng file `.env` (API key
của LLM + embedding provider) và Postgres/pgvector đang chạy giống như API —
pipeline được dựng theo đúng cách `api/deps.py` dựng cho một request.

```bash
# Chạy đánh giá gợi ý (mặc định dùng evaluation/test_case/test_cases_recommend.json)
uv run python evaluation/eval_recommend.py

# Chạy đánh giá so sánh (chưa implement — vẫn là TODO stub)
uv run python evaluation/eval_compare.py
```

Test case nằm trong `evaluation/test_case/`, tách theo pipeline thành
`test_cases_recommend.json` và `test_cases_compare.json`; mỗi file vẫn gắn
nhãn theo `type` (`recommend` hoặc `compare`) để mỗi script chỉ lấy đúng
case của mình.

### `eval_recommend.py`

`RecommendEvaluator` chạy từng case `type: "recommend"` qua `RecommendPipeline`
thật và chấm 4 metric. Mỗi metric được tính trên **candidate đã retrieve**
của pipeline thay vì văn bản tự do của LLM, để điểm thấp trỏ đúng vào một
bước cụ thể:

| Metric | Đo cái gì | Tính từ |
| ------ | ---------- | -------- |
| `relevance` | Tỉ lệ candidate đã retrieve có category khớp `expected_category` | Metadata của candidate đã retrieve |
| `budget_fit` | Tỉ lệ candidate đã retrieve có giá nằm trong `expected_price_range` | Metadata của candidate đã retrieve |
| `intent_recall` | Tỉ lệ `expected_features` mà `UserIntentParser` nhận ra được trong câu hỏi | Intent đã parse từ query (`priorities` + `use_case`) |
| `faithfulness` | Bằng 1.0 khi output của LLM parse được thành JSON có cấu trúc, không rỗng, và mọi sản phẩm được gợi ý đều khớp tên với một candidate đã retrieve; bị trừ điểm khi có sản phẩm "ảo" (hallucination) | So khớp output LLM với candidate đã retrieve |

Một case **pass** khi điểm trung bình của 4 metric ≥ `--pass-threshold`
(mặc định `0.7`). Script in ra chi tiết từng case và metric trung bình
trên toàn bộ:

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

#### Cách hiểu các thông số (metric)

Mỗi metric là một phân số 0.0–1.0; `score` của một case là trung bình 4
metric của nó, còn khối `Average metrics` ở cuối là trung bình từng metric
trên toàn bộ case của lượt chạy. Một metric rơi về `0.0` nghĩa là bước mà
nó đo *không tạo ra được gì dùng được* cho case đó — chứ không đơn thuần là
"dưới trung bình":

| Metric | Bằng 1.0 nghĩa là | Thấp / bằng 0.0 thường do | Xem ở |
| ------ | ------------------ | -------------------------- | ----- |
| `relevance` | Mọi candidate đã retrieve đều thuộc `expected_category` | Retrieval lấy nhầm sản phẩm ở category khác — hoặc catalog chưa có/có ít sản phẩm ở category đó, hoặc category trong query chưa được nhận diện | `src/retrieval/filter_engine.py` (trích xuất category), `configs/settings.yaml` (`use_bm25`, `top_k_retrieve`), hoặc chính dữ liệu catalog đã seed (`data/raw/products`) |
| `budget_fit` | Mọi candidate đã retrieve đều có giá nằm trong `expected_price_range` | Vector store không có sản phẩm ở khoảng giá đó, hoặc filter giá chưa được áp vào query | `src/retrieval/filter_engine.py` (trích xuất giá), `src/retrieval/product_retriever.py` (`_build_where_clause`) |
| `intent_recall` | Parser nhận ra đủ mọi `expected_features` từ cách diễn đạt của câu hỏi | `UserIntentParser` chỉ so khớp từ khóa thuần túy (không dùng LLM) — cách diễn đạt của query không nằm trong danh sách từ khóa, hoặc `expected_features` của test case dùng nhãn mà parser không bao giờ sinh ra | `src/pipeline/recommend/user_intent_parser.py` (`USE_CASE_KEYWORDS`, `PRIORITY_KEYWORDS`) |
| `faithfulness` | Output LLM parse được thành JSON, không rỗng, và mọi sản phẩm gợi ý đều khớp tên với một candidate đã retrieve | Một trong: (a) LLM không trả về JSON hợp lệ (`response_parser` fallback về `{"structured": False, "text": ...}`), (b) `recommendations` trả về rỗng, hoặc (c) LLM đổi tên/bịa ra sản phẩm không khớp chính xác tên (`name`) của candidate đã retrieve | `src/generation/response_parser.py`, `src/generation/prompt_templates/recommend_prompt.py`, và kiểm tra xem lời gọi LLM có thành công hay không (API key, provider, rate limit) |

`faithfulness` bằng đúng `0.0` ở *mọi* case (chứ không phải một giá trị
trung gian như `0.5`) là tín hiệu quan trọng nhất cần kiểm tra trước — nó
nghĩa là bước generation hoàn toàn không tạo ra output dùng được, chứ
không phải chỉ vài tên sản phẩm bị lệch. Chạy lại với
`--output evaluation/report.json` rồi xem trường `"error"` của từng case
trong JSON: nếu `pipeline.run()` raise exception (lỗi auth, hết quota,
network), nội dung lỗi sẽ được ghi ở đó thay vì một điểm số trung gian.

Ngược lại, `relevance`/`budget_fit`/`intent_recall` quanh mức `0.5` trên
một catalog vừa seed hoặc còn ít dữ liệu thường chỉ phản ánh catalog chưa
đủ sản phẩm ở category/khoảng giá đó, chứ không hẳn là lỗi logic retrieval.
Kiểm tra `data/raw/products` và chạy `scripts/seed.py` / `scripts/ingest.py`
trước khi kết luận là logic sai.

Các tham số CLI:

| Tham số | Mặc định | Mô tả |
| ------- | -------- | ----- |
| `--test-cases` | `evaluation/test_case/test_cases_recommend.json` | Đường dẫn tới file test case JSON |
| `--top-k` | `5` | `top_k` truyền vào pipeline |
| `--pass-threshold` | `0.7` | Điểm trung bình cần đạt để case được tính là pass |
| `--config` | `configs/settings.yaml` | File cấu hình pipeline YAML |
| `--output` | *(không có)* | Đường dẫn tuỳ chọn để ghi report đầy đủ dạng JSON |

```bash
# Tùy chỉnh top_k / ngưỡng pass, lưu report đầy đủ ra JSON
uv run python evaluation/eval_recommend.py \
  --top-k 3 \
  --pass-threshold 0.6 \
  --output evaluation/report.json
```

Nếu pipeline của một case bị lỗi khi chạy (vd: hết quota LLM, DB down),
evaluator sẽ bắt lỗi, chấm cả 4 metric bằng `0.0`, ghi lại nội dung lỗi vào
case đó, rồi tiếp tục với các case còn lại thay vì dừng cả lượt chạy.

`eval_compare.py` vẫn là TODO stub — chưa được nối với `ComparePipeline`.
