import pytest
from unittest.mock import Mock, patch
from backend.agent_system import AgentSystem
from backend.models import TaskStatus
from backend.config import TaskType


class MockDecisionLLM:
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        text = (user_prompt or "").lower()
        if "需求类型识别专家" in system_prompt and "请按以下json格式输出" in system_prompt.lower():
            if any(k in text for k in ["租", "房", "rent"]):
                return '{"demand_type":"RENTAL","confidence":0.95,"to_user":""}'
            if any(k in text for k in ["相亲", "交友", "对象", "dating", "女朋友", "男朋友"]):
                return '{"demand_type":"DATING","confidence":0.95,"to_user":""}'
            if any(k in text for k in ["游戏", "队友", "开黑", "gaming"]):
                return '{"demand_type":"GAMING","confidence":0.95,"to_user":""}'
            return '{"demand_type":"UNKNOWN","confidence":0.2,"to_user":""}'
        if "角色识别专家" in system_prompt:
            if any(k in text for k in ["租客", "租房", "tenant"]):
                return "tenant"
            if any(k in text for k in ["房东", "出租", "landlord"]):
                return "landlord"
            return "unknown"
        if "strict intent classifier" in (system_prompt or "").lower():
            return '{"intent":"continue","confidence":0.9}'
        return ""


class TestAgentSystem:
    """Test agent system functionality."""

    @pytest.fixture
    def agent_system(self):
        """Create an agent system instance."""
        system = AgentSystem()
        system.demand_engine.llm_client = MockDecisionLLM()
        return system

    def test_demand_engine_type_detection_rental(self, agent_system: AgentSystem):
        """Test demand engine type detection for rental."""
        from backend.demand_definition_v2 import DemandDefinitionEngineV2
        engine = DemandDefinitionEngineV2(llm_client=MockDecisionLLM())
        session = engine.create_session("user_123", "task_456")

        # 处理租房相关消息
        result = engine.process_message(session.session_id, "我想在朝阳区租个两居室")

        # 验证类型被正确识别为 rental
        assert session.demand_type == TaskType.RENTAL

    def test_demand_engine_type_detection_dating(self, agent_system: AgentSystem):
        """Test demand engine type detection for dating."""
        from backend.demand_definition_v2 import DemandDefinitionEngineV2
        engine = DemandDefinitionEngineV2(llm_client=MockDecisionLLM())
        session = engine.create_session("user_123", "task_456")

        # 处理相亲相关消息
        result = engine.process_message(session.session_id, "我想找个女朋友")

        # 验证类型被正确识别为 dating
        assert session.demand_type == TaskType.DATING

    def test_demand_engine_type_detection_gaming(self, agent_system: AgentSystem):
        """Test demand engine type detection for gaming."""
        from backend.demand_definition_v2 import DemandDefinitionEngineV2
        engine = DemandDefinitionEngineV2(llm_client=MockDecisionLLM())
        session = engine.create_session("user_123", "task_456")

        # 处理游戏相关消息
        result = engine.process_message(session.session_id, "找王者荣耀队友")

        # 验证类型被正确识别为 gaming
        assert session.demand_type == TaskType.GAMING

    def test_fallback_response_rental(self, agent_system: AgentSystem):
        """Test fallback response is generic and language-agnostic."""
        response = agent_system._fallback_response("我想租房")
        assert "目标" in response
    
    def test_fallback_response_dating(self, agent_system: AgentSystem):
        """Test fallback response is generic and language-agnostic."""
        response = agent_system._fallback_response("我想相亲")
        assert "目标" in response
    
    def test_fallback_response_gaming(self, agent_system: AgentSystem):
        """Test fallback response is generic and language-agnostic."""
        response = agent_system._fallback_response("找游戏队友")
        assert "目标" in response
    
    def test_generate_response_with_mock(self, agent_system: AgentSystem):
        """Test generate response with mocked OpenAI client."""
        # Mock the OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Mocked response"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        agent_system.client = mock_client
        
        response = agent_system.generate_response(
            "System prompt",
            "User prompt"
        )
        
        assert response == "Mocked response"
        mock_client.chat.completions.create.assert_called_once()
    
    def test_generate_response_fallback(self, agent_system: AgentSystem):
        """Test fallback when OpenAI client is None."""
        agent_system.client = None
        
        response = agent_system.generate_response(
            "System prompt",
            "我想租房"
        )
        
        # Should return generic fallback response
        assert "目标" in response

    def test_rental_match_with_city_normalization_and_monthly_price(self, agent_system: AgentSystem):
        tenant = {
            "demand_type": "rental",
            "role": "tenant",
            "values": {
                "location": "合肥",
                "bedrooms": 3,
                "max_price": 400,
                "max_price_period": "weekly",
            },
        }
        landlord = {
            "demand_type": "rental",
            "role": "landlord",
            "values": {
                "address": "合肥包河区",
                "bedrooms": 3,
                "price": 1600,
                "price_period": "monthly",
            },
        }

        assert agent_system._rental_compatible(tenant, landlord) is True

    def test_gaming_match_with_alias(self, agent_system: AgentSystem):
        d1 = {"demand_type": "gaming", "role": "player", "values": {"game_name": "LOL"}}
        d2 = {"demand_type": "gaming", "role": "player", "values": {"game_name": "英雄联盟"}}
        assert agent_system._gaming_compatible(d1, d2) is True

    def test_dating_match_rejects_non_overlapping_age_ranges(self, agent_system: AgentSystem):
        d1 = {
            "demand_type": "dating",
            "role": "seeker",
            "values": {
                "gender": "male",
                "gender_preference": "female",
                "location": "上海",
                "age_range": {"min": 20, "max": 25},
            },
        }
        d2 = {
            "demand_type": "dating",
            "role": "seeker",
            "values": {
                "gender": "female",
                "gender_preference": "male",
                "location": "上海浦东",
                "age_range": {"min": 30, "max": 35},
            },
        }
        assert agent_system._dating_compatible(d1, d2) is False
