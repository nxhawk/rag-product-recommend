"""Grounding guardrail - never let the LLM invent a product.

Every ``recommendations[].name`` (recommend) or ``product_analysis[].name``
(compare) must match a product that was actually retrieved/compared.
Ungrounded items are dropped and counted in a warning rather than silently
kept, so hallucinated products never reach the user.

Matching is intentionally a bit more forgiving than a raw string ``==``:
the prompt asks the LLM to copy ``name`` verbatim, but models still commonly
drop a prefix/suffix (e.g. a leading "Điện thoại " or a trailing
"| Chính hãng VN/A") or tweak punctuation while keeping the product
otherwise identifiable. An exact-only comparison caused every recommendation
to be dropped as "ungrounded" in practice. See ``GuardrailConfig`` for the
tunable thresholds.
"""

import difflib
import re
from typing import Any

from src.guardrails.config import GuardrailConfig

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_name(name: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", (name or "").strip()).lower()


def _known_names(products: list[dict[str, Any]]) -> set[str]:
    names = set()
    for product in products:
        metadata = product.get("metadata")
        name = metadata.get("name") if isinstance(metadata, dict) else product.get("name")
        normalized = _normalize_name(name)
        if normalized:
            names.add(normalized)
    return names


def _is_grounded(candidate: str, known_names: set[str], cfg: GuardrailConfig) -> bool:
    if not candidate:
        return False
    if candidate in known_names:
        return True
    # Substring containment (either direction) tolerates a dropped
    # prefix/suffix, guarded by a minimum length so a short, generic
    # fragment (e.g. a bare brand name) can't match everything.
    if len(candidate) >= cfg.grounding_min_containment_chars:
        for known in known_names:
            if len(known) >= cfg.grounding_min_containment_chars and (
                candidate in known or known in candidate
            ):
                return True
    # Fuzzy fallback for punctuation/spacing/small wording differences.
    close = difflib.get_close_matches(
        candidate, known_names, n=1, cutoff=cfg.grounding_fuzzy_ratio
    )
    return bool(close)


def _ground_items(
    items: list[dict[str, Any]],
    known_names: set[str],
    cfg: GuardrailConfig,
    *,
    dropped_message: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    grounded = []
    dropped = 0
    for item in items:
        if _is_grounded(_normalize_name(item.get("name")), known_names, cfg):
            grounded.append(item)
        else:
            dropped += 1
    warnings = [dropped_message.format(count=dropped)] if dropped else []
    return grounded, warnings


def ground_recommendations(
    items: list[dict[str, Any]],
    retrieved_products: list[dict[str, Any]],
    guardrail_config: GuardrailConfig | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop recommendation items whose name doesn't match a retrieved product."""
    return _ground_items(
        items,
        _known_names(retrieved_products),
        guardrail_config or GuardrailConfig(),
        dropped_message="Da loai {count} muc goi y khong khop voi san pham da truy xuat.",
    )


def ground_compare_analysis(
    items: list[dict[str, Any]],
    products: list[dict[str, Any]],
    guardrail_config: GuardrailConfig | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop analysis items whose name doesn't match a product being compared."""
    return _ground_items(
        items,
        _known_names(products),
        guardrail_config or GuardrailConfig(),
        dropped_message="Da loai {count} muc phan tich khong khop voi san pham dang so sanh.",
    )
