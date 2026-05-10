"""
Matching module — pluggable matching engines.

Legacy exports (V1): BaseMatcher, MatchResult, SimpleMatcher, MatcherFactory.
V2.0 exports: GenericMatchingEngine + built-in comparators.

Design doc: design/demand_definition_design_v2.0.md §五
"""
from backend.matching.base import BaseMatcher, MatchResult
from backend.matching.simple import SimpleMatcher
from backend.matching.factory import MatcherFactory
from backend.matching.comparators import (
    compare_exact,
    compare_enum_compatible,
    compare_range_overlap,
    compare_numeric_compatibility,
    compare_geo_proximity,
    compare_semantic_similarity,
    COMPARATOR_REGISTRY,
    apply_comparator,
)
from backend.matching.generic_engine import GenericMatchingEngine

__all__ = [
    "BaseMatcher",
    "MatchResult",
    "SimpleMatcher",
    "MatcherFactory",
    "compare_exact",
    "compare_enum_compatible",
    "compare_range_overlap",
    "compare_numeric_compatibility",
    "compare_geo_proximity",
    "compare_semantic_similarity",
    "COMPARATOR_REGISTRY",
    "apply_comparator",
    "GenericMatchingEngine",
]
