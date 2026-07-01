"""
CellphoneS Spider - Crawl sản phẩm từ cellphones.com.vn.

NOTE: CSS selectors reflect the site's markup at the time of writing and are the
most likely thing to break when the site changes. Verify them against the live
DOM before a production run. Parsing is defensive: missing fields fall back to
sensible defaults instead of raising.
"""
from urllib.parse import urljoin

from src.crawler.models import CrawledProduct, Review
from src.crawler.parser import (
    clean_ws,
    find_review_list,
    flatten_spec_groups,
    json_loads_safe,
    make_soup,
    parse_price,
    parse_rating,
    parse_spec_groups,
    pick,
    review_content,
    select_attr,
    select_text,
    star_rating,
)
from src.crawler.spiders.base_spider import BaseSpider

# JSON keys review endpoints tend to use (checked case-insensitively).
_LIST_KEYS = ("comments", "reviews", "data", "items", "listComment")
_AUTHOR_KEYS = ("fullname", "name", "customername", "author", "username")
_CONTENT_KEYS = ("content", "comment", "body", "message", "text")
_RATING_KEYS = ("rating", "star", "stars", "point", "score")


class CellphonesSpider(BaseSpider):
    """Spider for cellphones.com.vn (static HTML listing + detail pages)."""

    name = "cellphones"

    def build_list_url(self, category: str, page: int) -> str:
        template = self.source.categories[category]
        path = template.format(page=page)
        return urljoin(self.source.base_url, path)

    def parse_list(self, html: str, base_url: str) -> list[str]:
        soup = self.soup(html)
        urls: list[str] = []
        # Product cards: <div class="product-info"> <a class="product__link" href>
        for a in soup.select("a.product__link, .product-info a[href], .product-item a[href]"):
            href = a.get("href")
            if href:
                urls.append(urljoin(self.source.base_url, href))
        return [u for u in dict.fromkeys(urls) if u.startswith("http")]

    def parse_detail(self, html: str, url: str) -> CrawledProduct | None:
        soup = self.soup(html)

        name = select_text(soup, "h1")
        if not name:
            return None

        price = parse_price(select_text(soup, ".product__price--show, .box-info__box-price .tpt---sale-price, .price"))
        rating = parse_rating(select_text(soup, ".rating-average, .box-rating__average"))
        image = select_attr(soup, ".swiper-slide img, .product-image img", "src")
        description = select_text(soup, ".ksp-content, .product-description")

        spec_groups = self._parse_spec_groups(soup)
        specs = flatten_spec_groups(spec_groups)
        review_count = int(parse_rating(select_text(soup, ".rating-total, .box-rating__total")))

        product_id = self._slug_from_url(url)
        return CrawledProduct(
            id=f"{self.name}-{product_id}",
            name=name,
            source=self.name,
            source_url=url,
            brand=self._guess_brand(name),
            category="smartphone",
            price=price,
            specifications=specs,
            spec_groups=spec_groups,
            description=description,
            image_url=image,
            avg_rating=rating,
            review_count=review_count,
        )

    def _parse_spec_groups(self, soup) -> dict[str, dict[str, str]]:
        """Extract the spec table grouped by category, normalized to canonical keys."""
        root = soup.select_one(
            ".technical-content, .box-specification, .cps-block-content, "
            ".cps-block-content__box, table.table"
        )
        groups = parse_spec_groups(
            root,
            title_selector="h3, h4, .title, .box-specification__title, .group-title",
            row_selector="tr, li",
            label_selector="td:first-child, th, .label",
            value_selector="td:last-child, .value",
        )
        if groups:
            return groups
        general: dict[str, str] = {}
        for row in soup.select(
            ".technical-content tr, .box-specification tr, table.table tr"
        ):
            label = select_text(row, "td:first-child, th, .label")
            value = select_text(row, "td:last-child, .value")
            if label and value and label != value:
                general[clean_ws(label)] = clean_ws(value)
        return {"general": general} if general else {}

    # -- Reviews -------------------------------------------------------------

    _REVIEW_BLOCK_SELECTOR = (
        ".comment-item, .box-review__item, .review-item, .product-comment__item, "
        "[class*='review-item'], [class*='comment-item']"
    )
    _AUTHOR_SELECTOR = ".comment-author, .review-author, .rc-name, .name, .author, b, strong"
    _CONTENT_SELECTORS = (".comment-content", ".review-content", ".rc-content", ".content-comment")

    def parse_reviews(self, html: str, url: str) -> list[Review]:
        """Parse buyer reviews embedded in the detail page HTML (robust helpers)."""
        soup = make_soup(html)
        reviews: list[Review] = []
        for node in soup.select(self._REVIEW_BLOCK_SELECTOR):
            author = select_text(node, self._AUTHOR_SELECTOR)
            rating = star_rating(node)
            content = review_content(node, author, content_selectors=self._CONTENT_SELECTORS)
            if content and content != author:
                reviews.append(Review(author=author, rating=rating, content=content))
        return reviews

    def parse_reviews_payload(self, body: str, url: str) -> list[Review]:
        """Parse reviews from the review endpoint (JSON preferred, HTML fallback)."""
        data = json_loads_safe(body)
        if data is not None:
            reviews: list[Review] = []
            for record in find_review_list(data, _LIST_KEYS):
                content = pick(record, _CONTENT_KEYS)
                if not content:
                    continue
                reviews.append(
                    Review(
                        author=pick(record, _AUTHOR_KEYS),
                        rating=parse_rating(pick(record, _RATING_KEYS)),
                        content=content,
                    )
                )
            return reviews
        return self.parse_reviews(body, url)

    @staticmethod
    def _slug_from_url(url: str) -> str:
        return url.rstrip("/").split("/")[-1].split("?")[0].replace(".html", "")

    @staticmethod
    def _guess_brand(name: str) -> str:
        return name.split()[0] if name else ""
