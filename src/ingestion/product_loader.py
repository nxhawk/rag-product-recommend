"""
Product Loader - Đọc dữ liệu sản phẩm từ nhiều nguồn/format.
Hỗ trợ: JSON, CSV, API, crawl data.
"""
import csv
import json
from pathlib import Path


class ProductLoader:
    """Load product data from various sources."""

    def __init__(self, data_dir: str = "data/raw/products"):
        self.data_dir = Path(data_dir)

    def load_json(self, filepath: str) -> list[dict]:
        """Load products from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_csv(self, filepath: str) -> list[dict]:
        """Load products from a CSV file."""
        products = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(dict(row))
        return products

    def load_file(self, filepath: str | Path) -> list[dict]:
        """Load a single product file, dispatching on its extension."""
        path = Path(filepath)
        if path.suffix == ".json":
            return self.load_json(str(path))
        if path.suffix == ".csv":
            return self.load_csv(str(path))
        return []

    def load_all(self) -> list[dict]:
        """Load every JSON/CSV file in the (flat) data directory."""
        all_products: list[dict] = []
        for file in sorted(self.data_dir.iterdir()):
            all_products.extend(self.load_file(file))
        return all_products

    def load_crawled(
        self,
        crawled_dir: str = "data/raw/crawled",
        filename: str = "latest.json",
    ) -> list[dict]:
        """Load crawled products - one ``latest.json`` per source subfolder.

        The crawler writes ``data/raw/crawled/<source>/latest.json`` alongside
        timestamped snapshots; only each source's ``latest.json`` is read so the
        older snapshots are not double-counted.
        """
        all_products: list[dict] = []
        for file in sorted(Path(crawled_dir).glob(f"*/{filename}")):
            all_products.extend(self.load_json(str(file)))
        return all_products
