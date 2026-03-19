"""
需求定义模块 V2 测试
"""
import pytest
import os
import json
import re
from backend.demand_definition_v2 import (
    DemandDefinitionEngineV2,
    DemandDefinitionSession,
    DemandState,
    PromptMode
)
from backend.config import TaskType


class MockDecisionLLM:
    """Deterministic mock LLM for intent/state decisions in tests."""

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        sp = (system_prompt or "").lower()
        up = (user_prompt or "")
        up_lower = up.lower()

        if "strict intent classifier" in sp:
            labels_match = re.search(r"候选标签：(.+)", up)
            labels = [p.strip().lower() for p in labels_match.group(1).split(",")] if labels_match else []
            msg_match = re.search(r"当前消息：(.*)", up)
            msg = (msg_match.group(1).strip() if msg_match else up).lower()

            def has_any(words):
                return any(w in msg for w in words)

            if "complete" in labels:
                if has_any(["完成", "确认", "done", "没有了", "no more", "就这样", "准确", "很好"]):
                    return json.dumps({"intent": "complete", "confidence": 0.95}, ensure_ascii=False)
                return json.dumps({"intent": "continue", "confidence": 0.9}, ensure_ascii=False)

            if "confirm" in labels:
                if has_any(["修改", "改", "change"]):
                    return json.dumps({"intent": "modify", "confidence": 0.95}, ensure_ascii=False)
                return json.dumps({"intent": "confirm", "confidence": 0.95}, ensure_ascii=False)

            if "no_change" in labels:
                if has_any(["不需要修改", "不用改", "无需修改", "no change", "准确", "很好", "就这样"]):
                    return json.dumps({"intent": "no_change", "confidence": 0.95}, ensure_ascii=False)
                return json.dumps({"intent": "modify", "confidence": 0.9}, ensure_ascii=False)

            if "skip" in labels:
                if has_any(["跳过", "skip"]):
                    return json.dumps({"intent": "skip", "confidence": 0.95}, ensure_ascii=False)
                return json.dumps({"intent": "continue", "confidence": 0.9}, ensure_ascii=False)

        # V2 dynamic type detection prompt
        if "需求类型识别专家" in system_prompt and "请按以下json格式输出" in system_prompt.lower():
            msg = up_lower
            if any(k in msg for k in ["租", "房", "apartment", "rent"]):
                d_type = "RENTAL"
            elif any(k in msg for k in ["相亲", "交友", "对象", "dating"]):
                d_type = "DATING"
            elif any(k in msg for k in ["游戏", "开黑", "队友", "gaming"]):
                d_type = "GAMING"
            else:
                d_type = "UNKNOWN"
            conf = 0.95 if d_type != "UNKNOWN" else 0.2
            return json.dumps({"demand_type": d_type, "confidence": conf, "to_user": ""}, ensure_ascii=False)

        # Role detection prompt
        if "角色识别专家" in system_prompt:
            msg = up_lower
            if any(k in msg for k in ["房东", "出租", "landlord"]):
                return "landlord"
            if any(k in msg for k in ["租客", "租房", "租个房", "找房", "tenant"]):
                return "tenant"
            if any(k in msg for k in ["招募", "provider"]):
                return "provider"
            if any(k in msg for k in ["找队友", "seeker"]):
                return "seeker"
            return "unknown"

        if "asks concise clarifying questions" in sp:
            return "我还不能确定您是租客还是房东。您是要找房，还是有房要出租？可以直接回复“租客”或“房东”。"

        # Field extraction / ACP prompt
        if "structured data" in sp or "[acp v1.0]" in up_lower:
            text = up_lower
            extracted = {}
            if "公寓" in text or "apartment" in text:
                extracted["property_type"] = "apartment"
            bed = re.search(r"(\d+)\s*(室|居|卧)", text)
            if bed:
                extracted["bedrooms"] = int(bed.group(1))
            else:
                zh_map = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5}
                zh_bed = re.search(r"([一二两三四五])\s*(室|居|卧)", text)
                if zh_bed:
                    extracted["bedrooms"] = zh_map.get(zh_bed.group(1), 1)
            price = re.search(r"预算\s*(\d+)", text)
            if price:
                extracted["max_price"] = int(price.group(1))
            if "cbd" in text:
                extracted["location"] = "CBD"
            return json.dumps(
                {
                    "to_user": "好的，请继续补充信息。",
                    "extracted": extracted,
                    "next_action": "continue",
                    "asked_fields": [],
                    "confidence": 0.9,
                },
                ensure_ascii=False,
            )

        if "strict json parser for modification requests" in sp:
            m = re.search(r"(?:修改|把)?\s*([a-zA-Z_\u4e00-\u9fff]+)\s*(?:改为|改成|为|变成)\s*(.+)", up)
            if m:
                return json.dumps({"action": "modify", "field": m.group(1).strip(), "value": m.group(2).strip()}, ensure_ascii=False)
            return json.dumps({"action": "no_change", "field": "", "value": ""}, ensure_ascii=False)

        return ""


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

    def test_normalize_landlord_alias_fields(self, engine):
        """测试房东场景下将别名字段归一到模板字段。"""
        session = engine.create_session("user_123", "task_456")
        session.demand_type = TaskType.RENTAL
        session.role = "landlord"
        from backend.demand_templates import RENTAL_LANDLORD_TEMPLATE
        session.template = RENTAL_LANDLORD_TEMPLATE
        session.state = DemandState.COLLECTING
        session.pending_fields = list(RENTAL_LANDLORD_TEMPLATE.fields)

        extracted = engine._normalize_extracted_fields(
            session,
            {
                "location": "合肥包河区",
                "parking": "required",
                "min_lease": "6",
                "price": "400",
            },
            "合肥包河区，租金每月400，有停车位，最短6个月",
        )

        assert extracted["address"] == "合肥包河区"
        assert extracted["parking_available"] is True
        assert extracted["min_lease_term"] == "6_months"
        assert extracted["price"] == 400
        assert extracted["price_period"] == "monthly"

    def test_normalize_gaming_alias(self, engine):
        """测试游戏名别名标准化。"""
        session = engine.create_session("user_123", "task_456")
        session.demand_type = TaskType.GAMING
        session.role = "player"
        from backend.demand_templates import GAMING_PLAYER_TEMPLATE
        session.template = GAMING_PLAYER_TEMPLATE
        session.state = DemandState.COLLECTING
        session.pending_fields = list(GAMING_PLAYER_TEMPLATE.fields)

        extracted = engine._normalize_extracted_fields(
            session,
            {"game_name": "LOL"},
            "我想找lol队友",
        )
        assert extracted["game_name"] == "league of legends"


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

    def test_merged_history_messages_config(self):
        """测试merged模式历史消息条数可配置。"""
        engine = DemandDefinitionEngineV2(prompt_mode="merged", merged_history_messages=5)
        assert engine.merged_history_messages == 5

    def test_merged_history_messages_env(self):
        """测试历史消息条数可从环境变量读取。"""
        os.environ["DEMAND_MERGED_HISTORY_MESSAGES"] = "7"
        engine = DemandDefinitionEngineV2(prompt_mode="merged")
        assert engine.merged_history_messages == 7
        del os.environ["DEMAND_MERGED_HISTORY_MESSAGES"]


class TestNaturalConversation:
    """测试自然对话流程"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2(llm_client=MockDecisionLLM())

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

    def test_confirm_with_natural_phrase(self, engine):
        """测试确认阶段对自然表达的识别（如：准确，很好，去找吧）。"""
        session = engine.create_session("user_123", "task_456")

        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        session.template = RENTAL_TENANT_TEMPLATE
        session.values = {
            "property_type": "apartment",
            "bedrooms": 3,
            "max_price": 400,
            "location": "合肥包河区",
            "move_in_date": "2026-06",
            "furnished": "furnished",
            "parking": "yes",
            "lease_term": "6_months_plus",
        }
        session.filled_fields = list(session.values.keys())
        session.pending_fields = []
        session.state = DemandState.CONFIRMING

        result = engine.process_message(session.session_id, "准确，很好，去找吧。")
        assert result.get("completed") is True
        assert result["state"] == DemandState.COMPLETED.value

    def test_modifying_state_no_change_should_complete(self, engine):
        """测试进入修改态后，用户表示无需修改时应直接完成。"""
        session = engine.create_session("user_123", "task_456")

        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        session.template = RENTAL_TENANT_TEMPLATE
        session.values = {
            "property_type": "apartment",
            "bedrooms": 3,
            "max_price": 400,
            "location": "合肥包河区",
            "move_in_date": "2026-06",
        }
        session.filled_fields = list(session.values.keys())
        session.pending_fields = []
        session.state = DemandState.MODIFYING

        result = engine.process_message(session.session_id, "不需要修改，很好，准确。")
        assert result.get("completed") is True
        assert result["state"] == DemandState.COMPLETED.value

    def test_role_retry_response_uses_llm(self, engine):
        """测试角色无法识别时使用LLM生成更自然的追问。"""
        session = engine.create_session("user_123", "task_456")
        session.demand_type = TaskType.RENTAL
        session.state = DemandState.IDENTIFYING_ROLE

        result = engine.process_message(session.session_id, "随便")

        assert result["state"] == DemandState.IDENTIFYING_ROLE.value
        assert "租客" in result["message"]
        assert "房东" in result["message"]


class TestEfficiency:
    """测试效率提升"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2(llm_client=MockDecisionLLM())

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
        return DemandDefinitionEngineV2(llm_client=MockDecisionLLM())

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

    def test_role_detection_with_llm(self, engine):
        """测试通过LLM识别角色"""
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
        """测试通过LLM检测完成意图"""
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

        # 测试带上下文的检测
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

    def test_no_llm_returns_conservative_decision(self, engine):
        """测试无LLM时返回保守结果（不误判完成/角色）。"""
        engine_no_llm = DemandDefinitionEngineV2(llm_client=None)

        # 角色检测在无LLM时不应误判
        role = engine_no_llm._detect_role("我是租客", "rental")
        assert role is None

        # 完成意图在无LLM时保持保守
        assert engine_no_llm._is_completion_intent("完成了") is False
        assert engine_no_llm._is_completion_intent("继续") is False


class TestBackwardCompatibility:
    """测试向后兼容性"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngineV2(llm_client=MockDecisionLLM())

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
