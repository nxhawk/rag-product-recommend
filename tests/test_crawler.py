"""Unit tests for the crawler module (no network access required)."""
from src.crawler.config import CrawlerConfig, SourceConfig
from src.crawler.models import CrawledProduct, CrawlResult, Review
from src.crawler.parser import (
    canonical_spec_group,
    find_review_list,
    flatten_spec_groups,
    json_loads_safe,
    make_soup,
    parse_price,
    parse_rating,
    parse_spec_groups,
    pick,
    review_content,
    select_text,
    star_rating,
)
from src.crawler.spiders import SPIDER_REGISTRY
from src.crawler.spiders.tgdd_spider import TgddSpider


def test_parse_price_strips_noise():
    assert parse_price("29.990.000₫") == 29990000
    assert parse_price("Giá: 1,250,000 đ") == 1250000
    assert parse_price("") == 0


def test_parse_rating():
    assert parse_rating("4.7/5") == 4.7
    assert parse_rating("4,5 sao") == 4.5
    assert parse_rating("no rating") == 0.0


def test_select_text_default():
    html = "<div><h1> Hello </h1></div>"
    from src.crawler.parser import make_soup

    soup = make_soup(html)
    assert select_text(soup, "h1") == "Hello"
    assert select_text(soup, "h2", default="n/a") == "n/a"


def test_config_from_yaml(tmp_path):
    cfg_file = tmp_path / "crawler.yaml"
    cfg_file.write_text(
        """
request_delay: 2.0
sources:
  tgdd:
    base_url: "https://example.com"
    max_pages: 1
    categories:
      smartphone: "/dtdd?page={page}"
""",
        encoding="utf-8",
    )
    config = CrawlerConfig.from_yaml(str(cfg_file))
    assert config.request_delay == 2.0
    assert "tgdd" in config.sources
    src = config.get_source("tgdd")
    assert isinstance(src, SourceConfig)
    assert src.categories["smartphone"] == "/dtdd?page={page}"


def test_crawled_product_serializable():
    product = CrawledProduct(
        id="tgdd-x", name="Test", source="tgdd", source_url="https://x/y"
    )
    d = product.to_dict()
    assert d["id"] == "tgdd-x"
    assert d["currency"] == "VND"
    assert "crawled_at" in d


def test_crawl_result_count():
    result = CrawlResult(source="tgdd")
    assert result.count == 0
    result.products.append(
        CrawledProduct(id="a", name="A", source="tgdd", source_url="u")
    )
    assert result.count == 1
    assert result.to_dict()["count"] == 1


def test_spider_registry_registered():
    assert "tgdd" in SPIDER_REGISTRY
    assert "cellphones" in SPIDER_REGISTRY


def test_tgdd_build_list_url():
    spider = TgddSpider()
    spider.bind(
        client=None,  # not needed for URL building
        source=SourceConfig(
            name="tgdd",
            base_url="https://www.thegioididong.com",
            categories={"smartphone": "/dtdd?page={page}"},
        ),
    )
    url = spider.build_list_url("smartphone", 2)
    assert url == "https://www.thegioididong.com/dtdd?page=2"


def test_tgdd_parse_list_extracts_links():
    spider = TgddSpider()
    spider.bind(
        client=None,
        source=SourceConfig(name="tgdd", base_url="https://www.thegioididong.com"),
    )
    html = """
    <ul class="listproduct">
      <li class="item"><a class="main-contain" href="/dtdd/iphone-15">iPhone 15</a></li>
      <li class="item"><a class="main-contain" href="/dtdd/galaxy-s24">S24</a></li>
    </ul>
    """
    urls = spider.parse_list(html, "https://www.thegioididong.com/dtdd")
    assert "https://www.thegioididong.com/dtdd/iphone-15" in urls
    assert len(urls) == 2


def test_tgdd_parse_detail_minimal():
    spider = TgddSpider()
    spider.bind(
        client=None,
        source=SourceConfig(name="tgdd", base_url="https://www.thegioididong.com"),
    )
    html = """
    <html><body>
      <h1>iPhone 15 Pro Max</h1>
      <div class="box-price-present">29.990.000₫</div>
      <div class="rating-avg">4.7</div>
      <ul class="parameter">
        <li><aside>RAM</aside><span>8 GB</span></li>
      </ul>
    </body></html>
    """
    product = spider.parse_detail(html, "https://www.thegioididong.com/dtdd/iphone-15-pro-max")
    assert product is not None
    assert product.name == "iPhone 15 Pro Max"
    assert product.price == 29990000
    assert product.avg_rating == 4.7
    assert product.brand == "iPhone"
    assert product.specifications.get("RAM") == "8 GB"
    assert product.id == "tgdd-iphone-15-pro-max"


# -- Specs & reviews ---------------------------------------------------------


class _FakeClient:
    """Minimal stand-in for HttpClient used to test review collection offline."""

    def __init__(self, config: CrawlerConfig, body: str = ""):
        self.config = config
        self._body = body
        self.requested: list[str] = []

    def get(self, url: str) -> str:
        self.requested.append(url)
        return self._body


def _bind_tgdd(client=None, **source_kwargs):
    spider = TgddSpider()
    src = SourceConfig(name="tgdd", base_url="https://www.thegioididong.com", **source_kwargs)
    spider.bind(client=client, source=src)
    return spider


def test_review_serialized_inside_product():
    product = CrawledProduct(
        id="tgdd-x", name="X", source="tgdd", source_url="https://x/y",
        reviews=[Review(author="An", rating=5.0, content="Rất tốt")],
    )
    d = product.to_dict()
    assert d["reviews"][0] == {"author": "An", "rating": 5.0, "content": "Rất tốt"}


def test_json_loads_safe():
    assert json_loads_safe('{"a": 1}') == {"a": 1}
    assert json_loads_safe("not json") is None


def test_find_review_list_nested():
    payload = {"result": {"data": {"comments": [{"content": "hi"}, {"content": "yo"}]}}}
    found = find_review_list(payload, ("comments", "reviews"))
    assert len(found) == 2
    assert found[0]["content"] == "hi"


def test_pick_case_insensitive():
    record = {"FullName": "An", "Content": "Tốt"}
    assert pick(record, ("fullname", "name")) == "An"
    assert pick(record, ("missing",), default="?") == "?"


def test_tgdd_full_spec_table_flattened():
    spider = _bind_tgdd()
    html = """
    <ul class="parameter">
      <li><aside>RAM</aside><span>8 GB</span></li>
      <li><aside>Pin</aside><span>4441 mAh</span></li>
      <li><aside>Màn hình</aside><span>6.7 inch</span></li>
    </ul>
    """
    specs = flatten_spec_groups(spider._parse_spec_groups(spider.soup(html)))
    assert specs == {"RAM": "8 GB", "Pin": "4441 mAh", "Màn hình": "6.7 inch"}


def test_canonical_spec_group():
    assert canonical_spec_group("Cấu hình & Bộ nhớ") == "configuration_memory"
    assert canonical_spec_group("Camera & Màn hình") == "camera_display"
    assert canonical_spec_group("Pin & Sạc") == "battery_charging"
    assert canonical_spec_group("Thiết kế & Chất liệu") == "design_material"
    assert canonical_spec_group("Điều gì đó khác") == "general"


def test_parse_spec_groups_ordered_walk():
    html = """
    <div class="box-specifi">
      <h3>Cấu hình & Bộ nhớ</h3>
      <ul>
        <li><aside>Hệ điều hành</aside><span>iOS 17</span></li>
        <li><aside>Chip</aside><span>A17 Pro</span></li>
      </ul>
      <h3>Pin & Sạc</h3>
      <ul>
        <li><aside>Dung lượng pin</aside><span>4441 mAh</span></li>
        <li><aside>Công nghệ sạc</aside><span>Sạc nhanh 20 W</span></li>
      </ul>
    </div>
    """
    root = make_soup(html).select_one(".box-specifi")
    groups = parse_spec_groups(
        root, "h3", "li", "aside", "span"
    )
    assert groups["configuration_memory"] == {"Hệ điều hành": "iOS 17", "Chip": "A17 Pro"}
    assert groups["battery_charging"] == {
        "Dung lượng pin": "4441 mAh",
        "Công nghệ sạc": "Sạc nhanh 20 W",
    }


def test_flatten_spec_groups():
    groups = {
        "configuration_memory": {"RAM": "8 GB"},
        "battery_charging": {"Pin": "4441 mAh"},
    }
    assert flatten_spec_groups(groups) == {"RAM": "8 GB", "Pin": "4441 mAh"}


def test_tgdd_parse_detail_populates_spec_groups():
    spider = _bind_tgdd()
    html = """
    <html><body>
      <h1>iPhone 15 Pro Max</h1>
      <div class="box-specifi">
        <h3>Camera & Màn hình</h3>
        <ul><li><aside>Màn hình</aside><span>6.7 inch</span></li></ul>
        <h3>Thiết kế & Chất liệu</h3>
        <ul><li><aside>Khối lượng</aside><span>221 g</span></li></ul>
      </div>
    </body></html>
    """
    product = spider.parse_detail(html, "https://www.thegioididong.com/dtdd/iphone-15-pro-max")
    assert product is not None
    assert product.spec_groups["camera_display"] == {"Màn hình": "6.7 inch"}
    assert product.spec_groups["design_material"] == {"Khối lượng": "221 g"}
    # Flattened view still available.
    assert product.specifications["Khối lượng"] == "221 g"


def test_tgdd_parse_inline_reviews():
    spider = _bind_tgdd()
    html = """
    <div class="comment-list">
      <div class="par">
        <div class="cmt-top-name">Nguyễn An</div>
        <div class="cmt-star">5</div>
        <div class="cmt-content">Máy đẹp, pin trâu</div>
      </div>
      <div class="par">
        <div class="cmt-top-name">Trần Bình</div>
        <div class="cmt-content">Giá hơi cao</div>
      </div>
    </div>
    """
    reviews = spider.parse_reviews(html, "https://x/y")
    assert len(reviews) == 2
    assert reviews[0].author == "Nguyễn An"
    assert reviews[0].rating == 5.0
    assert reviews[0].content == "Máy đẹp, pin trâu"
    assert reviews[1].rating == 0.0  # no star element


def test_tgdd_parse_reviews_payload_json():
    spider = _bind_tgdd()
    body = (
        '{"data": {"comments": ['
        '{"FullName": "An", "Rating": 5, "Content": "Tốt"},'
        '{"FullName": "Bình", "Rating": "4/5", "Content": "Ổn"},'
        '{"FullName": "NoText", "Content": ""}'
        ']}}'
    )
    reviews = spider.parse_reviews_payload(body, "https://x/reviews")
    assert len(reviews) == 2  # empty-content record skipped
    assert reviews[0].author == "An" and reviews[0].rating == 5.0
    assert reviews[1].rating == 4.0


def test_collect_reviews_respects_flag_and_cap():
    # fetch_reviews disabled -> no reviews collected
    off = CrawlerConfig(fetch_reviews=False)
    spider = _bind_tgdd(client=_FakeClient(off))
    product = CrawledProduct(id="tgdd-x", name="X", source="tgdd", source_url="https://x/y")
    assert spider.collect_reviews(product, "<html></html>") == []

    # enabled with a cap of 2, endpoint returns 3 -> capped
    body = (
        '{"comments": ['
        '{"FullName": "A", "Content": "1"},'
        '{"FullName": "B", "Content": "2"},'
        '{"FullName": "C", "Content": "3"}'
        ']}'
    )
    on = CrawlerConfig(fetch_reviews=True, max_reviews=2)
    client = _FakeClient(on, body=body)
    spider = _bind_tgdd(
        client=client,
        reviews_url="https://www.thegioididong.com/aj/comment?slug={slug}",
    )
    reviews = spider.collect_reviews(product, "<html></html>")
    assert len(reviews) == 2
    assert client.requested == ["https://www.thegioididong.com/aj/comment?slug=y"]


def test_build_reviews_url_none_without_template():
    spider = _bind_tgdd()
    product = CrawledProduct(id="tgdd-x", name="X", source="tgdd", source_url="https://x/y")
    assert spider.build_reviews_url(product) is None


# -- Robust rating + content extraction --------------------------------------


def test_star_rating_numeric_label():
    node = make_soup('<div class="par"><span class="cmt-star">5/5</span></div>').select_one(".par")
    assert star_rating(node) == 5.0


def test_star_rating_width_percent():
    html = '<div class="par"><div class="star" style="width:100%"><div class="on" style="width: 80%"></div></div></div>'
    node = make_soup(html).select_one(".par")
    assert star_rating(node) == 4.0  # smallest positive width (80%) / 20


def test_star_rating_icon_count():
    html = '<div class="par">' + '<i class="star-on"></i>' * 5 + "</div>"
    node = make_soup(html).select_one(".par")
    assert star_rating(node) == 5.0


def test_review_content_fallback_excludes_author_and_footer():
    html = """
    <div class="par">
      <b class="cmt-top-name">Nguyễn Bá Hà</b>
      <i>Đã mua tại TGDĐ</i>
      <div>Sản phẩm rất tốt, pin trâu, camera đẹp</div>
      <div>Bộ phận bán hàng đã liên hệ hỗ trợ ngày 30/05/2026</div>
      <span>Hữu ích (116)</span>
      <span>Đã dùng khoảng 1 tháng</span>
    </div>
    """
    node = make_soup(html).select_one(".par")
    content = review_content(node, "Nguyễn Bá Hà")
    assert content == "Sản phẩm rất tốt, pin trâu, camera đẹp"


def test_tgdd_reviews_capture_content_and_rating_without_content_class():
    """Regression: content must be the review text (not the author) and rating captured."""
    spider = _bind_tgdd()
    html = """
    <div class="comment-list">
      <div class="par">
        <b class="cmt-top-name">Nguyễn Bá Hà</b>
        <i>Đã mua tại TGDĐ</i>
        <div class="star">""" + '<i class="star-on"></i>' * 5 + """</div>
        <div>Sản phẩm iphone 17 pro max màu bạc rất đẹp</div>
        <span>Hữu ích (116)</span>
      </div>
      <div class="par">
        <b class="cmt-top-name">Minh</b>
        <i>Đã mua tại TGDĐ</i>
        <div class="star">""" + '<i class="star-on"></i>' * 5 + """</div>
        <div>Nghe gọi khi bật loa ngoài thì tiếng vang rất to</div>
        <span>Hữu ích (51)</span>
      </div>
    </div>
    """
    reviews = spider.parse_reviews(html, "https://x/y")
    assert len(reviews) == 2
    assert reviews[0].author == "Nguyễn Bá Hà"
    assert reviews[0].content == "Sản phẩm iphone 17 pro max màu bạc rất đẹp"
    assert reviews[0].rating == 5.0
    assert reviews[1].author == "Minh"
    assert reviews[1].content == "Nghe gọi khi bật loa ngoài thì tiếng vang rất to"
    assert reviews[1].rating == 5.0


# -- Discovery / pagination --------------------------------------------------


class _FakeListClient:
    """Serves listing HTML per page number parsed from the URL."""

    def __init__(self, pages: dict[int, str]):
        self.pages = pages

    def get(self, url: str) -> str:
        import re

        m = re.search(r"(?:page|p)=(\d+)", url)
        page = int(m.group(1)) if m else 1
        return self.pages.get(page, self.pages[max(self.pages)])


def _listing_html(hrefs: list[str]) -> str:
    items = "".join(
        f'<li class="item"><a class="main-contain" href="{h}">x</a></li>' for h in hrefs
    )
    return f'<ul class="listproduct">{items}</ul>'


def test_discover_stops_when_no_new_urls():
    pages = {
        1: _listing_html(["/dtdd/p1a", "/dtdd/p1b"]),
        2: _listing_html(["/dtdd/p2a", "/dtdd/p2b"]),
        # page 3+ repeats page 2 -> no new URLs -> discover stops
    }
    spider = _bind_tgdd(
        client=_FakeListClient(pages),
        max_pages=8,
        max_products=100,
        categories={"smartphone": "/dtdd?page={page}"},
    )
    urls = spider.discover("smartphone")
    assert len(urls) == 4
    assert urls[0].endswith("/dtdd/p1a")


def test_discover_honors_max_products():
    pages = {
        1: _listing_html(["/dtdd/p1a", "/dtdd/p1b"]),
        2: _listing_html(["/dtdd/p2a", "/dtdd/p2b"]),
        3: _listing_html(["/dtdd/p3a", "/dtdd/p3b"]),
    }
    spider = _bind_tgdd(
        client=_FakeListClient(pages),
        max_pages=8,
        max_products=3,
        categories={"smartphone": "/dtdd?page={page}"},
    )
    urls = spider.discover("smartphone")
    assert len(urls) == 3
