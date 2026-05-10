"""
Built-in comparators for the GenericMatchingEngine.

Each comparator takes two resolved values and an optional config dict,
returning a (score: float, reason: str) tuple. Scores are normalized to [0, 1].

Comparators are registered in COMPARATOR_REGISTRY and dispatched by name
from MatchingDimension.comparator. New comparators can be added by defining
a function and registering it — no engine changes required.

Design doc: design/demand_definition_design_v2.0.md §5.1
"""
import re
import logging
from typing import Any, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


def compare_exact(v1: Any, v2: Any, config: Dict = None) -> Tuple[float, str]:
    if v1 is None or v2 is None or v1 == "" or v2 == "":
        return (0.5, "data_missing")
    if v1 == v2:
        return (1.0, "exact_match")
    return (0.0, "no_match")


def compare_enum_compatible(v1: Any, v2: Any, config: Dict = None) -> Tuple[float, str]:
    if v1 is None or v2 is None:
        return (0.5, "data_missing")
    if v1 == "any" or v2 == "any":
        return (1.0, "any_compatible")
    if v1 == v2:
        return (1.0, "exact_match")
    return (0.0, "incompatible")


def compare_range_overlap(v1: Any, v2: Any, config: Dict = None) -> Tuple[float, str]:
    if not isinstance(v1, dict) or not isinstance(v2, dict):
        return (0.5, "invalid_input")
    try:
        min1, max1 = float(v1.get("min", 0)), float(v1.get("max", 0))
        min2, max2 = float(v2.get("min", 0)), float(v2.get("max", 0))
    except (TypeError, ValueError):
        return (0.5, "invalid_input")
    if max1 < min1 or max2 < min2:
        return (0.0, "invalid_range")
    overlap_start = max(min1, min2)
    overlap_end = min(max1, max2)
    if overlap_start >= overlap_end:
        return (0.0, "no_overlap")
    overlap = overlap_end - overlap_start
    span1 = max1 - min1
    span2 = max2 - min2
    max_span = max(span1, span2)
    if max_span <= 0:
        return (0.0, "no_overlap")
    score = min(1.0, max(0.0, overlap / max_span))
    return (score, "range_overlap")


def compare_numeric_compatibility(v1: Any, v2: Any, config: Dict = None) -> Tuple[float, str]:
    if v1 is None or v2 is None:
        return (0.5, "data_missing")
    try:
        buyer_max = float(v1)
        seller_price = float(v2)
    except (TypeError, ValueError):
        return (0.5, "data_missing")
    if seller_price <= 0:
        return (0.5, "data_missing")
    if buyer_max >= seller_price:
        ratio = seller_price / buyer_max
        score = 0.3 + 0.7 * ratio
    else:
        score = max(0.0, 1.0 - (seller_price - buyer_max) / buyer_max)
    score = min(1.0, max(0.0, score))
    return (score, "numeric_compatible")


def _extract_city(text: str) -> str:
    if not text:
        return ""
    match = re.match(r"([\u4e00-\u9fff]{2,}(?:市)?)", str(text).strip())
    if match:
        return match.group(1)
    if "," in str(text):
        return str(text).split(",", 1)[0].strip().lower()
    return str(text).strip().lower()


def compare_geo_proximity(v1: Any, v2: Any, config: Dict = None) -> Tuple[float, str]:
    if v1 is None or v2 is None:
        return (0.5, "data_missing")
    city1 = _extract_city(str(v1))
    city2 = _extract_city(str(v2))
    if not city1 or not city2:
        return (0.5, "data_missing")
    if city1 == city2:
        return (1.0, "same_city")
    return (0.0, "different_city")


def compare_semantic_similarity(v1: Any, v2: Any, config: Dict = None) -> Tuple[float, str]:
    if v1 is None or v2 is None:
        return (0.5, "data_missing")
    if not isinstance(v1, list) or not isinstance(v2, list):
        return (0.5, "data_missing")
    if len(v1) == 0 and len(v2) == 0:
        return (1.0, "both_empty")
    if len(v1) == 0 or len(v2) == 0:
        return (0.5, "data_missing")

    config = config or {}
    vectors1 = config.get("vectors1")
    vectors2 = config.get("vectors2")

    if vectors1 is not None and vectors2 is not None:
        try:
            import math

            best = 0.0
            for a in vectors1:
                for b in vectors2:
                    dot = sum(ai * bi for ai, bi in zip(a, b))
                    norm_a = math.sqrt(sum(ai * ai for ai in a))
                    norm_b = math.sqrt(sum(bi * bi for bi in b))
                    if norm_a > 0 and norm_b > 0:
                        sim = dot / (norm_a * norm_b)
                        if sim > best:
                            best = sim
            score = min(1.0, max(0.0, best))
            return (score, "semantic_overlap")
        except Exception:
            logger.warning("Failed to compute cosine similarity, falling back to keyword overlap", exc_info=True)

    set1 = {str(item).lower() for item in v1}
    set2 = {str(item).lower() for item in v2}
    intersection = set1 & set2
    union = set1 | set2
    if len(union) == 0:
        return (0.0, "no_semantic_overlap")
    score = len(intersection) / len(union)
    return (score, "semantic_overlap")


COMPARATOR_REGISTRY = {
    "exact": compare_exact,
    "enum_compatible": compare_enum_compatible,
    "range_overlap": compare_range_overlap,
    "numeric_compatibility": compare_numeric_compatibility,
    "geo_proximity": compare_geo_proximity,
    "semantic_similarity": compare_semantic_similarity,
}


def apply_comparator(comparator_name: str, v1: Any, v2: Any, config: Dict = None) -> Tuple[float, str]:
    func = COMPARATOR_REGISTRY.get(comparator_name)
    if not func:
        return (0.5, f"unknown_comparator:{comparator_name}")
    return func(v1, v2, config)
