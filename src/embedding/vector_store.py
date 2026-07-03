"""
Vector Store - Manage connection and operations with the vector database.
Backend: PostgreSQL + pgvector (cosine similarity).
"""
import json
import os
import re
from typing import Any, Optional

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rag_products"


class VectorStore:
    """Manage vector database operations backed by Postgres + pgvector."""

    def __init__(
        self,
        provider: str = "pgvector",
        collection_name: str = "products",
        embedding_dim: int = 1536,
    ):
        self.provider = provider
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.conn = None
        # Sanitize collection name to a safe SQL identifier
        self.table_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)

    def setup(self, **kwargs) -> None:
        """Initialize the Postgres connection, extension, table and index.

        Connection string resolution order:
        1. ``dsn`` keyword argument
        2. ``DATABASE_URL`` environment variable
        3. Local default (``localhost:5432/rag_products``)
        """
        import psycopg
        from pgvector.psycopg import register_vector

        dsn = kwargs.get("dsn") or os.getenv("DATABASE_URL", DEFAULT_DSN)
        self.conn = psycopg.connect(dsn, autocommit=True)
        self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self.conn)
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id TEXT PRIMARY KEY,
                document TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                embedding vector({self.embedding_dim}) NOT NULL
            )
            """
        )
        self.conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx
            ON {self.table_name}
            USING hnsw (embedding vector_cosine_ops)
            """
        )

    def add_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Upsert documents with embeddings into the store."""
        with self.conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO {self.table_name} (id, document, metadata, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    document = EXCLUDED.document,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding
                """,
                [
                    (doc_id, doc, json.dumps(meta, ensure_ascii=False), str(emb))
                    for doc_id, doc, meta, emb in zip(
                        ids, documents, metadatas, embeddings
                    )
                ],
            )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> dict:
        """Query similar documents by cosine distance.

        Returns a dict shaped like ``{"ids": [[...]], "documents": [[...]],
        "metadatas": [[...]], "distances": [[...]]}`` (one nested list per
        query) so downstream consumers can iterate results uniformly.
        """
        where_sql, params = self._build_where_sql(where)
        sql = f"""
            SELECT id, document, metadata,
                   embedding <=> %s::vector AS distance
            FROM {self.table_name}
            {where_sql}
            ORDER BY distance ASC
            LIMIT %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, [str(query_embedding), *params, n_results])
            rows = cur.fetchall()

        return {
            "ids": [[row[0] for row in rows]],
            "documents": [[row[1] for row in rows]],
            "metadatas": [[row[2] for row in rows]],
            "distances": [[float(row[3]) for row in rows]],
        }

    def delete_collection(self) -> None:
        """Drop the table backing the current collection."""
        self.conn.execute(f"DROP TABLE IF EXISTS {self.table_name}")

    def close(self) -> None:
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _build_where_sql(self, where: Optional[dict]) -> tuple[str, list[Any]]:
        """Translate a metadata filter dict into a SQL WHERE clause.

        Supports simple equality filters (``{"brand": "Apple"}``) and
        ``{"$and": [{...}, {...}]}`` composites over JSONB metadata.
        """
        if not where:
            return "", []

        conditions = where.get("$and", [where]) if isinstance(where, dict) else []
        clauses: list[str] = []
        params: list[Any] = []
        for condition in conditions:
            for key, value in condition.items():
                clauses.append("metadata->>%s = %s")
                params.extend([key, str(value)])
        if not clauses:
            return "", []
        return "WHERE " + " AND ".join(clauses), params
