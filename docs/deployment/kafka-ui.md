# Viewing Kafka in Kafka UI

## Overview

A hands-on guide to inspecting the CDC pipeline through the Kafka UI web dashboard — browsing topics and messages, watching consumer-group lag, and checking the Debezium connector.

Kafka UI ([kafbat/kafka-ui](https://ui.docs.kafbat.io/)) is the web dashboard for
browsing the Kafka broker in this stack — think of it as the "Kibana for Kafka".
It shows topics and their live messages, consumer-group lag, and the state of the
Debezium connector, all in one place. This page is a hands-on guide to inspecting
the CDC pipeline through it.

!!! info "Read-only by intent"
    The CDC topics (e.g. `ragshop.public.product_catalog`) are produced by
    **Debezium** from the `product_catalog` source of truth and consumed by the
    [sync workers](../scripts/sync-worker.md). Use Kafka UI to **observe** the
    pipeline — don't hand-produce messages onto these topics, because the next
    Debezium event would overwrite the effect and the indexes would drift. To
    change product data, call `POST/PUT/DELETE /api/products`.

## 1. Start Kafka UI & open it

Kafka UI is part of the Compose stack. Start it (Kafka and Debezium Connect must
be up first — Compose gates it on their health checks):

```bash
cd docker
docker compose up -d kafka-ui
```

It's ready in a few seconds. Open `http://localhost:8080` — no login is required
(the dev stack runs with security disabled). It's pre-wired to one cluster named
**`rag`** (`KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS=kafka:9092`) with the Debezium
**`debezium`** Kafka Connect endpoint (`http://connect:8083`) already registered,
so there is nothing to configure.

## 2. Quick check — is the cluster online?

On the **Dashboard** (landing page) you should see the `rag` cluster marked
**online** with a broker count of **1**, plus totals for topics, partitions and
consumers. If it shows *offline*, Kafka wasn't ready when the UI started — check
`docker compose logs kafka-ui` and that `kafka` is healthy.

## 3. Browse topics & messages

In the left sidebar, **`rag` → Topics** lists every topic. The ones that matter
here:

| Topic | Produced by | Meaning |
| ----- | ----------- | ------- |
| `ragshop.public.product_catalog` | Debezium | One change event per catalog row insert/update/delete — the CDC stream both sync workers consume |
| `rag_connect_configs` / `rag_connect_offsets` / `rag_connect_statuses` | Kafka Connect | Internal Connect state (connector config, offsets, task status) |
| `__consumer_offsets`, `__transaction_state` | Kafka | Internal broker topics |

Click **`ragshop.public.product_catalog`**, then the **Messages** tab to see the
change events. Each message is a Debezium envelope: `payload.op` is the operation
(`c` create, `u` update, `d` delete, `r` snapshot read), and `payload.after`
holds the new row. Use the filters at the top to seek by offset, partition or
timestamp when you're tracing a specific write.

## 4. Watch consumer lag (the eventual-consistency window)

**`rag` → Consumers** lists the consumer groups. There is one per sync worker:

| Group | Worker | Sink |
| ----- | ------ | ---- |
| `rag-sync-indexer` | `indexer-worker` | Elasticsearch `product_chunks` |
| `rag-sync-embedder` | `embedding-worker` | pgvector `products` |

Open a group to see its per-partition **lag** — how many messages the worker
still has to process. That lag is exactly the eventual-consistency window between
a catalog write and the search index catching up. It should hover near zero; a
growing lag means a worker is down or slow (check
`docker compose logs -f indexer-worker embedding-worker`).

## 5. Inspect the Debezium connector

**`rag` → Kafka Connect → `debezium`** shows the connectors registered on the
Connect cluster. `product-catalog-connector` should be **RUNNING** with one task
also RUNNING. From here you can view its config, pause/resume it, or restart a
failed task — the same operations as the raw REST API
(`curl http://localhost:8083/connectors/product-catalog-connector/status`), but
without leaving the browser.

If the connector is missing, `connect-init` hasn't registered it yet — re-run
`docker compose up -d connect-init` (see [Docker](docker.md)).

## 6. Troubleshooting

| Symptom | Cause & fix |
| ------- | ----------- |
| Dashboard shows the cluster **offline** | Kafka wasn't ready at startup, or `KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS` is wrong. Wait, then check `docker compose logs kafka-ui` and `docker compose ps kafka`. |
| No `ragshop.public.product_catalog` topic | Debezium hasn't snapshotted yet. Check the connector under **Kafka Connect** and `docker compose logs connect connect-init`. |
| Topic exists but **Messages** is empty | Nothing has been ingested. Run `docker compose exec app uv run python scripts/ingest.py`. |
| Consumer-group lag keeps growing | A sync worker is down or slow. Check `docker compose logs -f indexer-worker embedding-worker`. |
| **Kafka Connect** tab is empty | The UI can't reach Connect. Verify `KAFKA_CLUSTERS_0_KAFKACONNECT_0_ADDRESS=http://connect:8083` and that `connect` is healthy. |

## Related

- [Docker Deployment](docker.md) — running the full stack, including Kafka UI.
- [Viewing Data in Kibana](kibana.md) — the equivalent UI for the Elasticsearch index.
- [sync_worker.py](../scripts/sync-worker.md) — the consumers behind the `rag-sync-*` groups.
- [CDC Sync](../architecture/cdc.md) — how change events flow from Postgres to the indexes.
