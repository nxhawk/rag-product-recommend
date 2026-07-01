"""
Exceptions - Các lỗi tùy chỉnh cho module crawler.
"""


class CrawlerError(Exception):
    """Base exception for all crawler errors."""


class FetchError(CrawlerError):
    """Raised when an HTTP request fails after all retries."""

    def __init__(self, url: str, status_code: int | None = None, message: str = ""):
        self.url = url
        self.status_code = status_code
        detail = f" (status={status_code})" if status_code else ""
        super().__init__(f"Failed to fetch {url}{detail}: {message}".strip())


class ParseError(CrawlerError):
    """Raised when parsing an HTML page fails or required data is missing."""

    def __init__(self, url: str, message: str = ""):
        self.url = url
        super().__init__(f"Failed to parse {url}: {message}".strip())


class RobotsDisallowed(CrawlerError):
    """Raised when robots.txt disallows crawling a URL."""

    def __init__(self, url: str):
        self.url = url
        super().__init__(f"Disallowed by robots.txt: {url}")
