# Xem Kafka trong Kafka UI

## Tổng quan

Hướng dẫn thực hành để soi pipeline CDC qua web dashboard Kafka UI — duyệt topic và message, theo dõi consumer-group lag, và kiểm tra Debezium connector.

Kafka UI ([kafbat/kafka-ui](https://ui.docs.kafbat.io/)) là web dashboard để duyệt
broker Kafka trong stack này — có thể xem như "Kibana cho Kafka". Nó hiển thị các
topic cùng message trực tiếp, consumer-group lag, và trạng thái Debezium
connector, tất cả ở một nơi. Trang này là hướng dẫn thực hành để xem pipeline CDC
qua nó.

!!! info "Chỉ để quan sát (read-only)"
    Các topic CDC (ví dụ `ragshop.public.product_catalog`) do **Debezium** sinh ra
    từ source of truth `product_catalog` và được các
    [sync worker](../scripts/sync-worker.vi.md) consume. Dùng Kafka UI để **quan
    sát** pipeline — đừng tự tay produce message lên các topic này, vì event
    Debezium kế tiếp sẽ ghi đè và các index sẽ bị lệch. Muốn đổi dữ liệu sản phẩm,
    hãy gọi `POST/PUT/DELETE /api/products`.

## 1. Khởi động Kafka UI & mở lên

Kafka UI nằm trong stack Compose. Khởi động nó (Kafka và Debezium Connect phải
chạy trước — Compose chặn nó theo health check của chúng):

```bash
cd docker
docker compose up -d kafka-ui
```

Chỉ vài giây là sẵn sàng. Mở `http://localhost:8080` — không cần đăng nhập (stack
dev chạy với security đã tắt). Nó được nối sẵn tới một cluster tên **`rag`**
(`KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS=kafka:9092`) cùng endpoint Kafka Connect
**`debezium`** (`http://connect:8083`) đã đăng ký sẵn, nên không cần cấu hình gì.

## 2. Kiểm tra nhanh — cluster đã online chưa?

Ở **Dashboard** (trang chính) bạn sẽ thấy cluster `rag` được đánh dấu **online**
với số broker là **1**, cùng tổng số topic, partition và consumer. Nếu báo
*offline*, nghĩa là Kafka chưa sẵn sàng lúc UI khởi động — xem
`docker compose logs kafka-ui` và kiểm tra `kafka` đã healthy chưa.

## 3. Duyệt topic & message

Ở sidebar bên trái, **`rag` → Topics** liệt kê mọi topic. Những topic đáng chú ý
ở đây:

| Topic | Được sinh bởi | Ý nghĩa |
| ----- | ------------- | ------- |
| `ragshop.public.product_catalog` | Debezium | Mỗi change event ứng với một lần insert/update/delete row catalog — luồng CDC mà cả hai sync worker consume |
| `rag_connect_configs` / `rag_connect_offsets` / `rag_connect_statuses` | Kafka Connect | Trạng thái nội bộ của Connect (config connector, offset, status task) |
| `__consumer_offsets`, `__transaction_state` | Kafka | Topic nội bộ của broker |

Bấm **`ragshop.public.product_catalog`**, rồi tab **Messages** để xem các change
event. Mỗi message là một envelope Debezium: `payload.op` là loại thao tác (`c`
create, `u` update, `d` delete, `r` snapshot read), và `payload.after` chứa row
mới. Dùng bộ lọc phía trên để tìm theo offset, partition hoặc timestamp khi bạn
lần theo một lần ghi cụ thể.

## 4. Theo dõi consumer lag (cửa sổ eventual-consistency)

**`rag` → Consumers** liệt kê các consumer group. Mỗi sync worker một group:

| Group | Worker | Sink |
| ----- | ------ | ---- |
| `rag-sync-indexer` | `indexer-worker` | Elasticsearch `product_chunks` |
| `rag-sync-embedder` | `embedding-worker` | pgvector `products` |

Mở một group để xem **lag** theo từng partition — worker còn phải xử lý bao nhiêu
message. Lag đó đúng bằng cửa sổ eventual-consistency giữa lúc ghi catalog và lúc
index tìm kiếm bắt kịp. Nó nên xấp xỉ 0; lag tăng dần nghĩa là một worker đang
chết hoặc chậm (xem `docker compose logs -f indexer-worker embedding-worker`).

## 5. Kiểm tra Debezium connector

**`rag` → Kafka Connect → `debezium`** hiển thị các connector đã đăng ký trên
cluster Connect. `product-catalog-connector` phải ở trạng thái **RUNNING** với một
task cũng RUNNING. Từ đây bạn có thể xem config, pause/resume, hoặc restart một
task lỗi — đúng các thao tác như REST API thô
(`curl http://localhost:8083/connectors/product-catalog-connector/status`) nhưng
không cần rời trình duyệt.

Nếu thiếu connector, nghĩa là `connect-init` chưa đăng ký nó — chạy lại
`docker compose up -d connect-init` (xem [Docker](docker.vi.md)).

## 6. Xử lý sự cố

| Triệu chứng | Nguyên nhân & cách xử lý |
| ----------- | ------------------------ |
| Dashboard báo cluster **offline** | Kafka chưa sẵn sàng lúc khởi động, hoặc `KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS` sai. Đợi rồi xem `docker compose logs kafka-ui` và `docker compose ps kafka`. |
| Không có topic `ragshop.public.product_catalog` | Debezium chưa snapshot. Kiểm tra connector ở **Kafka Connect** và `docker compose logs connect connect-init`. |
| Topic có nhưng tab **Messages** rỗng | Chưa nạp dữ liệu. Chạy `docker compose exec app uv run python scripts/ingest.py`. |
| Lag consumer-group cứ tăng | Một sync worker đang chết hoặc chậm. Xem `docker compose logs -f indexer-worker embedding-worker`. |
| Tab **Kafka Connect** rỗng | UI không kết nối được tới Connect. Kiểm tra `KAFKA_CLUSTERS_0_KAFKACONNECT_0_ADDRESS=http://connect:8083` và `connect` đã healthy chưa. |

## Liên quan

- [Triển khai với Docker](docker.vi.md) — chạy full stack, gồm cả Kafka UI.
- [Xem dữ liệu trong Kibana](kibana.vi.md) — UI tương đương cho index Elasticsearch.
- [sync_worker.py](../scripts/sync-worker.vi.md) — các consumer đứng sau nhóm `rag-sync-*`.
- [Đồng bộ CDC](../architecture/cdc.vi.md) — cách change event chảy từ Postgres tới các index.
