"""Unit tests for src/guardrails/output/ and fallback.py."""

import json

from src.guardrails import (
    build_compare_fallback,
    build_recommend_fallback,
    ground_compare_analysis,
    ground_recommendations,
    validate_compare_output,
    validate_recommend_output,
)


def test_validate_recommend_output_valid_json():
    raw = json.dumps(
        {
            "recommendations": [
                {
                    "name": "Xiaomi 14",
                    "price": 13990000,
                    "reason": "tot",
                    "pros": [],
                    "cons": [],
                    "best_for": "sinh vien",
                }
            ],
            "summary": "Goi y dien thoai",
        }
    )
    result = validate_recommend_output(raw)
    assert not result.blocked
    assert result.sanitized_payload["recommendations"][0]["name"] == "Xiaomi 14"


def test_validate_recommend_output_blocks_non_json():
    assert validate_recommend_output("day khong phai JSON").blocked


def test_validate_recommend_output_blocks_schema_violation():
    # "name" is required on each recommendation item.
    raw = json.dumps({"recommendations": [{"price": 1000}], "summary": "x"})
    assert validate_recommend_output(raw).blocked


def test_validate_compare_output_valid_json():
    raw = json.dumps(
        {
            "criteria_comparison": [{"criterion": "Gia", "winner": "A", "details": "..."}],
            "product_analysis": [{"name": "A", "pros": [], "cons": [], "best_for": ""}],
            "conclusion": "Chon A",
        }
    )
    assert not validate_compare_output(raw).blocked


def test_ground_recommendations_drops_hallucinated_items():
    items = [{"name": "Xiaomi 14"}, {"name": "San pham khong ton tai"}]
    retrieved = [{"metadata": {"name": "Xiaomi 14"}}]
    grounded, warnings = ground_recommendations(items, retrieved)
    assert [g["name"] for g in grounded] == ["Xiaomi 14"]
    assert warnings


def test_ground_recommendations_case_and_whitespace_insensitive():
    items = [{"name": "  xiaomi   14 "}]
    retrieved = [{"metadata": {"name": "Xiaomi 14"}}]
    grounded, warnings = ground_recommendations(items, retrieved)
    assert len(grounded) == 1
    assert not warnings


def test_ground_recommendations_tolerates_dropped_prefix_and_suffix():
    # Regression: the LLM commonly drops a leading category word or a
    # trailing "| Chính hãng ..." suffix while otherwise copying the name
    # verbatim. An exact-only comparison used to drop every item in this
    # situation and always fall back (see GUARDRAIL_PLAN.md).
    items = [
        {"name": "Xiaomi 17T 5G 12GB/256GB"},
        {"name": "iPhone 15 128GB"},
    ]
    retrieved = [
        {"metadata": {"name": "Điện thoại Xiaomi 17T 5G 12GB/256GB"}},
        {"metadata": {"name": "iPhone 15 128GB | Chính hãng VN/A"}},
    ]
    grounded, warnings = ground_recommendations(items, retrieved)
    assert len(grounded) == 2
    assert not warnings


def test_ground_recommendations_still_drops_unrelated_name():
    items = [{"name": "Samsung Galaxy Z Fold"}]
    retrieved = [{"metadata": {"name": "iPhone 15 128GB | Chính hãng VN/A"}}]
    grounded, warnings = ground_recommendations(items, retrieved)
    assert grounded == []
    assert warnings


def test_ground_compare_analysis_drops_unknown_product():
    items = [{"name": "A"}, {"name": "Z"}]
    products = [{"name": "A"}, {"name": "B"}]
    grounded, warnings = ground_compare_analysis(items, products)
    assert [g["name"] for g in grounded] == ["A"]
    assert warnings


def test_build_recommend_fallback_uses_retrieved_products():
    retrieved = [
        {"metadata": {"name": "A", "price": 100}},
        {"metadata": {"name": "B", "price": 200}},
    ]
    fallback = build_recommend_fallback(retrieved, top_k=1)
    assert len(fallback["recommendations"]) == 1
    assert fallback["recommendations"][0]["name"] == "A"
    assert fallback["summary"]


def test_build_recommend_fallback_empty_when_no_products():
    fallback = build_recommend_fallback([], top_k=5)
    assert fallback["recommendations"] == []
    assert "Khong tim thay" in fallback["summary"]


def test_build_compare_fallback_uses_products():
    products = [{"name": "A"}, {"name": "B"}]
    fallback = build_compare_fallback(products)
    assert [a["name"] for a in fallback["product_analysis"]] == ["A", "B"]
    assert fallback["criteria_comparison"] == []
