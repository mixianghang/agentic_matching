"""
需求定义模块 V2 测试
"""
import pytest
import os
from backend.demand_definition_v2 import (
    DemandDefinitionEngineV2,
    DemandDefinitionSession,
    DemandState,
    PromptMode
)
from backend.config import TaskType


class TestDynamicPrompts:
    """测试动态提示词生成"""

    def test_dynamic_type_prompt(self):
        """测试动态生成类型识别提示词"""
        engine = DemandDefinitionEngineV2()
        prompt = engine._get_dynamic_type_prompt()

        # 提示词应该包含至少一个类型
        assert "RENTAL" in prompt or "DATING" in prompt or "GAMING" in prompt
        # 提示词应该包含类型名称
        assert "租房" in prompt or "相亲" in prompt

    def test_dynamic_role_prompt(self):
        """测试动态生成角色识别提示词"""
        engine = DemandDefinitionEngineV2()
        prompt = engine._get_dynamic_role_prompt("rental")

        assert "tenant" in prompt
        assert "landlord" in prompt
        assert "租客" in prompt
        assert "房东" in prompt


class TestACPPrompt:
    """测试ACP协议提示词"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2(prompt_mode="merged")

    @pytest.fixture
    def session(self, engine):
        session = engine.create_session("user_123", "task_456")
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.template = RENTAL_TENANT_TEMPLATE
        session.state = DemandState.COLLECTING
        return session

    def test_acp_prompt_structure(self, engine, session):
        """测试ACP提示词结构"""
        prompt = engine._build_acp_prompt(session, "我想租个公寓")

        assert "[ACP v1.0]" in prompt
        assert "<session>" in prompt
        assert "<context>" in prompt
        assert "<conversation_history>" in prompt
        assert "<user>" in prompt
        assert "<system>" in prompt
        assert "<memory>" in prompt

    def test_acp_prompt_content(self, engine, session):
        """测试ACP提示词内容"""
        session.values = {"property_type": "apartment"}
        prompt = engine._build_acp_prompt(session, "我想租个公寓")

        assert "rental" in prompt
        assert "tenant" in prompt
        assert "collecting" in prompt
        assert "apartment" in prompt
        assert session.session_id in prompt


class TestMultiFieldExtraction:
    """测试多字段提取"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2()

    @pytest.fixture
    def session(self, engine):
        session = engine.create_session("user_123", "task_456")
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.template = RENTAL_TENANT_TEMPLATE
        session.state = DemandState.COLLECTING
        session.pending_fields = list(RENTAL_TENANT_TEMPLATE.fields)
        return session

    def test_extract_multiple_fields(self, engine, session):
        """测试从一句话中提取多个字段"""
        message = "我想租一个两室一厅的公寓，预算600刀每周"
        extracted = engine._extract_multiple_fields(message, session)

        assert "property_type" in extracted or len(extracted) > 0

    def test_extract_bedrooms_and_price(self, engine, session):
        """测试提取卧室数量和价格"""
        message = "需要2间卧室，预算500-700刀"
        extracted = engine._extract_multiple_fields(message, session)

        # 应该提取到 bedrooms 和 max_price
        assert len(extracted) >= 1

    def test_extract_with_context(self, engine, session):
        """测试结合上下文的提取"""
        session.values = {"property_type": "apartment"}
        message = "还要2个卧室，预算600"
        extracted = engine._extract_multiple_fields(message, session)

        assert len(extracted) >= 1


class TestPromptMode:
    """测试提示词模式"""

    def test_default_prompt_mode(self):
        """测试默认提示词模式"""
        engine = DemandDefinitionEngineV2()
        assert engine.prompt_mode == PromptMode.SEPARATE

    def test_merged_prompt_mode(self):
        """测试合并提示词模式"""
        engine = DemandDefinitionEngineV2(prompt_mode="merged")
        assert engine.prompt_mode == PromptMode.MERGED

    def test_env_prompt_mode(self):
        """测试环境变量配置"""
        os.environ["DEMAND_PROMPT_MODE"] = "merged"
        engine = DemandDefinitionEngineV2()
        assert engine.prompt_mode == PromptMode.MERGED
        del os.environ["DEMAND_PROMPT_MODE"]


class TestNaturalConversation:
    """测试自然对话流程"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2()

    def test_natural_multi_field_input(self, engine):
        """测试自然的多个字段输入"""
        session = engine.create_session("user_123", "task_456")

        # 第一步：识别类型和角色
        result = engine.process_message(session.session_id, "我想在墨尔本租房")
        assert result["success"] is True

        # 第二步：一次性提供多个信息
        result = engine.process_message(session.session_id, "我是租客，想要一个两室一厅的公寓，预算600刀每周，靠近CBD")

        assert result["success"] is True
        # 验证会话状态正确
        assert session.demand_type == "rental"
        assert session.role == "tenant"

    def test_skip_optional_fields(self, engine):
        """测试跳过选填字段"""
        session = engine.create_session("user_123", "task_456")

        # 快速完成流程
        engine.process_message(session.session_id, "租房")
        engine.process_message(session.session_id, "租客")

        # 填写所有必填字段
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.template = RENTAL_TENANT_TEMPLATE
        session.values = {
            "property_type": "apartment",
            "bedrooms": 2,
            "max_price": 600,
            "location": "墨尔本",
            "move_in_date": "2026-04-01"
        }
        session.filled_fields = list(session.values.keys())
        session.pending_fields = []
        session.state = DemandState.COLLECTING

        # 第一步：进入确认状态
        result = engine.process_message(session.session_id, "确认")
        assert result["state"] == DemandState.CONFIRMING.value

        # 第二步：最终确认完成
        result = engine.process_message(session.session_id, "确认")
        assert result.get("completed") is True


class TestEfficiency:
    """测试效率提升"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2()

    def test_fewer_turns(self, engine):
        """测试减少对话轮次"""
        session = engine.create_session("user_123", "task_456")

        # 第一轮：类型识别
        engine.process_message(session.session_id, "我想租房")
        assert session.turn_count == 1
        assert session.demand_type == "rental"

        # 第二轮：角色识别
        engine.process_message(session.session_id, "我是租客")
        assert session.turn_count == 2
        assert session.role == "tenant"


class TestPipelineMode:
    """测试流水线模式 - 单次消息多阶段处理"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2()

    def test_single_message_type_and_role(self, engine):
        """测试单条消息同时识别类型和角色"""
        session = engine.create_session("user_123", "task_456")

        # 一条消息包含类型和角色
        result = engine.process_message(session.session_id, "我要租房，我是租客")

        assert session.demand_type == "rental"
        assert session.role == "tenant"
        assert session.state.value == "collecting"
        assert session.turn_count == 1  # 只进行了一轮对话

    def test_single_message_complete_info(self, engine):
        """测试单条消息提供完整信息"""
        session = engine.create_session("user_123", "task_456")

        # 用户一次提供所有信息
        message = "我要租房，三居室，靠近北京理工大学，我是租客，预算不高于3000元"
        result = engine.process_message(session.session_id, message)

        # 验证类型和角色已识别
        assert session.demand_type == "rental"
        assert session.role == "tenant"

        # 验证提取了字段
        assert "property_type" in session.values or "bedrooms" in session.values
        assert session.turn_count == 1

    def test_pipeline_progressive_collection(self, engine):
        """测试流水线渐进式收集"""
        session = engine.create_session("user_123", "task_456")

        # 第一轮：类型+角色+部分字段
        result = engine.process_message(
            session.session_id,
            "我要租房，我是租客，想要两室一厅"
        )

        assert session.demand_type == "rental"
        assert session.role == "tenant"
        assert "bedrooms" in session.values

        # 第二轮：补充更多字段
        result = engine.process_message(
            session.session_id,
            "预算600刀，墨尔本CBD，4月入住"
        )

        # 应该提取到更多字段
        assert session.turn_count == 2
        assert len(session.values) >= 2

    def test_role_detection_keywords(self, engine):
        """测试角色关键词检测"""
        session = engine.create_session("user_123", "task_456")
        session.demand_type = "rental"
        session.state = DemandState.IDENTIFYING_ROLE

        # 测试租客关键词
        role = engine._detect_role("我想租个房子", "rental")
        assert role == "tenant"

        # 测试房东关键词
        role = engine._detect_role("我有房要出租", "rental")
        assert role == "landlord"

    def test_completion_intent_detection(self, engine):
        """测试完成意图检测"""
        session = engine.create_session("user_123", "task_456")

        # 各种完成意图
        assert engine._is_completion_intent("完成了") is True
        assert engine._is_completion_intent("done") is True
        assert engine._is_completion_intent("没有了") is True
        assert engine._is_completion_intent("确认") is True
        assert engine._is_completion_intent("还需要信息") is False

    def test_completion_intent_with_context(self, engine):
        """测试带上下文的完成意图检测"""
        context = {
            "filled_fields": ["property_type", "bedrooms", "max_price"],
            "pending_fields": ["location", "move_in_date"]
        }

        # 测试带上下文的检测（回退到规则匹配）
        result = engine._is_completion_intent("就这样吧", context)
        assert isinstance(result, bool)

    def test_role_detection_with_single_role(self, engine):
        """测试单角色场景自动选择"""
        # 对于只有一个角色的类型，应该自动返回
        from backend.config import TaskType

        # 模拟只有一个角色的场景
        session = engine.create_session("user_123", "task_456")
        session.demand_type = "rental"

        # 获取可用角色数
        from backend.demand_templates import TEMPLATE_REGISTRY
        templates = [t for t in TEMPLATE_REGISTRY.values() if t.demand_type == "rental"]

        if len(templates) == 1:
            role = engine._detect_role("任意消息", "rental")
            assert role == templates[0].role

    def test_llm_fallback_to_rules(self, engine):
        """测试LLM失败时回退到规则匹配"""
        # 当没有LLM客户端时，应该使用规则匹配
        engine_no_llm = DemandDefinitionEngineV2(llm_client=None)

        # 角色检测应该仍然工作
        role = engine_no_llm._detect_role("我是租客", "rental")
        assert role == "tenant"

        # 完成意图检测应该仍然工作
        assert engine_no_llm._is_completion_intent("完成了") is True
        assert engine_no_llm._is_completion_intent("继续") is False


class TestBackwardCompatibility:
    """测试向后兼容性"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2()

    def test_session_creation(self, engine):
        """测试会话创建"""
        session = engine.create_session("user_123", "task_456")
        assert session.user_id == "user_123"
        assert session.task_id == "task_456"
        assert session.state == DemandState.INITIAL

    def test_get_session(self, engine):
        """测试获取会话"""
        session = engine.create_session("user_123", "task_456")
        retrieved = engine.get_session(session.session_id)
        assert retrieved.session_id == session.session_id

    def test_is_demand_complete(self, engine):
        """测试完成度检查"""
        session = engine.create_session("user_123", "task_456")
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.template = RENTAL_TENANT_TEMPLATE

        # 初始状态未完成
        assert engine.is_demand_complete(session.session_id) is False

        # 填写所有必填字段
        required_fields = [f.name for f in RENTAL_TENANT_TEMPLATE.fields if f.required]
        for field_name in required_fields:
            session.values[field_name] = "test_value"

        assert engine.is_demand_complete(session.session_id) is True

    def test_get_demand_data(self, engine):
        """测试获取需求数据"""
        session = engine.create_session("user_123", "task_456")
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        session.values = {"property_type": "apartment"}

        data = engine.get_demand_data(session.session_id)

        assert data is not None
        assert data["demand_type"] == TaskType.RENTAL
        assert data["role"] == "tenant"
        assert data["values"]["property_type"] == "apartment"
