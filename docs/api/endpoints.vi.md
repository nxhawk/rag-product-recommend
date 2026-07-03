# API Endpoints

Base URL: `http://localhost:8000`

## Health Check

```
GET /health
```

**Response:**
```json
{"status": "ok"}
```

## Gợi ý sản phẩm

```
POST /api/recommend
```

Tìm các sản phẩm khớp với truy vấn ngôn ngữ tự nhiên của người dùng.

**Request Body:**

| Trường    | Kiểu   | Bắt buộc | Mặc định | Mô tả                    |
| --------- | ------ | -------- | ------- | ------------------------------ |
| `query`   | string | Có      | —       | Truy vấn sản phẩm bằng ngôn ngữ tự nhiên |
| `top_k`   | int    | Không       | 5       | Số lượng gợi ý      |
| `filters` | object | Không       | null    | Ghi đè filter bổ sung     |

**Ví dụ:**

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"query": "Phone with great camera under 15 million VND", "top_k": 3}'
```

**Response:**

```json
{
  "recommendations": [
    {
      "name": "Xiaomi 14",
      "price": 13990000,
      "reason": "Leica camera system with competitive pricing",
      "pros": ["Leica camera quality", "Great value", "90W fast charging"],
      "cons": ["HyperOS has ads"],
      "best_for": "Photography enthusiasts on a budget"
    }
  ],
  "summary": "Top picks based on camera quality within your budget"
}
```

## So sánh sản phẩm

```
POST /api/compare
```

So sánh hai hoặc nhiều sản phẩm cạnh nhau.

**Request Body:**

| Trường         | Kiểu     | Bắt buộc | Mô tả                         |
| ------------- | -------- | -------- | ----------------------------------- |
| `query`       | string   | Không       | Truy vấn so sánh bằng ngôn ngữ tự nhiên   |
| `product_ids` | string[] | Không       | ID sản phẩm cụ thể cần so sánh     |

Cung cấp `query` hoặc `product_ids` (cần ít nhất một trong hai).

**Ví dụ:**

```bash
curl -X POST http://localhost:8000/api/compare \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare iPhone 15 Pro Max vs Samsung Galaxy S24 Ultra"}'
```

**Response:**

```json
{
  "comparison_table": {
    "fields": ["processor", "ram", "battery", "rear_camera"],
    "products": [...]
  },
  "analysis": {
    "criteria_comparison": [...],
    "product_analysis": [...]
  },
  "conclusion": "Summary of which product suits which use case"
}
```

## Tìm kiếm sản phẩm

```
POST /api/search
```

Tìm kiếm sản phẩm theo truy vấn kèm filter tùy chọn.

**Request Body:**

| Trường    | Kiểu   | Bắt buộc | Mặc định | Mô tả            |
| --------- | ------ | -------- | ------- | ---------------------- |
| `query`   | string | Có      | —       | Truy vấn tìm kiếm           |
| `filters` | object | Không       | null    | Filter metadata       |
| `limit`   | int    | Không       | 10      | Số kết quả tối đa trả về  |

**Response:**

```json
{
  "results": [
    {
      "id": "iphone-15-pro-max",
      "document": "iPhone 15 Pro Max - Apple...",
      "metadata": {"brand": "Apple", "price": 29990000},
      "score": 0.92
    }
  ],
  "total": 1
}
```
