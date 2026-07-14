# seed.py — Luồng chạy

## Tổng quan

Mô tả luồng chạy của `seed.py`, script placeholder để seed dữ liệu development mẫu, cùng cách thay thế bằng pipeline thật cho tới khi nó được cài đặt.

Seed dữ liệu sản phẩm mẫu cho development. Hiện tại là placeholder — logic
seeding chưa được cài đặt.

```bash
uv run python scripts/seed.py
```

## Sơ đồ luồng

```mermaid
flowchart TB
    MAIN["main()<br/><i>scripts/seed.py</i>"] --> LOG["setup_logger('seed')<br/><i>src/utils/logger.py</i>"]
    MAIN --> TODO["TODO: logic seeding<br/>(chưa cài đặt)"]
```

## Từng bước

| # | Bước | Function | File |
|---|------|----------|------|
| 1 | Tạo logger | `setup_logger()` | `src/utils/logger.py` |
| 2 | Log bắt đầu/kết thúc; logic seeding còn là `TODO` | `main()` | `scripts/seed.py` |

## Cách thay thế hiện tại

Trong khi chưa có seeding, hãy nạp dữ liệu development bằng pipeline thật:

```bash
uv run python scripts/crawl.py --all
uv run python scripts/ingest.py --source crawled
```

Hoặc bỏ file JSON/CSV mẫu vào `data/raw/products/` rồi chạy
`uv run python scripts/ingest.py --source products`.
