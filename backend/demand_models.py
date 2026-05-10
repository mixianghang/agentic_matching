"""
Intermediate Representation (IR) data models for the demand-matching pipeline.

These dataclasses form the contract between demand extraction and matching:
    DemandSchema — defines what fields to extract and how to match them.
    StructuredDemand — a concrete demand instance produced by extraction.
    MatchingDimension — declaratively describes how two demands should be compared.

The IR decouples the extraction engine (backend/demand_engine.py) from the matching
engine (backend/matching/generic_engine.py): neither module needs to understand the
other's internal logic — they only need to agree on the IR schema.

Design doc: design/demand_definition_design_v2.0.md §二 & §五
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class FieldType(str, Enum):
    """Field value types for SchemaField definitions.

    Used to determine how extracted values are coerced and validated,
    and which matching comparator is appropriate for the dimension.
    """
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ENUM = "enum"
    RANGE = "range"
    PRICE = "price"
    DATE = "date"
    LOCATION = "location"
    TAGS = "tags"
    TEXT = "text"


@dataclass
class SchemaField:
    key: str
    display_name: str
    value_type: str
    options: Optional[List[str]] = None
    prompt: str = ""
    required: bool = True
    matching_dimension: Optional[str] = None
    prefill_from: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "value_type": self.value_type,
            "options": self.options,
            "prompt": self.prompt,
            "required": self.required,
            "matching_dimension": self.matching_dimension,
            "prefill_from": self.prefill_from,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SchemaField":
        return cls(
            key=d.get("key", ""),
            display_name=d.get("display_name", ""),
            value_type=d.get("value_type", "text"),
            options=d.get("options"),
            prompt=d.get("prompt", ""),
            required=d.get("required", True),
            matching_dimension=d.get("matching_dimension"),
            prefill_from=d.get("prefill_from"),
        )


@dataclass
class MatchingDimension:
    """Declarative matching rule — the core abstraction of the V2.0 matching engine.

    Instead of hardcoding _score_rental() / _score_dating() / _score_gaming(),
    each demand type declares its matching logic as a list of MatchingDimensions.
    The GenericMatchingEngine executes comparators without understanding domain
    semantics.

    See design/demand_definition_design_v2.0.md §5.1
    """
    dimension_id: str
    name: str
    field_keys: Dict[str, List[str]]
    comparator: str
    comparator_config: Dict[str, Any] = field(default_factory=dict)
    weight: float = 0.0
    is_hard_filter: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension_id": self.dimension_id,
            "name": self.name,
            "field_keys": self.field_keys,
            "comparator": self.comparator,
            "comparator_config": self.comparator_config,
            "weight": self.weight,
            "is_hard_filter": self.is_hard_filter,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MatchingDimension":
        return cls(
            dimension_id=d.get("dimension_id", ""),
            name=d.get("name", ""),
            field_keys=d.get("field_keys", {}),
            comparator=d.get("comparator", "exact"),
            comparator_config=d.get("comparator_config", {}),
            weight=d.get("weight", 0.0),
            is_hard_filter=d.get("is_hard_filter", False),
        )


@dataclass
class DemandSchema:
    """Runtime demand type definition — replaces hardcoded TEMPLATE_REGISTRY.

    Each schema defines what fields to extract from user conversation and
    which MatchingDimensions drive scoring. Schemas are stored in SQLite via
    SchemaRegistry and can be created/evolved at runtime without code changes.

    Lifecycle: pending (proposed by LLM) -> active (after 3 successful uses).
    See design/demand_definition_design_v2.0.md §2.3
    """
    schema_id: str
    demand_type: str
    roles: List[str]
    fields: List[SchemaField] = field(default_factory=list)
    matching_dimensions: List[MatchingDimension] = field(default_factory=list)
    version: int = 1
    status: str = "active"
    usage_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "demand_type": self.demand_type,
            "roles": self.roles,
            "fields": [f.to_dict() for f in self.fields],
            "matching_dimensions": [m.to_dict() for m in self.matching_dimensions],
            "version": self.version,
            "status": self.status,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DemandSchema":
        created_at = d.get("created_at")
        updated_at = d.get("updated_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        return cls(
            schema_id=d.get("schema_id", ""),
            demand_type=d.get("demand_type", ""),
            roles=d.get("roles", []),
            fields=[SchemaField.from_dict(f) for f in d.get("fields", [])],
            matching_dimensions=[MatchingDimension.from_dict(m) for m in d.get("matching_dimensions", [])],
            version=d.get("version", 1),
            status=d.get("status", "active"),
            usage_count=d.get("usage_count", 0),
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
        )


@dataclass
class FieldValue:
    raw: Any
    normalized: Any
    value_type: str
    confidence: float = 1.0
    amount: Optional[float] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    city: Optional[str] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "raw": self.raw,
            "normalized": self.normalized,
            "value_type": self.value_type,
            "confidence": self.confidence,
        }
        if self.amount is not None:
            result["amount"] = self.amount
        if self.currency is not None:
            result["currency"] = self.currency
        if self.period is not None:
            result["period"] = self.period
        if self.city is not None:
            result["city"] = self.city
        if self.min_val is not None:
            result["min_val"] = self.min_val
        if self.max_val is not None:
            result["max_val"] = self.max_val
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FieldValue":
        return cls(
            raw=d.get("raw"),
            normalized=d.get("normalized"),
            value_type=d.get("value_type", "text"),
            confidence=d.get("confidence", 1.0),
            amount=d.get("amount"),
            currency=d.get("currency"),
            period=d.get("period"),
            city=d.get("city"),
            min_val=d.get("min_val"),
            max_val=d.get("max_val"),
        )


@dataclass
class Constraint:
    field: str
    operator: str
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Constraint":
        return cls(
            field=d.get("field", ""),
            operator=d.get("operator", "eq"),
            value=d.get("value"),
        )


@dataclass
class SemanticRequirement:
    text: str
    embedding: Optional[List[float]] = None
    weight: float = 0.3
    is_negotiable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "embedding": self.embedding,
            "weight": self.weight,
            "is_negotiable": self.is_negotiable,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SemanticRequirement":
        return cls(
            text=d.get("text", ""),
            embedding=d.get("embedding"),
            weight=d.get("weight", 0.3),
            is_negotiable=d.get("is_negotiable", True),
        )


@dataclass
class StructuredDemand:
    """The finished demand product — consumed by the matching engine.

    This is the contract between extraction and matching. The extraction engine
    populates it; the GenericMatchingEngine reads it. Neither needs to understand
    the other's internals.

    Structure: universal fields (role, location, budget, timeframe), schema-specific
    fields (e.g., bedrooms, game_name), hard/soft constraints, and semantic
    requirements for vector-based matching.
    """
    demand_id: str
    schema_id: str
    demand_type: str
    role: str
    universal: Dict[str, Any] = field(default_factory=dict)
    fields: Dict[str, FieldValue] = field(default_factory=dict)
    hard_constraints: List[Constraint] = field(default_factory=list)
    soft_preferences: List[Constraint] = field(default_factory=list)
    semantic_requirements: List[SemanticRequirement] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "demand_id": self.demand_id,
            "schema_id": self.schema_id,
            "demand_type": self.demand_type,
            "role": self.role,
            "universal": self.universal,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "hard_constraints": [c.to_dict() for c in self.hard_constraints],
            "soft_preferences": [c.to_dict() for c in self.soft_preferences],
            "semantic_requirements": [s.to_dict() for s in self.semantic_requirements],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StructuredDemand":
        return cls(
            demand_id=d.get("demand_id", ""),
            schema_id=d.get("schema_id", ""),
            demand_type=d.get("demand_type", ""),
            role=d.get("role", ""),
            universal=d.get("universal", {}),
            fields={k: FieldValue.from_dict(v) for k, v in d.get("fields", {}).items()},
            hard_constraints=[Constraint.from_dict(c) for c in d.get("hard_constraints", [])],
            soft_preferences=[Constraint.from_dict(c) for c in d.get("soft_preferences", [])],
            semantic_requirements=[SemanticRequirement.from_dict(s) for s in d.get("semantic_requirements", [])],
        )

    def is_complete(self, schema: DemandSchema) -> bool:
        for field_def in schema.fields:
            if field_def.required and field_def.key not in self.fields:
                return False
        return True


class ExtractionState(str, Enum):
    INIT = "initial"
    SAFETY_CHECK = "safety_check"
    INTENT_DETECT = "intent_detect"
    PROPOSE_SCHEMA = "propose_schema"
    COLLECTING = "collecting"
    CONFIRMING = "confirming"
    MODIFYING = "modifying"
    COMPLETED = "completed"
    REJECT = "reject"
