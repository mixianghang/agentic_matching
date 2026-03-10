import pytest
from unittest.mock import Mock, patch
from backend.agent_system import AgentSystem
from backend.models import TaskStatus
from backend.config import TaskType


class TestAgentSystem:
    """Test agent system functionality."""

    @pytest.fixture
    def agent_system(self):
        """Create an agent system instance."""
        return AgentSystem()

    def test_demand_engine_type_detection_rental(self, agent_system: AgentSystem):
        """Test demand engine type detection for rental."""
        from backend.demand_definition_v2 import DemandDefinitionEngineV2
        engine = DemandDefinitionEngineV2()
        session = engine.create_session("user_123", "task_456")

        # 处理租房相关消息
        result = engine.process_message(session.session_id, "我想在朝阳区租个两居室")

        # 验证类型被正确识别为 rental
        assert session.demand_type == TaskType.RENTAL

    def test_demand_engine_type_detection_dating(self, agent_system: AgentSystem):
        """Test demand engine type detection for dating."""
        from backend.demand_definition_v2 import DemandDefinitionEngineV2
        engine = DemandDefinitionEngineV2()
        session = engine.create_session("user_123", "task_456")

        # 处理相亲相关消息
        result = engine.process_message(session.session_id, "我想找个女朋友")

        # 验证类型被正确识别为 dating
        assert session.demand_type == TaskType.DATING

    def test_demand_engine_type_detection_gaming(self, agent_system: AgentSystem):
        """Test demand engine type detection for gaming."""
        from backend.demand_definition_v2 import DemandDefinitionEngineV2
        engine = DemandDefinitionEngineV2()
        session = engine.create_session("user_123", "task_456")

        # 处理游戏相关消息
        result = engine.process_message(session.session_id, "找王者荣耀队友")

        # 验证类型被正确识别为 gaming
        assert session.demand_type == TaskType.GAMING

    def test_fallback_response_rental(self, agent_system: AgentSystem):
        """Test fallback response for rental keywords."""
        response = agent_system._fallback_response("我想租房")
        assert "住房" in response or "房子" in response
    
    def test_fallback_response_dating(self, agent_system: AgentSystem):
        """Test fallback response for dating keywords."""
        response = agent_system._fallback_response("我想相亲")
        assert "朋友" in response or "对象" in response
    
    def test_fallback_response_gaming(self, agent_system: AgentSystem):
        """Test fallback response for gaming keywords."""
        response = agent_system._fallback_response("找游戏队友")
        assert "游戏" in response or "玩" in response
    
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
        
        # Should return fallback response
        assert "住房" in response or "房子" in response
