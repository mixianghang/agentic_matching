import json
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from backend.demand_models import (
    DemandSchema, SchemaField, MatchingDimension, FieldValue,
    Constraint, SemanticRequirement, StructuredDemand, ExtractionState,
)
from backend.schema_registry import SchemaRegistry, schema_registry, _build_default_schemas
from backend.content_safety import ContentSafetyFilter
from backend.matching.comparators import (
    compare_exact, compare_enum_compatible, compare_range_overlap,
    compare_numeric_compatibility, compare_geo_proximity, compare_semantic_similarity,
    apply_comparator, COMPARATOR_REGISTRY,
)
from backend.matching.generic_engine import GenericMatchingEngine


class TestDemandModels:

    def test_schema_field_roundtrip(self):
        f = SchemaField(key="bedrooms", display_name="卧室", value_type="integer",
                        options=None, prompt="几间卧室？", required=True,
                        matching_dimension="bedrooms_match", prefill_from="prefs.bedrooms")
        d = f.to_dict()
        f2 = SchemaField.from_dict(d)
        assert f2.key == "bedrooms"
        assert f2.value_type == "integer"
        assert f2.matching_dimension == "bedrooms_match"

    def test_matching_dimension_roundtrip(self):
        md = MatchingDimension(
            dimension_id="city_match", name="城市匹配",
            field_keys={"tenant": ["location"], "landlord": ["address"]},
            comparator="geo_proximity", weight=0.3, is_hard_filter=True,
            comparator_config={"max_distance_km": 5},
        )
        d = md.to_dict()
        md2 = MatchingDimension.from_dict(d)
        assert md2.dimension_id == "city_match"
        assert md2.is_hard_filter is True
        assert md2.weight == 0.3

    def test_demand_schema_roundtrip(self):
        schema = DemandSchema(
            schema_id="test_v1", demand_type="test", roles=["buyer", "seller"],
            fields=[
                SchemaField(key="item", display_name="物品", value_type="text", required=True,
                            matching_dimension="item_match"),
                SchemaField(key="price", display_name="价格", value_type="price", required=True,
                            matching_dimension="price_compat"),
            ],
            matching_dimensions=[
                MatchingDimension(dimension_id="item_match", name="物品匹配",
                                  field_keys={"buyer": ["item"], "seller": ["item"]},
                                  comparator="exact", weight=0.5),
                MatchingDimension(dimension_id="price_compat", name="价格兼容",
                                  field_keys={"buyer": ["price"], "seller": ["price"]},
                                  comparator="numeric_compatibility", weight=0.5),
            ],
        )
        d = schema.to_dict()
        s2 = DemandSchema.from_dict(d)
        assert s2.schema_id == "test_v1"
        assert len(s2.fields) == 2
        assert len(s2.matching_dimensions) == 2

    def test_structured_demand_is_complete(self):
        schema = DemandSchema(
            schema_id="test_v1", demand_type="test", roles=["user"],
            fields=[
                SchemaField(key="a", display_name="A", value_type="text", required=True),
                SchemaField(key="b", display_name="B", value_type="text", required=True),
                SchemaField(key="c", display_name="C", value_type="text", required=False),
            ],
            matching_dimensions=[],
        )
        sd = StructuredDemand(
            demand_id="d1", schema_id="test_v1", demand_type="test", role="user",
            fields={"a": FieldValue(raw="x", normalized="x", value_type="text")},
        )
        assert sd.is_complete(schema) is False
        sd.fields["b"] = FieldValue(raw="y", normalized="y", value_type="text")
        assert sd.is_complete(schema) is True

    def test_structured_demand_roundtrip(self):
        sd = StructuredDemand(
            demand_id="d1", schema_id="rental_v1", demand_type="rental", role="tenant",
            universal={"role": "tenant"},
            fields={
                "bedrooms": FieldValue(raw=2, normalized=2, value_type="integer"),
                "max_price": FieldValue(raw=600, normalized=600, value_type="price", amount=600, currency="AUD", period="weekly"),
                "location": FieldValue(raw="墨尔本", normalized="墨尔本", value_type="geo", city="墨尔本"),
            },
            semantic_requirements=[
                SemanticRequirement(text="必须朝北有阳台"),
            ],
        )
        d = sd.to_dict()
        sd2 = StructuredDemand.from_dict(d)
        assert sd2.demand_type == "rental"
        assert sd2.role == "tenant"
        assert sd2.fields["bedrooms"].normalized == 2
        assert sd2.fields["max_price"].amount == 600
        assert len(sd2.semantic_requirements) == 1


class TestSchemaRegistry:

    @pytest.fixture(autouse=True)
    def _reset_registry(self):
        sr = SchemaRegistry(":memory:")
        sr._schemas.clear()
        sr._seed_defaults()
        yield

    def test_default_schemas_seeded(self):
        sr = schema_registry()
        active = sr.list_active()
        assert len(active) >= 3
        types = {s.demand_type for s in active}
        assert "rental" in types
        assert "dating" in types
        assert "gaming" in types

    def test_get_schema(self):
        sr = schema_registry()
        rental = sr.get("rental_v1")
        assert rental is not None
        assert rental.demand_type == "rental"
        assert len(rental.roles) == 2
        assert "tenant" in rental.roles
        assert "landlord" in rental.roles

    def test_get_by_type(self):
        sr = schema_registry()
        rental_schemas = sr.get_by_type("rental")
        assert len(rental_schemas) >= 1
        assert rental_schemas[0].demand_type == "rental"

    def test_register_new_schema(self):
        sr = schema_registry()
        new_schema = DemandSchema(
            schema_id="carpool_v1", demand_type="carpool",
            roles=["driver", "passenger"],
            fields=[
                SchemaField(key="route", display_name="路线", value_type="text", required=True),
                SchemaField(key="departure_time", display_name="出发时间", value_type="text", required=True),
            ],
            matching_dimensions=[
                MatchingDimension(dimension_id="route_match", name="路线匹配",
                                  field_keys={"driver": ["route"], "passenger": ["route"]},
                                  comparator="exact", weight=1.0),
            ],
            status="pending", usage_count=0,
        )
        sr.register(new_schema)
        retrieved = sr.get("carpool_v1")
        assert retrieved is not None
        assert retrieved.demand_type == "carpool"
        assert retrieved.status == "pending"

    def test_increment_usage_auto_activates(self):
        sr = schema_registry()
        new_schema = DemandSchema(
            schema_id="petcare_v1", demand_type="petcare",
            roles=["owner", "walker"],
            fields=[SchemaField(key="pet_type", display_name="宠物类型", value_type="text", required=True)],
            matching_dimensions=[
                MatchingDimension(dimension_id="pet_match", name="宠物匹配",
                                  field_keys={"owner": ["pet_type"], "walker": ["pet_type"]},
                                  comparator="exact", weight=1.0),
            ],
            status="pending", usage_count=0,
        )
        sr.register(new_schema)
        assert sr.get("petcare_v1").status == "pending"

        sr.increment_usage("petcare_v1")
        sr.increment_usage("petcare_v1")
        assert sr.get("petcare_v1").status == "pending"

        sr.increment_usage("petcare_v1")
        assert sr.get("petcare_v1").status == "active"

    def test_delete_schema(self):
        sr = schema_registry()
        new_schema = DemandSchema(
            schema_id="temp_v1", demand_type="temp", roles=["user"],
            fields=[SchemaField(key="x", display_name="X", value_type="text", required=True)],
            matching_dimensions=[],
        )
        sr.register(new_schema)
        assert sr.get("temp_v1") is not None
        assert sr.delete("temp_v1") is True
        assert sr.get("temp_v1") is None
        assert sr.delete("nonexistent") is False

    def test_list_by_status(self):
        sr = schema_registry()
        active = sr.list_by_status("active")
        pending = sr.list_by_status("pending")
        assert len(active) >= 3
        assert len(pending) == 0

    def test_matching_dimensions_have_weights_summing_to_one(self):
        sr = schema_registry()
        for schema in sr.list_active():
            if schema.matching_dimensions:
                total = sum(d.weight for d in schema.matching_dimensions)
                assert abs(total - 1.0) < 0.05, f"{schema.schema_id} weights sum to {total}"


class TestContentSafety:

    def test_blocklist_drugs(self):
        cf = ContentSafetyFilter(llm_client=None)
        r = cf.check("帮我找一些大麻")
        assert r["is_safe"] is False
        assert r["flagged_categories"] == ["blocklist"]

    def test_blocklist_adult(self):
        cf = ContentSafetyFilter(llm_client=None)
        r = cf.check("约炮")
        assert r["is_safe"] is False

    def test_blocklist_gambling(self):
        cf = ContentSafetyFilter(llm_client=None)
        r = cf.check("赌场在哪里")
        assert r["is_safe"] is False

    def test_safe_message_passes(self):
        cf = ContentSafetyFilter(llm_client=None)
        r = cf.check("我想在墨尔本租房，两室一厅，预算600刀")
        assert r["is_safe"] is True

    def test_safe_message_english(self):
        cf = ContentSafetyFilter(llm_client=None)
        r = cf.check("Looking for a gaming partner for League of Legends")
        assert r["is_safe"] is True

    def test_schema_domain_allowed(self):
        cf = ContentSafetyFilter(llm_client=None)
        assert cf.is_schema_domain_allowed("rental") is True
        assert cf.is_schema_domain_allowed("dating") is True
        assert cf.is_schema_domain_allowed("drugs") is False
        assert cf.is_schema_domain_allowed("adult_content") is False
        assert cf.is_schema_domain_allowed("gambling") is False

    def test_reject_messages(self):
        cf = ContentSafetyFilter(llm_client=None)
        assert "无法" in cf.get_reject_message("nsfw")
        assert "非法" in cf.get_reject_message("illegal")
        assert "友善" in cf.get_reject_message("harassment")


class TestComparators:

    def test_exact_match(self):
        score, _ = compare_exact("hello", "hello")
        assert score == 1.0
        score, _ = compare_exact("hello", "world")
        assert score == 0.0
        score, _ = compare_exact(None, "hello")
        assert score == 0.5

    def test_enum_compatible(self):
        score, _ = compare_enum_compatible("male", "male")
        assert score == 1.0
        score, _ = compare_enum_compatible("any", "female")
        assert score == 1.0
        score, _ = compare_enum_compatible("male", "any")
        assert score == 1.0
        score, _ = compare_enum_compatible("male", "female")
        assert score == 0.0

    def test_range_overlap(self):
        r1 = {"min": 25, "max": 32}
        r2 = {"min": 28, "max": 35}
        score, _ = compare_range_overlap(r1, r2)
        assert 0.5 < score < 1.0

        r3 = {"min": 20, "max": 25}
        r4 = {"min": 30, "max": 40}
        score2, _ = compare_range_overlap(r3, r4)
        assert score2 == 0.0

    def test_numeric_compatibility(self):
        score, _ = compare_numeric_compatibility(600, 500)
        assert 0.8 < score < 1.0
        score, _ = compare_numeric_compatibility(500, 600)
        assert 0.5 < score < 0.9
        score, _ = compare_numeric_compatibility(None, 500)
        assert score == 0.5

    def test_geo_proximity_same_city(self):
        score, _ = compare_geo_proximity("墨尔本CBD", "墨尔本")
        assert score == 1.0
        score, _ = compare_geo_proximity("悉尼", "墨尔本")
        assert score == 0.0

    def test_geo_proximity_english(self):
        score, _ = compare_geo_proximity("Melbourne, Australia", "Melbourne")
        assert score == 1.0

    def test_apply_comparator_dispatcher(self):
        score, _ = apply_comparator("exact", "x", "x")
        assert score == 1.0
        score, _ = apply_comparator("unknown", "x", "x")
        assert score == 0.5

    def test_all_comparators_registered(self):
        assert "exact" in COMPARATOR_REGISTRY
        assert "enum_compatible" in COMPARATOR_REGISTRY
        assert "range_overlap" in COMPARATOR_REGISTRY
        assert "numeric_compatibility" in COMPARATOR_REGISTRY
        assert "geo_proximity" in COMPARATOR_REGISTRY
        assert "semantic_similarity" in COMPARATOR_REGISTRY


class TestGenericMatchingEngine:

    @pytest.fixture
    def engine(self):
        sr = SchemaRegistry(":memory:")
        sr._schemas.clear()
        sr._seed_defaults()
        return GenericMatchingEngine(schema_registry=sr)

    def test_rental_matching_tenant_landlord(self, engine):
        tenant = StructuredDemand(
            demand_id="d1", schema_id="rental_v1", demand_type="rental", role="tenant",
            fields={
                "property_type": FieldValue(raw="apartment", normalized="apartment", value_type="enum"),
                "bedrooms": FieldValue(raw=2, normalized=2, value_type="integer"),
                "max_price": FieldValue(raw=600, normalized=600, value_type="price", amount=600),
                "location": FieldValue(raw="墨尔本CBD", normalized="墨尔本CBD", value_type="geo", city="墨尔本"),
            },
        )
        landlord = StructuredDemand(
            demand_id="d2", schema_id="rental_v1", demand_type="rental", role="landlord",
            fields={
                "property_type": FieldValue(raw="apartment", normalized="apartment", value_type="enum"),
                "bedrooms": FieldValue(raw=2, normalized=2, value_type="integer"),
                "price": FieldValue(raw=500, normalized=500, value_type="price", amount=500),
                "address": FieldValue(raw="墨尔本CBD", normalized="墨尔本CBD", value_type="geo", city="墨尔本"),
            },
        )
        score, reason, dims = engine.compute_match(tenant, landlord)
        assert score > 0.5
        assert "dimension_based" in reason
        assert "bedrooms_match" in dims
        assert "price_compat" in dims

    def test_rental_hard_filter_different_city(self, engine):
        tenant = StructuredDemand(
            demand_id="d1", schema_id="rental_v1", demand_type="rental", role="tenant",
            fields={
                "property_type": FieldValue(raw="apartment", normalized="apartment", value_type="enum"),
                "bedrooms": FieldValue(raw=2, normalized=2, value_type="integer"),
                "max_price": FieldValue(raw=600, normalized=600, value_type="price", amount=600),
                "location": FieldValue(raw="墨尔本", normalized="墨尔本", value_type="geo", city="墨尔本"),
            },
        )
        landlord = StructuredDemand(
            demand_id="d2", schema_id="rental_v1", demand_type="rental", role="landlord",
            fields={
                "property_type": FieldValue(raw="apartment", normalized="apartment", value_type="enum"),
                "bedrooms": FieldValue(raw=2, normalized=2, value_type="integer"),
                "price": FieldValue(raw=500, normalized=500, value_type="price", amount=500),
                "address": FieldValue(raw="悉尼", normalized="悉尼", value_type="geo", city="悉尼"),
            },
        )
        score, reason, _ = engine.compute_match(tenant, landlord)
        assert score == 0.0
        assert "hard_filter" in reason

    def test_dating_matching(self, engine):
        d1 = StructuredDemand(
            demand_id="d1", schema_id="dating_v1", demand_type="dating", role="seeker",
            fields={
                "gender_preference": FieldValue(raw="any", normalized="any", value_type="enum"),
                "age_range": FieldValue(raw={"min": 25, "max": 32}, normalized={"min": 25, "max": 32}, value_type="range"),
                "location": FieldValue(raw="墨尔本", normalized="墨尔本", value_type="geo", city="墨尔本"),
            },
        )
        d2 = StructuredDemand(
            demand_id="d2", schema_id="dating_v1", demand_type="dating", role="seeker",
            fields={
                "gender_preference": FieldValue(raw="any", normalized="any", value_type="enum"),
                "age_range": FieldValue(raw={"min": 28, "max": 35}, normalized={"min": 28, "max": 35}, value_type="range"),
                "location": FieldValue(raw="墨尔本", normalized="墨尔本", value_type="geo", city="墨尔本"),
            },
        )
        score, reason, dims = engine.compute_match(d1, d2)
        assert score >= 0.15, f"expected >= 0.15, got {score}"

    def test_gaming_matching(self, engine):
        d1 = StructuredDemand(
            demand_id="d1", schema_id="gaming_v1", demand_type="gaming", role="player",
            fields={
                "game_name": FieldValue(raw="league of legends", normalized="league of legends", value_type="text"),
                "rank": FieldValue(raw="钻石", normalized="钻石", value_type="text"),
            },
        )
        d2 = StructuredDemand(
            demand_id="d2", schema_id="gaming_v1", demand_type="gaming", role="player",
            fields={
                "game_name": FieldValue(raw="league of legends", normalized="league of legends", value_type="text"),
                "rank": FieldValue(raw="钻石", normalized="钻石", value_type="text"),
            },
        )
        score, reason, _ = engine.compute_match(d1, d2)
        assert score > 0.8

    def test_gaming_hard_filter_different_game(self, engine):
        d1 = StructuredDemand(
            demand_id="d1", schema_id="gaming_v1", demand_type="gaming", role="player",
            fields={
                "game_name": FieldValue(raw="league of legends", normalized="league of legends", value_type="text"),
                "rank": FieldValue(raw="钻石", normalized="钻石", value_type="text"),
            },
        )
        d2 = StructuredDemand(
            demand_id="d2", schema_id="gaming_v1", demand_type="gaming", role="player",
            fields={
                "game_name": FieldValue(raw="pubg", normalized="pubg", value_type="text"),
                "rank": FieldValue(raw="钻石", normalized="钻石", value_type="text"),
            },
        )
        score, reason, _ = engine.compute_match(d1, d2)
        assert score == 0.0


class TestDemandExtractionV3Integration:

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        return llm

    @pytest.fixture
    def engine(self, mock_llm):
        from backend.demand_engine import DemandEngine
        import backend.schema_registry as sr_module
        sr = sr_module.SchemaRegistry(":memory:")
        sr._schemas.clear()
        sr._seed_defaults()
        sr_module.SchemaRegistry._instance = sr
        sr_module.SchemaRegistry._instance._initialized = True
        eng = DemandEngine(llm_client=mock_llm)
        eng.registry = sr
        return eng

    def test_session_creation(self, engine):
        session = engine.create_session("user1", "task1")
        assert session.session_id is not None
        assert session.state == ExtractionState.INIT

    def test_safety_reject(self, engine):
        engine.safety_filter.llm_client = None
        session = engine.create_session("user1")
        result = engine.process_message(session.session_id, "帮我找大麻")
        assert result.get("rejected") is True
        assert result["state"] == "reject"

    def test_intent_detect_rental(self, engine, mock_llm):
        engine.safety_filter.llm_client = None
        mock_llm.generate_response.return_value = json.dumps({
            "demand_type": "rental", "role": "tenant", "confidence": 0.9, "to_user": ""
        })
        session = engine.create_session("user1")
        session.state = ExtractionState.SAFETY_CHECK
        session.safety_label = "safe"
        result = engine.process_message(session.session_id, "想在墨尔本租房")
        assert result["success"] is True
        assert result["state"] in ("collecting", "intent_detect")

    def test_intent_detect_new_type_proposes_schema(self, engine, mock_llm):
        engine.safety_filter.llm_client = None
        call_count = [0]

        def side_effect(sys_prompt, user_prompt):
            call_count[0] += 1
            if "Classify this user" in sys_prompt:
                return json.dumps({"demand_type": "unknown_type", "role": "seeker", "confidence": 0.8, "to_user": ""})
            return json.dumps({
                "demand_type": "pet_care",
                "roles": ["owner", "walker"],
                "fields": [
                    {"key": "pet_type", "display_name": "宠物类型", "value_type": "text", "required": True, "prompt": "什么宠物？"},
                    {"key": "schedule", "display_name": "时间安排", "value_type": "text", "required": True, "prompt": "什么时间？"},
                ],
                "matching_dimensions": [
                    {"dimension_id": "pet_match", "name": "宠物匹配", "field_keys": {"owner": ["pet_type"], "walker": ["pet_type"]}, "comparator": "exact", "weight": 1.0},
                ],
            })

        mock_llm.generate_response.side_effect = side_effect
        session = engine.create_session("user1")
        session.state = ExtractionState.SAFETY_CHECK
        session.safety_label = "safe"
        result = engine.process_message(session.session_id, "想找个帮我遛狗的人")
        assert result["success"] is True
        schemas = engine.registry.list_all()
        types = {s.demand_type for s in schemas}
        assert "rental" in types

    def test_collecting_fields(self, engine, mock_llm):
        engine.safety_filter.llm_client = None
        mock_llm.generate_response.side_effect = [
            json.dumps({"demand_type": "rental", "role": "tenant", "confidence": 0.9, "to_user": ""}),
            json.dumps({"extracted": {"property_type": "apartment", "bedrooms": 2, "max_price": 600, "location": "墨尔本CBD"}, "confidence": 0.9}),
            json.dumps({"to_user": "还有其他要求吗？"}),
        ]
        session = engine.create_session("user1")
        session.state = ExtractionState.SAFETY_CHECK
        session.safety_label = "safe"
        result = engine.process_message(session.session_id, "想在墨尔本租房，两室一厅公寓，预算600刀一周")
        assert result["success"] is True
        assert len(session.values) >= 3

    def test_collecting_missing_required_shows_missing(self, engine, mock_llm):
        engine.safety_filter.llm_client = None
        mock_llm.generate_response.side_effect = [
            json.dumps({"demand_type": "rental", "role": "tenant", "confidence": 0.9, "to_user": ""}),
            json.dumps({"extracted": {"bedrooms": 2}, "confidence": 0.9}),
            json.dumps({"to_user": "还有其他要求吗？"}),
            json.dumps({"extracted": {}, "confidence": 0.9}),
            json.dumps({"intent": "complete", "confidence": 0.9}),
        ]
        session = engine.create_session("user1")
        session.state = ExtractionState.SAFETY_CHECK
        session.safety_label = "safe"
        engine.process_message(session.session_id, "我要租房，两室")
        result = engine.process_message(session.session_id, "确认")
        assert result["success"] is True
        assert "必填" in result.get("message", "")

    def test_full_rental_extraction_flow(self, engine, mock_llm):
        engine.safety_filter.llm_client = None
        call_seq = iter([
            json.dumps({"demand_type": "rental", "role": "tenant", "confidence": 0.9, "to_user": ""}),
            json.dumps({"extracted": {"property_type": "apartment", "bedrooms": 2, "max_price": 600, "location": "墨尔本CBD"}, "confidence": 0.9}),
            json.dumps({"to_user": "还有其他要求吗？"}),
            json.dumps({"extracted": {"move_in_date": "下个月"}, "confidence": 0.9}),
            json.dumps({"intent": "complete", "confidence": 0.9}),
        ])
        mock_llm.generate_response.side_effect = lambda *a, **kw: next(call_seq)

        session = engine.create_session("user1")
        session.state = ExtractionState.SAFETY_CHECK
        session.safety_label = "safe"

        r = engine.process_message(session.session_id, "想在墨尔本CBD租房，两室一厅公寓，预算600刀一周")
        assert r["state"] == "collecting"

        r = engine.process_message(session.session_id, "下个月入住")
        assert r["state"] in ("confirming", "collecting")

        r = engine.process_message(session.session_id, "确认")
        assert r["state"] == "completed"
        assert r["completed"] is True
        assert "structured_demand" in r

    def test_build_structured_demand(self, engine, mock_llm):
        engine.safety_filter.llm_client = None
        mock_llm.generate_response.side_effect = [
            json.dumps({"demand_type": "rental", "role": "tenant", "confidence": 0.9, "to_user": ""}),
            json.dumps({"extracted": {"property_type": "apartment", "bedrooms": 2, "max_price": 600, "location": "墨尔本CBD", "move_in_date": "2026-06"}, "confidence": 0.9}),
            json.dumps({"to_user": "好的，请确认"}),
        ]
        session = engine.create_session("user1")
        session.state = ExtractionState.SAFETY_CHECK
        session.safety_label = "safe"
        session.schema = engine.registry.get("rental_v1")
        session.demand_type = "rental"
        session.role = "tenant"
        session.values = {"property_type": "apartment", "bedrooms": 2, "max_price": 600, "location": "墨尔本CBD", "move_in_date": "2026-06"}
        session.filled_fields = list(session.values.keys())
        session.pending_fields = [f for f in session.schema.fields if f.key not in session.values]

        sd = engine.build_structured_demand(session)
        assert sd.demand_type == "rental"
        assert sd.role == "tenant"
        assert "bedrooms" in sd.fields
        assert sd.fields["bedrooms"].normalized == 2
        assert sd.fields["max_price"].amount == 600
        assert sd.is_complete(session.schema) is True

    def test_get_demand_data(self, engine):
        session = engine.create_session("user1")
        session.demand_type = "rental"
        session.role = "tenant"
        session.state = ExtractionState.COMPLETED
        session.schema = engine.registry.get("rental_v1")
        session.values = {"property_type": "apartment"}

        data = engine.get_demand_data(session.session_id)
        assert data is not None
        assert data["demand_type"] == "rental"
        assert data["is_complete"] is True
