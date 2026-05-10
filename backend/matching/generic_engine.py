"""
Generic dimension-based matching engine.

Replaces the V1 per-type scoring functions (_score_rental, _score_dating,
_score_gaming) with a single declarative engine. Matching logic is defined
entirely through MatchingDimensions in DemandSchema records.

Two-phase matching:
    Phase 1 — Hard filters: each is_hard_filter dimension must pass (>0.0)
              or the candidate is immediately rejected.
    Phase 2 — Weighted scoring: non-hard-filter dimensions are scored via
              their declared comparator, then combined by weight (normalized
              to sum of scoring weights).

The engine has no domain knowledge — it only executes comparators and
resolves field paths from StructuredDemand instances.

Design doc: design/demand_definition_design_v2.0.md §5.2
"""
import logging
from typing import Dict, List, Optional, Tuple, Any

from backend.demand_models import (
    DemandSchema, StructuredDemand, FieldValue, MatchingDimension,
)
from backend.matching.comparators import apply_comparator

logger = logging.getLogger(__name__)


class GenericMatchingEngine:

    def __init__(self, schema_registry=None):
        self.schema_registry = schema_registry

    def compute_match(
        self, d1: StructuredDemand, d2: StructuredDemand
    ) -> Tuple[float, str, Dict[str, float]]:
        schema = self._get_schema(d1.schema_id)
        if not schema:
            return (0.5, "unknown_schema", {})

        dimension_scores: Dict[str, float] = {}

        for dim in schema.matching_dimensions:
            if dim.is_hard_filter:
                if not self._check_hard_constraint(dim, d1, d2, schema):
                    return (0.0, f"hard_filter:{dim.name}", {dim.dimension_id: 0.0})

        total_score = 0.0
        total_weight = 0.0
        for dim in schema.matching_dimensions:
            if dim.is_hard_filter:
                continue
            v1 = self._resolve_field(dim, d1, schema)
            v2 = self._resolve_field(dim, d2, schema)
            dim_score, _ = apply_comparator(dim.comparator, v1, v2, dim.comparator_config)
            dimension_scores[dim.dimension_id] = dim_score
            total_score += dim_score * dim.weight
            total_weight += dim.weight

        if total_weight == 0:
            return (0.5, "no_scoring_dimensions", dimension_scores)

        total_score /= total_weight

        return (max(0.0, min(1.0, total_score)), "dimension_based", dimension_scores)

    def _check_hard_constraint(
        self, dim: MatchingDimension, d1: StructuredDemand, d2: StructuredDemand, schema: DemandSchema
    ) -> bool:
        v1 = self._resolve_field(dim, d1, schema)
        v2 = self._resolve_field(dim, d2, schema)
        dim_score, _ = apply_comparator(dim.comparator, v1, v2, dim.comparator_config)
        return dim_score > 0.0

    def _resolve_field(
        self, dim: MatchingDimension, demand: StructuredDemand, schema: DemandSchema
    ) -> Any:
        role = demand.role
        field_keys = dim.field_keys.get(role, [])
        if not field_keys:
            field_keys = dim.field_keys.get(list(dim.field_keys.keys())[0], []) if dim.field_keys else []

        for key in field_keys:
            if key in demand.fields:
                fv = demand.fields[key]
                if fv.normalized is not None:
                    return fv.normalized
                if fv.raw is not None:
                    return fv.raw
                return None
            if key in demand.universal:
                uv = demand.universal[key]
                if isinstance(uv, dict) and "city" in uv:
                    return uv["city"]
                if isinstance(uv, dict) and "amount" in uv:
                    return uv["amount"]
                return uv
        return None

    def _get_schema(self, schema_id: str) -> Optional[DemandSchema]:
        if self.schema_registry:
            return self.schema_registry.get(schema_id)
        from backend.schema_registry import schema_registry as sr
        return sr().get(schema_id)
