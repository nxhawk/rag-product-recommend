"""
Parser - Các hàm tiện ích parse HTML dùng chung (BeautifulSoup).
"""
import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.utils.helpers import parse_price_text


def make_soup(html: str) -> BeautifulSoup:
    """Build a BeautifulSoup tree, preferring lxml with a stdlib fallback."""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:  # lxml not installed
        return BeautifulSoup(html, "html.parser")


def select_text(node: Tag | BeautifulSoup, selector: str, default: str = "") -> str:
    """Return stripped text of the first element matching `selector`."""
    el = node.select_one(selector)
    return el.get_text(strip=True) if el else default


def select_attr(
    node: Tag | BeautifulSoup, selector: str, attr: str, default: str = ""
) -> str:
    """Return an attribute value of the first element matching `selector`."""
    el = node.select_one(selector)
    if not el:
        return default
    value = el.get(attr, default)
    return value if isinstance(value, str) else default


def parse_price(text: str) -> int:
    """Extract an integer price (VND) from noisy text like '29.990.000₫'.

    Delegates to :func:`src.utils.helpers.parse_price_text`, which uses only the
    first price-like number so pages listing several prices (current +
    struck-through original + installment) are not concatenated.
    """
    return parse_price_text(text)


def parse_rating(text: str) -> float:
    """Extract a float rating from text like '4.7/5' or '4,7'."""
    match = re.search(r"(\d+[.,]?\d*)", text or "")
    if not match:
        return 0.0
    return float(match.group(1).replace(",", "."))


def clean_ws(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text or "").strip()


# -- Review helpers ----------------------------------------------------------


def json_loads_safe(text: str) -> Any | None:
    """Parse JSON, returning None on failure instead of raising."""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def find_review_list(obj: Any, list_keys: tuple[str, ...]) -> list[dict]:
    """Recursively locate the first list-of-dicts under one of `list_keys`.

    Review endpoints wrap the array differently (``data``, ``comments``,
    ``listComment`` ...); this walks the JSON to find it regardless of nesting.
    """
    if isinstance(obj, dict):
        for key in list_keys:
            value = obj.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
        for value in obj.values():
            found = find_review_list(value, list_keys)
            if found:
                return found
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and any(k in obj[0] for k in list_keys):
            return obj
        for item in obj:
            found = find_review_list(item, list_keys)
            if found:
                return found
    return []


def pick(record: dict, keys: tuple[str, ...], default: str = "") -> str:
    """Return the first non-empty value among `keys` (case-insensitive)."""
    lowered = {str(k).lower(): v for k, v in record.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, "", []):
            return clean_ws(str(value))
    return default


# -- Specification-group helpers ---------------------------------------------

# Map a site's Vietnamese spec-group heading to a stable canonical key.
_CANONICAL_SPEC_GROUPS: dict[str, tuple[str, ...]] = {
    "configuration_memory": ("cấu hình", "bộ nhớ", "hệ điều hành", "chip", "cpu"),
    "camera_display": ("camera", "màn hình"),
    "battery_charging": ("pin", "sạc"),
    "design_material": ("thiết kế", "chất liệu", "kích thước", "khối lượng"),
    "connectivity": ("kết nối", "tiện ích", "giao tiếp"),
}


def canonical_spec_group(title: str) -> str:
    """Normalize a spec-group heading to a canonical key (or 'general')."""
    low = (title or "").lower()
    for key, needles in _CANONICAL_SPEC_GROUPS.items():
        if any(n in low for n in needles):
            return key
    return "general"


def parse_spec_groups(
    root: Tag | BeautifulSoup | None,
    title_selector: str,
    row_selector: str,
    label_selector: str,
    value_selector: str,
    canonicalize: bool = True,
) -> dict[str, dict[str, str]]:
    """Group spec rows under their nearest preceding heading.

    Walks `root` in document order: when a heading (``title_selector``) is seen it
    becomes the current group; each following row (``row_selector``) is added to
    it. Robust to flat lists with interspersed ``<h3>`` headers. Rows before any
    heading fall under ``"general"``. Identity is matched by ``id()`` so that two
    structurally-identical rows are not treated as equal.
    """
    if root is None:
        return {}
    title_ids = {id(t) for t in root.select(title_selector)}
    row_ids = {id(r) for r in root.select(row_selector)}
    groups: dict[str, dict[str, str]] = {}
    current = "general"
    for el in root.descendants:
        if not isinstance(el, Tag):
            continue
        if id(el) in title_ids:
            title = clean_ws(el.get_text(" "))
            current = canonical_spec_group(title) if canonicalize else title
        elif id(el) in row_ids:
            label = select_text(el, label_selector)
            value = select_text(el, value_selector)
            if label and value and label != value:
                groups.setdefault(current, {})[clean_ws(label)] = clean_ws(value)
    return groups


def flatten_spec_groups(groups: dict[str, dict[str, str]]) -> dict[str, str]:
    """Flatten grouped specs into a single label -> value map (first wins)."""
    flat: dict[str, str] = {}
    for rows in groups.values():
        for label, value in rows.items():
            flat.setdefault(label, value)
    return flat


# -- Review content / rating extraction --------------------------------------

# Footer/label text that marks the end of a review body (Vietnamese e-commerce).
_REVIEW_STOP_MARKERS: tuple[str, ...] = (
    "Hữu ích",
    "Đã dùng",
    "Bộ phận bán hàng",
    "Phản hồi",
    "Trả lời",
    "Xem thêm",
    "Chưa dùng",
)

# Purchase badges to strip from a review body.
_REVIEW_REMOVE_PHRASES: tuple[str, ...] = (
    "Đã mua tại TGDĐ",
    "Đã mua tại Điện Máy Xanh",
    "Đã mua tại CellphoneS",
    "Đã mua tại",
    "Đã mua hàng",
    "Đã mua",
)


def star_rating(node) -> float:
    """Best-effort star rating (0..5) from a review node.

    Tries, in order: a numeric rating label, a filled-bar `width: N%` overlay,
    the count of filled star icons, then the count of any star icons (assumed
    filled). Returns 0.0 when nothing star-like is found.
    """
    # 1) explicit numeric label (e.g. "5/5", "4.5")
    for sel in (".cmt-star", ".rating", ".star-user", ".point", "[class*='rating'] [class*='num']"):
        el = node.select_one(sel)
        if el:
            value = parse_rating(el.get_text(" "))
            if 0 < value <= 5:
                return value
    # 2) filled-bar width percentage (filled overlay = smallest positive width)
    widths: list[float] = []
    for el in node.select("[style*='width']"):
        match = re.search(r"width:\s*([\d.]+)%", el.get("style", "") or "")
        if match:
            pct = float(match.group(1))
            if 0 < pct <= 100:
                widths.append(pct)
    if widths:
        return round(min(widths) / 20, 1)
    # 3) count filled star icons
    filled = node.select(
        "i.iconcmt-startON, .star-on, .is-active, "
        "[class*='star'][class*='on'], [class*='star'][class*='active'], "
        "[class*='star'][class*='full'], [class*='star'][class*='fill']"
    )
    if filled:
        return float(min(len(filled), 5))
    # 4) any star icons (assume all shown are filled)
    stars = node.select(
        "i[class*='star'], span[class*='star'], svg[class*='star'], em[class*='star']"
    )
    if stars:
        return float(min(len(stars), 5))
    return 0.0


def review_content(
    node,
    author: str = "",
    content_selectors: tuple[str, ...] = (),
    remove_phrases: tuple[str, ...] | None = None,
    stop_markers: tuple[str, ...] | None = None,
) -> str:
    """Extract a review body from its node.

    Tries the specific `content_selectors` first; if none yield text distinct
    from the author, falls back to the node's full text with the author, purchase
    badges (`remove_phrases`) and footer (`stop_markers`) stripped. This works
    even when the exact content class name is unknown, as long as the review node
    itself is correct.
    """
    remove_phrases = _REVIEW_REMOVE_PHRASES if remove_phrases is None else remove_phrases
    stop_markers = _REVIEW_STOP_MARKERS if stop_markers is None else stop_markers
    author = clean_ws(author)

    for sel in content_selectors:
        el = node.select_one(sel)
        if el:
            text = clean_ws(el.get_text(" "))
            if text and text != author:
                return text

    text = clean_ws(node.get_text(" "))
    for phrase in remove_phrases:
        text = text.replace(phrase, " ")
    if author:
        text = text.replace(author, " ")
    for marker in stop_markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    text = clean_ws(text)
    return text if text and text != author else ""
