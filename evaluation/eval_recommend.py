"""Evaluation - Đánh giá chất lượng gợi ý sản phẩm.

Offline quality eval against `evaluation/test_case/test_cases_recommend.json`. Uses the real
pipeline (embedder + vector store + LLM), so it is run manually - see
TEST_PLAN.md: "evaluation/ không đưa vào pytest suite - đó là offline
quality eval cần LLM thật, giữ chạy thủ công."

Usage:
    uv run python evaluation/eval_recommend.py
    uv run python evaluation/eval_recommend.py --top-k 3 --output evaluation/report.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from api.deps import get_recommend_pipeline
from src.pipeline.config import PipelineConfig
from src.pipeline.recommend.user_intent_parser import UserIntent
from src.pipeline.recommend_pipeline import RecommendPipeline
from src.utils.logger import setup_logger

logger = setup_logger("eval_recommend")

# A case is "passed" when its average metric score reaches this bar.
PASS_THRESHOLD = 0.7

METRIC_NAMES = ("relevance", "budget_fit", "intent_recall", "faithfulness")


class RecommendEvaluator:
    """Evaluate recommendation quality against a set of test cases.

    Each case is scored on four metrics, computed against the pipeline's
    *retrieved candidates* wherever possible (rather than free-form LLM
    prose) so a failure points at a specific stage:

    - relevance:     fraction of retrieved candidates matching ``expected_category``.
    - budget_fit:    fraction of retrieved candidates priced inside ``expected_price_range``.
    - intent_recall: fraction of ``expected_features`` detected by the intent parser.
    - faithfulness:  the LLM output parsed as structured JSON, is non-empty, and every
                      recommended product name traces back to a retrieved candidate
                      (no hallucinated products).
    """

    def __init__(self, pipeline: RecommendPipeline, pass_threshold: float = PASS_THRESHOLD):
        self.pipeline = pipeline
        self.pass_threshold = pass_threshold

    def evaluate(self, test_cases: list[dict], top_k: int = 5) -> dict:
        """Run evaluation on test cases (only ``type == "recommend"`` ones)."""
        cases = [c for c in test_cases if c.get("type", "recommend") == "recommend"]
        agg: dict[str, list[float]] = {name: [] for name in METRIC_NAMES}
        case_results = []

        for case in cases:
            case_result = self._evaluate_case(case, top_k=top_k)
            case_results.append(case_result)
            for metric, value in case_result["scores"].items():
                agg[metric].append(value)

        passed = sum(1 for c in case_results if c["passed"])
        return {
            "total": len(cases),
            "passed": passed,
            "pass_rate": round(passed / len(cases), 3) if cases else None,
            "metrics": {
                metric: round(sum(values) / len(values), 3) if values else None
                for metric, values in agg.items()
            },
            "cases": case_results,
        }

    def _evaluate_case(self, case: dict, top_k: int) -> dict:
        query = case["query"]
        try:
            parsed = self.pipeline.run(query, top_k=top_k)
        except Exception as exc:
            logger.exception("Pipeline run failed for case %s", case.get("id"))
            zero_scores = dict.fromkeys(METRIC_NAMES, 0.0)
            return {
                "id": case.get("id"),
                "query": query,
                "error": str(exc),
                "scores": zero_scores,
                "score": 0.0,
                "passed": False,
            }

        candidates = parsed.get("retrieved_products") or []
        intent = self.pipeline.recommend_engine.intent_parser.parse(query)

        scores = {
            "relevance": self._score_relevance(candidates, case.get("expected_category")),
            "budget_fit": self._score_budget_fit(candidates, case.get("expected_price_range")),
            "intent_recall": self._score_intent_recall(intent, case.get("expected_features") or []),
            "faithfulness": self._score_faithfulness(parsed, candidates),
        }
        overall = sum(scores.values()) / len(scores)

        return {
            "id": case.get("id"),
            "query": query,
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "score": round(overall, 3),
            "passed": overall >= self.pass_threshold,
        }

    @staticmethod
    def _score_relevance(candidates: list[dict], expected_category: str | None) -> float:
        """Fraction of retrieved candidates matching the expected category."""
        if not expected_category:
            return 1.0
        if not candidates:
            return 0.0
        expected = expected_category.lower()
        matches = sum(
            1
            for c in candidates
            if str(c.get("metadata", {}).get("category", "")).lower() == expected
        )
        return matches / len(candidates)

    @staticmethod
    def _score_budget_fit(candidates: list[dict], expected_price_range: list[int] | None) -> float:
        """Fraction of retrieved candidates priced inside the expected range."""
        if not expected_price_range:
            return 1.0
        if not candidates:
            return 0.0
        low, high = expected_price_range
        in_range = sum(
            1
            for c in candidates
            if isinstance((price := c.get("metadata", {}).get("price")), (int, float))
            and low <= price <= high
        )
        return in_range / len(candidates)

    @staticmethod
    def _score_intent_recall(intent: UserIntent, expected_features: list[str]) -> float:
        """Fraction of expected_features detected by the intent parser."""
        if not expected_features:
            return 1.0
        detected = set(intent.priorities) | set(intent.use_case)
        hits = sum(1 for feature in expected_features if feature in detected)
        return hits / len(expected_features)

    @staticmethod
    def _score_faithfulness(parsed: dict, candidates: list[dict]) -> float:
        """1.0 when the output is structured JSON with grounded recommendations.

        Penalizes: unparseable LLM output (falls back to raw text), empty
        recommendation lists, and recommended product names that don't match
        any retrieved candidate (hallucinated products).
        """
        if parsed.get("structured") is False:
            return 0.0
        recommendations = parsed.get("recommendations") or []
        if not recommendations:
            return 0.0
        candidate_names = {str(c.get("metadata", {}).get("name", "")).lower() for c in candidates}
        grounded = sum(
            1 for r in recommendations if str(r.get("name", "")).lower() in candidate_names
        )
        return grounded / len(recommendations)


def _print_report(report: dict) -> None:
    print(f"\n{'=' * 70}\nRecommend Evaluation Report\n{'=' * 70}")
    for case in report["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        print(f"\n[{status}] {case['id']} (score={case['score']}) - {case['query']}")
        if "error" in case:
            print(f"  error: {case['error']}")
            continue
        for metric, value in case["scores"].items():
            print(f"  {metric:<14}: {value}")

    print(f"\n{'-' * 70}")
    print(f"Total: {report['total']}  Passed: {report['passed']}  Pass rate: {report['pass_rate']}")
    print("Average metrics:")
    for metric, value in report["metrics"].items():
        print(f"  {metric:<14}: {value}")
    print(f"{'=' * 70}\n")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Evaluate recommendation pipeline quality.")
    parser.add_argument(
        "--test-cases",
        default=str(Path(__file__).parent / "test_case" / "test_cases_recommend.json"),
        help="Path to the JSON test case file. Default: evaluation/test_case/test_cases_recommend.json",
    )
    parser.add_argument(
        "--top-k", type=int, default=5, help="top_k passed to the pipeline. Default: 5"
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=PASS_THRESHOLD,
        help=f"Average metric score needed for a case to pass. Default: {PASS_THRESHOLD}",
    )
    parser.add_argument(
        "--config", default="configs/settings.yaml", help="Path to the pipeline config YAML."
    )
    parser.add_argument("--output", default=None, help="Optional path to write the JSON report to.")
    args = parser.parse_args()

    with open(args.test_cases, encoding="utf-8") as f:
        test_cases = json.load(f)

    logger.info("Building recommend pipeline...")
    config = PipelineConfig.from_yaml(args.config)
    pipeline = get_recommend_pipeline(config)

    evaluator = RecommendEvaluator(pipeline, pass_threshold=args.pass_threshold)
    logger.info(f"Running evaluation on {len(test_cases)} test case(s)...")
    report = evaluator.evaluate(test_cases, top_k=args.top_k)

    _print_report(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
