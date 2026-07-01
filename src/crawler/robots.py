"""
Robots - Kiểm tra robots.txt trước khi crawl.
"""
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.utils.logger import setup_logger

logger = setup_logger("crawler.robots")


class RobotsChecker:
    """Fetch and cache robots.txt rules per host.

    Falls back to allowing the URL if robots.txt cannot be fetched, which keeps
    crawling resilient while still honoring explicit disallow rules.
    """

    def __init__(self, user_agent: str, timeout: float = 10.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self._parsers: dict[str, RobotFileParser] = {}

    def _get_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._parsers:
            parser = RobotFileParser()
            robots_url = urljoin(host, "/robots.txt")
            try:
                resp = httpx.get(
                    robots_url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser.allow_all = True
            except httpx.HTTPError as exc:
                logger.warning("Cannot fetch robots.txt for %s: %s", host, exc)
                parser.allow_all = True
            self._parsers[host] = parser
        return self._parsers[host]

    def can_fetch(self, url: str) -> bool:
        """Return True if the user agent is allowed to fetch the URL."""
        parser = self._get_parser(url)
        return parser.can_fetch(self.user_agent, url)
