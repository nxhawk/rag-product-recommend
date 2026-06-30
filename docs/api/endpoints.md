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

## Recommend Products

```
POST /api/recommend
```

Find products matching a user's natural language query.

**Request Body:**

| Field     | Type   | Required | Default | Description                    |
| --------- | ------ | -------- | ------- | ------------------------------ |
| `query`   | string | Yes      | —       | Natural language product query |
| `top_k`   | int    | No       | 5       | Number of recommendations      |
| `filters` | object | No       | null    | Additional filter overrides     |

**Example:**

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

## Compare Products

```
POST /api/compare
```

Compare two or more products side by side.

**Request Body:**

| Field         | Type     | Required | Description                         |
| ------------- | -------- | -------- | ----------------------------------- |
| `query`       | string   | No       | Natural language comparison query   |
| `product_ids` | string[] | No       | Specific product IDs to compare     |

Provide either `query` or `product_ids` (at least one required).

**Example:**

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

## Search Products

```
POST /api/search
```

Search products by query with optional filters.

**Request Body:**

| Field     | Type   | Required | Default | Description            |
| --------- | ------ | -------- | ------- | ---------------------- |
| `query`   | string | Yes      | —       | Search query           |
| `filters` | object | No       | null    | Metadata filters       |
| `limit`   | int    | No       | 10      | Max results to return  |

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
