"""Script: Crawl product data from configured sources into data/raw/crawled.

Usage:
    uv run python scripts/crawl.py --source tgdd
    uv run python scripts/crawl.py --source cellphones --category smartphone
    uv run python scripts/crawl.py --all
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler.config import CrawlerConfig
from src.crawler.pipeline import CrawlPipeline
from src.crawler.spiders import SPIDER_REGISTRY
from src.utils.logger import setup_logger

logger = setup_logger("crawl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl product data.")
    parser.add_argument(
        "--source",
        choices=sorted(SPIDER_REGISTRY.keys()),
        help="Which source to crawl.",
    )
    parser.add_argument(
        "--category",
        action="append",
        help="Category to crawl (repeatable). Defaults to all configured categories.",
    )
    parser.add_argument("--all", action="store_true", help="Crawl every enabled source.")
    parser.add_argument(
        "--config",
        default="configs/crawler.yaml",
        help="Path to crawler config YAML.",
    )
    return parser.parse_args()


def run_source(config: CrawlerConfig, name: str, categories: list[str] | None) -> None:
    spider_cls = SPIDER_REGISTRY[name]
    pipeline = CrawlPipeline(config)
    result = pipeline.run(spider_cls(), categories=categories)
    logger.info("Source '%s': crawled %d products", name, result.count)


def main() -> None:
    args = parse_args()
    config = CrawlerConfig.from_yaml(args.config)

    if args.all:
        targets = [n for n, s in config.sources.items() if s.enabled]
    elif args.source:
        targets = [args.source]
    else:
        logger.error("Specify --source <name> or --all")
        sys.exit(1)

    for name in targets:
        if name not in SPIDER_REGISTRY:
            logger.warning("No spider registered for source '%s', skipping", name)
            continue
        run_source(config, name, args.category)


if __name__ == "__main__":
    main()
