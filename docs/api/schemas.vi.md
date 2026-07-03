# Schema Request & Response

Tất cả schema được định nghĩa dưới dạng Pydantic model trong `api/schemas.py`.

## Request Models

### RecommendRequest

```python
class RecommendRequest(BaseModel):
    query: str                    # Truy vấn ngôn ngữ tự nhiên
    top_k: int = 5               # Số lượng kết quả
    filters: dict | None = None  # Ghi đè filter tùy chọn
```

### CompareRequest

```python
class CompareRequest(BaseModel):
    query: str | None = None           # Truy vấn so sánh bằng ngôn ngữ tự nhiên
    product_ids: list[str] | None = None  # Hoặc ID sản phẩm cụ thể
```

### SearchRequest

```python
class SearchRequest(BaseModel):
    query: str                    # Truy vấn tìm kiếm
    filters: dict | None = None  # Filter metadata
    limit: int = 10              # Số kết quả tối đa
```

## Response Models

### RecommendResponse

```python
class RecommendResponse(BaseModel):
    recommendations: list[dict]  # Danh sách sản phẩm đã xếp hạng
    summary: str = ""            # Tóm tắt tổng quan
```

### CompareResponse

```python
class CompareResponse(BaseModel):
    comparison_table: dict       # Bảng thông số đã đối chiếu
    analysis: dict               # Phân tích của LLM
    conclusion: str = ""         # Kết luận cuối cùng
```

### SearchResponse

```python
class SearchResponse(BaseModel):
    results: list[dict]          # Kết quả tìm kiếm kèm điểm số
    total: int = 0               # Tổng số kết quả khớp
```
