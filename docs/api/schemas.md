# Request & Response Schemas

All schemas are defined as Pydantic models in `api/schemas.py`.

## Request Models

### RecommendRequest

```python
class RecommendRequest(BaseModel):
    query: str                    # Natural language query
    top_k: int = 5               # Number of results
    filters: dict | None = None  # Optional filter overrides
```

### CompareRequest

```python
class CompareRequest(BaseModel):
    query: str | None = None           # NL comparison query
    product_ids: list[str] | None = None  # Or specific product IDs
```

### SearchRequest

```python
class SearchRequest(BaseModel):
    query: str                    # Search query
    filters: dict | None = None  # Metadata filters
    limit: int = 10              # Max results
```

## Response Models

### RecommendResponse

```python
class RecommendResponse(BaseModel):
    recommendations: list[dict]  # Ranked product list
    summary: str = ""            # Overall summary
```

### CompareResponse

```python
class CompareResponse(BaseModel):
    comparison_table: dict       # Aligned specs table
    analysis: dict               # LLM analysis
    conclusion: str = ""         # Final verdict
```

### SearchResponse

```python
class SearchResponse(BaseModel):
    results: list[dict]          # Search results with scores
    total: int = 0               # Total matches
```
