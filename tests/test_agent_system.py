import pytest
from unittest.mock import Mock, MagicMock, patch
from backend.agent_system import AgentSystem
from backend.models import TaskStatus
from backend.config import TaskType
from backend.demand_models import StructuredDemand, FieldValue


class MockDecisionLLM:
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        import json
        sp = (system_prompt or "").lower()
        up = (user_prompt or "").lower()
        if "classify user intents" in sp or "demand matching platform" in sp:
            if any(k in up for k in ["王者荣耀", "lol", "英雄联盟", "找队友", "组队"]):
                return json.dumps({"demand_type": "gaming", "role": "player", "confidence": 0.95, "to_user": ""})
            if any(k in up for k in ["女朋友", "男朋友", "相亲", "找对象", "交友"]):
                return json.dumps({"demand_type": "dating", "role": "seeker", "confidence": 0.95, "to_user": ""})
            if any(k in up for k in ["租房", "出租", "租个", "房租", "两室", "三室", "一居", "两居"]):
                return json.dumps({"demand_type": "rental", "role": "tenant", "confidence": 0.95, "to_user": ""})
            return json.dumps({"demand_type": None, "role": None, "confidence": 0.2, "to_user": "请说明需求类型"})
        if "intent" in sp:
            return json.dumps({"intent": "continue", "confidence": 0.9})
        return json.dumps({})


class TestAgentSystem:

    @pytest.fixture
    def agent_system(self):
        system = AgentSystem()
        system.demand_engine.llm_client = MockDecisionLLM()
        return system

    def test_demand_engine_type_detection_rental(self, agent_system: AgentSystem):
        session = agent_system.demand_engine.create_session("user_123", "task_456")
        result = agent_system.demand_engine.process_message(session.session_id, "我想在朝阳区租个两居室")
        assert session.demand_type == "rental"

    def test_demand_engine_type_detection_dating(self, agent_system: AgentSystem):
        session = agent_system.demand_engine.create_session("user_123", "task_456")
        result = agent_system.demand_engine.process_message(session.session_id, "我想找个女朋友")
        assert session.demand_type == "dating"

    def test_demand_engine_type_detection_gaming(self, agent_system: AgentSystem):
        session = agent_system.demand_engine.create_session("user_123", "task_456")
        result = agent_system.demand_engine.process_message(session.session_id, "找王者荣耀队友")
        assert session.demand_type == "gaming"

    def test_fallback_response_rental(self, agent_system: AgentSystem):
        response = agent_system._fallback_response("我想租房")
        assert "目标" in response

    def test_fallback_response_dating(self, agent_system: AgentSystem):
        response = agent_system._fallback_response("我想相亲")
        assert "目标" in response

    def test_fallback_response_gaming(self, agent_system: AgentSystem):
        response = agent_system._fallback_response("找游戏队友")
        assert "目标" in response

    def test_generate_response_with_mock(self, agent_system: AgentSystem):
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Mocked response"))]
        mock_client.chat.completions.create.return_value = mock_response
        agent_system.client = mock_client
        response = agent_system.generate_response("System prompt", "User prompt")
        assert response == "Mocked response"
        mock_client.chat.completions.create.assert_called_once()

    def test_generate_response_fallback(self, agent_system: AgentSystem):
        agent_system.client = None
        response = agent_system.generate_response("System prompt", "我想租房")
        assert "目标" in response

    def test_rental_matching(self, agent_system: AgentSystem):
        tenant = StructuredDemand(
            demand_id="d1", schema_id="rental_v1", demand_type="rental", role="tenant",
            fields={
                "property_type": FieldValue(raw="apartment", normalized="apartment", value_type="enum"),
                "bedrooms": FieldValue(raw=3, normalized=3, value_type="integer"),
                "max_price": FieldValue(raw=400, normalized=400, value_type="price", amount=400),
                "location": FieldValue(raw="合肥", normalized="合肥", value_type="geo", city="合肥"),
            },
        )
        landlord = StructuredDemand(
            demand_id="d2", schema_id="rental_v1", demand_type="rental", role="landlord",
            fields={
                "property_type": FieldValue(raw="apartment", normalized="apartment", value_type="enum"),
                "bedrooms": FieldValue(raw=3, normalized=3, value_type="integer"),
                "price": FieldValue(raw=400, normalized=400, value_type="price", amount=400),
                "address": FieldValue(raw="合肥", normalized="合肥", value_type="geo", city="合肥"),
            },
        )
        score, reason, dims = agent_system.matching_engine.compute_match(tenant, landlord)
        assert score > 0.5

    def test_gaming_match_with_alias(self, agent_system: AgentSystem):
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
        score, reason, _ = agent_system.matching_engine.compute_match(d1, d2)
        assert score >= 0.85

    def test_dating_non_overlapping_age_ranges(self, agent_system: AgentSystem):
        d1 = StructuredDemand(
            demand_id="d1", schema_id="dating_v1", demand_type="dating", role="seeker",
            fields={
                "gender_preference": FieldValue(raw="female", normalized="female", value_type="enum"),
                "age_range": FieldValue(raw={"min": 20, "max": 25}, normalized={"min": 20, "max": 25}, value_type="range"),
                "location": FieldValue(raw="上海", normalized="上海", value_type="geo", city="上海"),
            },
        )
        d2 = StructuredDemand(
            demand_id="d2", schema_id="dating_v1", demand_type="dating", role="seeker",
            fields={
                "gender_preference": FieldValue(raw="male", normalized="male", value_type="enum"),
                "age_range": FieldValue(raw={"min": 30, "max": 35}, normalized={"min": 30, "max": 35}, value_type="range"),
                "location": FieldValue(raw="上海", normalized="上海", value_type="geo", city="上海"),
            },
        )
        score, reason, _ = agent_system.matching_engine.compute_match(d1, d2)
        assert score == 0.0
