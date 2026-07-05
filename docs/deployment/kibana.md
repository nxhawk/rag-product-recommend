# Viewing Data in Kibana

Kibana is the web UI for browsing and querying the Elasticsearch keyword index
(`product_chunks`) — think of it as the "DBeaver for Elasticsearch" in this
stack. This page is a hands-on guide to inspecting the index.

!!! info "Read-only by design"
    `product_chunks` is a **derived** index: it is rebuilt from the
    `product_catalog` source of truth by the CDC sync workers (see
    [sync_worker.py](../scripts/sync-worker.md)). Use Kibana to **read** the
    data — never create/edit/delete documents here, because the next CDC event
    would overwrite your change and the index would drift from the catalog. To
    change product data, call `POST/PUT/DELETE /api/products`.

## 1. Start Kibana & open it

Kibana is part of the Compose stack. Start it (Elasticsearch must be up first):

```bash
cd docker
docker compose up -d kibana
```

It takes ~30–60s to become ready. Open `http://localhost:5601`, and on the
welcome screen click **"Explore on my own"** to skip the onboarding.

No login is required — the dev stack runs Elasticsearch with security disabled.

## 2. Quick check — Dev Tools

The fastest way to confirm data exists is the **Dev Tools** console, which sends
raw requests to Elasticsearch.

Open the menu ☰ (top-left) → **Management → Dev Tools** (or go straight to
`http://localhost:5601/app/dev_tools`). Paste each command and run it with the
▶ button (or `Ctrl`/`Cmd`+`Enter`):

```
GET _cat/indices?v

GET product_chunks/_count

GET product_chunks/_search
{
  "query": { "match_all": {} },
  "size": 5
}
```

- If you see `hits` with documents → the index is populated.
- `index_not_found_exception` or `count` = `0` → **no data yet**. Run
  `docker compose exec app uv run python scripts/ingest.py`, then retry. If it's
  still empty, check the indexer worker: `docker compose logs -f indexer-worker`.

## 3. Browse as a grid — Discover

**Discover** shows documents in a table you can sort and filter.

1. Menu ☰ → **Analytics → Discover**.
2. The first time, Kibana asks you to create a **Data View**. Click *Create data view*.
3. Fill in:
    - **Name**: anything, e.g. `product_chunks`
    - **Index pattern**: `product_chunks`
    - **Timestamp field**: choose **"I don't want to use the time filter"** (this index has no time field)
4. Click *Save data view to Kibana*.

You now see the documents. In the left sidebar, click a field to see its top
values, or use the **+** to add it as a column (e.g. `product_id`, `chunk_type`,
`brand`, `price`).

### Filtering in Discover (KQL)

The search bar uses **KQL** (Kibana Query Language). Examples:

```
brand : "apple"
category : "smartphone" and price <= 15000000
chunk_type : "specifications"
document : *camera*
product_id : "tgdd-iphone-17-pro-max"
```

!!! note "brand / category are lowercased"
    `brand` and `category` are `keyword` fields indexed through a lowercase
    normalizer, so match them in lower case (`"apple"`, not `"Apple"`).

## 4. Understanding the documents

Each product is split into several chunks, one Elasticsearch document per chunk.
The document `_id` is `{product_id}_{chunk_type}` (e.g.
`tgdd-iphone-17-pro-max_specifications`), so a single product produces multiple
rows in `product_chunks`.

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `document` | text | The chunk text (full-text searched with BM25) |
| `product_id` | keyword | Product this chunk belongs to |
| `chunk_type` | keyword | `description`, `specifications`, `pros_cons`, `review` |
| `brand` | keyword | Lower-cased brand (filter field) |
| `category` | keyword | Lower-cased category (filter field) |
| `price` | double | Price in VND (range filter) |
| `avg_rating` | float | Average rating (range filter) |
| `content_hash` | keyword | Hash of the text fields — lets CDC skip re-embedding when unchanged |

See the mapping any time with:

```
GET product_chunks/_mapping
```

## 5. Useful Dev Tools queries

These mirror what the API's keyword branch runs (`ESKeywordSearch`).

```
# Full-text (BM25) search on the chunk text
GET product_chunks/_search
{ "query": { "match": { "document": "chụp ảnh đẹp" } } }

# BM25 + filters (same shape as the app's bool query)
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

# All chunks of one product
GET product_chunks/_search
{ "query": { "term": { "product_id": "tgdd-iphone-17-pro-max" } } }

# Fetch a single chunk document by id
GET product_chunks/_doc/tgdd-iphone-17-pro-max_description

# How many documents per chunk_type?
GET product_chunks/_search
{
  "size": 0,
  "aggs": { "by_type": { "terms": { "field": "chunk_type" } } }
}
```

## 6. Troubleshooting

| Symptom | Cause & fix |
| ------- | ----------- |
| Kibana won't load / `Kibana server is not ready yet` | Still starting, or Elasticsearch is down. Wait ~1 min, then check `docker compose logs elasticsearch kibana`. |
| `index_not_found_exception` for `product_chunks` | Nothing ingested yet. Run `scripts/ingest.py` (or check the indexer worker logs). |
| `_count` is 0 but the catalog has products | The indexer worker isn't consuming. Check `docker compose logs -f indexer-worker` and the Kafka consumer lag (see [Docker](docker.md#kafka-topics-consumer-lag)). |
| A `term` filter on `brand`/`category` returns nothing | Use lower case — those fields are normalized (`"apple"`, `"smartphone"`). |

## Related

- [Docker Deployment](docker.md) — running the full stack, including Kibana.
- [sync_worker.py](../scripts/sync-worker.md) — how `product_chunks` is kept in sync via CDC.
- [Hybrid Retrieval](../architecture/hybrid-retrieval.md) — how the keyword index is used at query time.
