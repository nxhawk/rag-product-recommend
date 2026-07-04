"""Script: Ingest product data vao vector store."""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.product_loader import ProductLoader
from src.ingestion.data_cleaner import DataCleaner
from src.ingestion.chunker import ProductChunker
from src.embedding.product_embedder import ProductEmbedder
from src.embedding.vector_store import VectorStore
from src.pipeline.config import PipelineConfig
from src.utils.helpers import resolve_api_keys
from src.utils.logger import setup_logger

logger = setup_logger("ingest")


def main():
    # Load environment variables from .env before any os.getenv lookups.
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Ingest product data into the vector store."
    )
    parser.add_argument(
        "--source",
        choices=["crawled", "products", "all"],
        default="crawled",
        help=(
            "Where to read products from: 'crawled' (data/raw/crawled/*/latest.json), "
            "'products' (data/raw/products), or 'all' (both). Default: crawled."
        ),
    )
    args = parser.parse_args()

    config = PipelineConfig.from_yaml("configs/settings.yaml")

    loader = ProductLoader()
    cleaner = DataCleaner()
    chunker = ProductChunker()

    embedder = ProductEmbedder(
        model_name=config.embedding_model,
        provider=config.embedding_provider,
        embedding_dim=config.embedding_dim,
    )
    key_env = ProductEmbedder.PROVIDER_API_KEY_ENV.get(
        config.embedding_provider, "OPENAI_API_KEY"
    )
    embedder.setup(api_key=resolve_api_keys(key_env) or [""])

    store = VectorStore(
        collection_name=config.collection_name,
        embedding_dim=config.embedding_dim,
    )
    store.setup(dsn=config.vector_db_url)

    logger.info(f"Loading products (source={args.source})...")
    if args.source == "crawled":
        raw_products = loader.load_crawled()
    elif args.source == "products":
        raw_products = loader.load_all()
    else:  # "all"
        raw_products = loader.load_all() + loader.load_crawled()
    logger.info(f"Loaded {len(raw_products)} products")

    all_chunks = []
    for raw in raw_products:
        product = cleaner.build_product_profile(raw)
        chunks = chunker.chunk_product(product)
        all_chunks.extend(chunks)

    logger.info(f"Created {len(all_chunks)} chunks, embedding...")

    texts = [c["text"] for c in all_chunks]
    embeddings = embedder.embed_batch(texts)

    ids = [f"{c['product_id']}_{c['chunk_type']}" for c in all_chunks]
    metadatas = [
        {k: v for k, v in c.items() if k != "text"}
        for c in all_chunks
    ]

    store.add_documents(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    logger.info("Ingestion complete!")


if __name__ == "__main__":
    main()
