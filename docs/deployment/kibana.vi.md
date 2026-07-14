# Xem dữ liệu trong Kibana

## Tổng quan

Hướng dẫn thực hành để duyệt và truy vấn index keyword Elasticsearch (`product_chunks`) trong Kibana — dùng Dev Tools, Discover và bộ lọc KQL để đọc dữ liệu đã index.

Kibana là web UI để duyệt và query index keyword Elasticsearch
(`product_chunks`) — có thể xem như "DBeaver cho Elasticsearch" trong stack này.
Trang này là hướng dẫn thực hành để xem dữ liệu trong index.

!!! info "Chỉ để đọc (read-only)"
    `product_chunks` là index **dẫn xuất**: nó được dựng lại từ source of truth
    `product_catalog` bởi các CDC sync worker (xem
    [sync_worker.py](../scripts/sync-worker.vi.md)). Dùng Kibana để **đọc** dữ
    liệu — đừng tạo/sửa/xóa document ở đây, vì event CDC kế tiếp sẽ ghi đè thay
    đổi của bạn và index sẽ lệch khỏi catalog. Muốn đổi dữ liệu sản phẩm, hãy gọi
    `POST/PUT/DELETE /api/products`.

## 1. Khởi động Kibana & mở lên

Kibana nằm trong stack Compose. Khởi động nó (Elasticsearch phải chạy trước):

```bash
cd docker
docker compose up -d kibana
```

Mất ~30–60s để sẵn sàng. Mở `http://localhost:5601`, ở màn hình chào bấm
**"Explore on my own"** để bỏ qua phần onboarding.

Không cần đăng nhập — stack dev chạy Elasticsearch với security đã tắt.

## 2. Kiểm tra nhanh — Dev Tools

Cách nhanh nhất để xác nhận có dữ liệu là console **Dev Tools**, nơi gửi request
thô tới Elasticsearch.

Mở menu ☰ (góc trên trái) → **Management → Dev Tools** (hoặc vào thẳng
`http://localhost:5601/app/dev_tools`). Dán từng lệnh và chạy bằng nút ▶ (hoặc
`Ctrl`/`Cmd`+`Enter`):

```
GET _cat/indices?v

GET product_chunks/_count

GET product_chunks/_search
{
  "query": { "match_all": {} },
  "size": 5
}
```

- Nếu thấy `hits` có document → index đã có dữ liệu.
- `index_not_found_exception` hoặc `count` = `0` → **chưa có dữ liệu**. Chạy
  `docker compose exec app uv run python scripts/ingest.py` rồi thử lại. Nếu vẫn
  rỗng, kiểm tra indexer worker: `docker compose logs -f indexer-worker`.

## 3. Xem dạng bảng — Discover

**Discover** hiển thị document dạng bảng có thể sắp xếp và lọc.

1. Menu ☰ → **Analytics → Discover**.
2. Lần đầu, Kibana yêu cầu tạo **Data View**. Bấm *Create data view*.
3. Điền:
    - **Name**: tùy ý, ví dụ `product_chunks`
    - **Index pattern**: `product_chunks`
    - **Timestamp field**: chọn **"I don't want to use the time filter"** (index này không có trường thời gian)
4. Bấm *Save data view to Kibana*.

Giờ bạn thấy các document. Ở sidebar bên trái, bấm một field để xem các giá trị
phổ biến, hoặc dùng **+** để thêm nó thành cột (ví dụ `product_id`, `chunk_type`,
`brand`, `price`).

### Lọc trong Discover (KQL)

Thanh tìm kiếm dùng **KQL** (Kibana Query Language). Ví dụ:

```
brand : "apple"
category : "smartphone" and price <= 15000000
chunk_type : "specifications"
document : *camera*
product_id : "tgdd-iphone-17-pro-max"
```

!!! note "brand / category viết thường"
    `brand` và `category` là field `keyword` được index qua lowercase
    normalizer, nên hãy so khớp bằng chữ thường (`"apple"`, không phải
    `"Apple"`).

## 4. Hiểu cấu trúc document

Mỗi sản phẩm được tách thành nhiều chunk, mỗi chunk là một document
Elasticsearch. `_id` của document là `{product_id}_{chunk_type}` (ví dụ
`tgdd-iphone-17-pro-max_specifications`), nên một sản phẩm tạo ra nhiều dòng
trong `product_chunks`.

| Field | Kiểu | Ý nghĩa |
| ----- | ---- | ------- |
| `document` | text | Văn bản chunk (được full-text search bằng BM25) |
| `product_id` | keyword | Sản phẩm mà chunk này thuộc về |
| `chunk_type` | keyword | `description`, `specifications`, `pros_cons`, `review` |
| `brand` | keyword | Thương hiệu (viết thường) — field lọc |
| `category` | keyword | Danh mục (viết thường) — field lọc |
| `price` | double | Giá (VND) — lọc theo khoảng |
| `avg_rating` | float | Điểm đánh giá trung bình — lọc theo khoảng |
| `content_hash` | keyword | Hash của các text field — giúp CDC bỏ qua re-embedding khi không đổi |

Xem mapping bất cứ lúc nào bằng:

```
GET product_chunks/_mapping
```

## 5. Các query Dev Tools hữu ích

Các query này phản chiếu đúng những gì nhánh keyword của API chạy
(`ESKeywordSearch`).

```
# Full-text (BM25) trên văn bản chunk
GET product_chunks/_search
{ "query": { "match": { "document": "chụp ảnh đẹp" } } }

# BM25 + filter (đúng dạng bool query của app)
GET product_chunks/_search
{
  "query": {
    "bool": {
      "must":   [{ "match": { "document": "gaming" } }],
      "filter": [
        { "term":  { "brand": "asus" } },
        { "range": { "price": { "lte": 25000000 } } }
      ]
    }
  }
}

# Tất cả chunk của một sản phẩm
GET product_chunks/_search
{ "query": { "term": { "product_id": "tgdd-iphone-17-pro-max" } } }

# Lấy một document chunk theo id
GET product_chunks/_doc/tgdd-iphone-17-pro-max_description

# Có bao nhiêu document theo từng chunk_type?
GET product_chunks/_search
{
  "size": 0,
  "aggs": { "by_type": { "terms": { "field": "chunk_type" } } }
}
```

## 6. Xử lý sự cố

| Triệu chứng | Nguyên nhân & cách xử lý |
| ----------- | ------------------------ |
| Kibana không load / `Kibana server is not ready yet` | Còn đang khởi động, hoặc Elasticsearch đang down. Đợi ~1 phút rồi xem `docker compose logs elasticsearch kibana`. |
| `index_not_found_exception` cho `product_chunks` | Chưa nạp dữ liệu. Chạy `scripts/ingest.py` (hoặc xem log indexer worker). |
| `_count` bằng 0 nhưng catalog đã có sản phẩm | Indexer worker không consume. Xem `docker compose logs -f indexer-worker` và Kafka consumer lag (xem [Docker](docker.vi.md#kafka-topic-consumer-lag)). |
| Filter `term` trên `brand`/`category` không ra gì | Dùng chữ thường — các field đó được normalize (`"apple"`, `"smartphone"`). |

## Liên quan

- [Triển khai với Docker](docker.vi.md) — chạy full stack, gồm cả Kibana.
- [sync_worker.py](../scripts/sync-worker.vi.md) — cách `product_chunks` được giữ đồng bộ qua CDC.
- [Truy xuất lai](../architecture/hybrid-retrieval.vi.md) — cách index keyword được dùng lúc query.
