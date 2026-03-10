"""
需求定义模块测试
"""
import pytest
from backend.demand_definition import (
    DemandDefinitionEngine,
    DemandDefinitionSession,
    DemandState
)
from backend.demand_templates import (
    get_template,
    get_template_for_role,
    list_all_templates,
    FieldType
)
from backend.config import TaskType


class TestDemandTemplates:
    """测试需求模板"""

    def test_list_all_templates(self):
        """测试列出所有模板"""
        templates = list_all_templates()
        assert len(templates) > 0
        assert "rental_tenant" in templates
        assert "rental_landlord" in templates
        assert "dating_basic" in templates

    def test_get_template(self):
        """测试获取模板"""
        template = get_template("rental_tenant")
        assert template is not None
        assert template.template_id == "rental_tenant"
        assert template.demand_type == "rental"
        assert template.role == "tenant"

    def test_get_template_for_role(self):
        """测试根据类型和角色获取模板"""
        template = get_template_for_role("rental", "tenant")
        assert template is not None
        assert template.template_id == "rental_tenant"

        template = get_template_for_role("rental", "landlord")
        assert template is not None
        assert template.template_id == "rental_landlord"

    def test_template_fields(self):
        """测试模板字段"""
        template = get_template("rental_tenant")

        # 检查必填字段
        required_fields = [f for f in template.fields if f.required]
        required_names = [f.name for f in required_fields]
        assert "property_type" in required_names
        assert "bedrooms" in required_names
        assert "max_price" in required_names
        assert "location" in required_names
        assert "move_in_date" in required_names

        # 检查选填字段
        optional_fields = [f for f in template.fields if not f.required]
        optional_names = [f.name for f in optional_fields]
        assert "furnished" in optional_names
        assert "parking" in optional_names


class TestDemandDefinitionEngine:
    """测试需求定义引擎"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        return DemandDefinitionEngine(llm_client=None)

    @pytest.fixture
    def session(self, engine):
        """创建会话"""
        return engine.create_session("test_user", "test_task")

    def test_create_session(self, engine):
        """测试创建会话"""
        session = engine.create_session("user_123", "task_456")
        assert session is not None
        assert session.user_id == "user_123"
        assert session.task_id == "task_456"
        assert session.state == DemandState.INITIAL
        assert session.session_id is not None

    def test_get_session(self, engine, session):
        """测试获取会话"""
        retrieved = engine.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_detect_demand_type_rental(self, engine):
        """测试检测租房需求类型"""
        result = engine._detect_demand_type("我想在墨尔本租个房子")
        assert result == TaskType.RENTAL

        result = engine._detect_demand_type("找室友合租")
        assert result == TaskType.RENTAL

    def test_detect_demand_type_dating(self, engine):
        """测试检测相亲需求类型"""
        result = engine._detect_demand_type("我想找个对象")
        assert result == TaskType.DATING

        result = engine._detect_demand_type("相亲交友")
        assert result == TaskType.DATING

    def test_detect_demand_type_gaming(self, engine):
        """测试检测游戏需求类型"""
        result = engine._detect_demand_type("找游戏队友")
        assert result == TaskType.GAMING

        result = engine._detect_demand_type("王者开黑")
        assert result == TaskType.GAMING

    def test_detect_role_rental(self, engine):
        """测试检测租房角色"""
        result = engine._detect_role("我是租客，想找个房子", TaskType.RENTAL)
        assert result == "tenant"

        result = engine._detect_role("我有房子出租", TaskType.RENTAL)
        assert result == "landlord"

    def test_process_message_initial_to_type(self, engine, session):
        """测试从初始状态到类型识别"""
        result = engine.process_message(session.session_id, "我想租房子")

        assert result["success"] is True
        assert session.state == DemandState.IDENTIFYING_ROLE
        assert session.demand_type == TaskType.RENTAL

    def test_process_message_type_to_role(self, engine, session):
        """测试从类型识别到角色识别"""
        # 先设置类型
        session.state = DemandState.IDENTIFYING_ROLE
        session.demand_type = TaskType.RENTAL

        result = engine.process_message(session.session_id, "我是租客")

        assert result["success"] is True
        assert session.role == "tenant"
        assert session.template is not None

    def test_process_message_filling_required(self, engine, session):
        """测试必填字段填充"""
        # 设置到必填字段填充状态
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.state = DemandState.FILLING_REQUIRED
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        session.template = RENTAL_TENANT_TEMPLATE
        session.pending_fields = [f for f in RENTAL_TENANT_TEMPLATE.fields if f.required]

        # 回答第一个字段
        result = engine.process_message(session.session_id, "公寓")

        assert result["success"] is True
        assert "property_type" in session.values
        assert len(session.pending_fields) == 4  # 还剩4个必填字段

    def test_simple_extract_enum(self, engine):
        """测试简单提取枚举值"""
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        field = next(f for f in RENTAL_TENANT_TEMPLATE.fields if f.name == "property_type")

        value, success = engine._simple_extract("我想租公寓", field)
        assert success is True
        assert value == "apartment"

    def test_simple_extract_integer(self, engine):
        """测试简单提取整数"""
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        field = next(f for f in RENTAL_TENANT_TEMPLATE.fields if f.name == "bedrooms")

        value, success = engine._simple_extract("需要2间卧室", field)
        assert success is True
        assert value == 2

    def test_simple_extract_boolean(self, engine):
        """测试简单提取布尔值"""
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        field = next(f for f in RENTAL_TENANT_TEMPLATE.fields if f.name == "parking")

        value, success = engine._simple_extract("需要停车位", field)
        assert success is True
        assert value is True

        value, success = engine._simple_extract("不需要", field)
        assert success is True
        assert value is False

    def test_simple_extract_range(self, engine):
        """测试简单提取范围"""
        from backend.demand_templates import DATING_TEMPLATE
        field = next(f for f in DATING_TEMPLATE.fields if f.name == "age_range")

        value, success = engine._simple_extract("25到35岁之间", field)
        assert success is True
        assert value["min"] == 25
        assert value["max"] == 35

    def test_is_demand_complete(self, engine, session):
        """测试需求完成度检查"""
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.template = RENTAL_TENANT_TEMPLATE

        # 初始状态未完成
        assert engine.is_demand_complete(session.session_id) is False

        # 填充所有必填字段
        required_fields = [f.name for f in RENTAL_TENANT_TEMPLATE.fields if f.required]
        for field_name in required_fields:
            session.values[field_name] = "test_value"

        assert engine.is_demand_complete(session.session_id) is True

    def test_get_demand_data(self, engine, session):
        """测试获取需求数据"""
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        session.template = RENTAL_TENANT_TEMPLATE
        session.values = {"property_type": "apartment", "bedrooms": 2}
        session.custom_requirements = ["必须有阳台"]

        data = engine.get_demand_data(session.session_id)

        assert data is not None
        assert data["demand_type"] == TaskType.RENTAL
        assert data["role"] == "tenant"
        assert data["values"]["property_type"] == "apartment"
        assert len(data["custom_requirements"]) == 1

    def test_generate_demand_summary(self, engine, session):
        """测试生成需求摘要"""
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.template = RENTAL_TENANT_TEMPLATE
        session.demand_type = TaskType.RENTAL
        session.role = "tenant"
        session.values = {
            "property_type": "apartment",
            "bedrooms": 2,
            "max_price": 600,
            "location": "墨尔本",
            "move_in_date": "2026-04-01"
        }
        session.custom_requirements = ["必须有北阳台"]

        summary = engine._generate_demand_summary(session)

        assert "房源类型" in summary
        assert "apartment" in summary
        assert "必须有北阳台" in summary

    def test_apply_modification(self, engine, session):
        """测试应用修改"""
        from backend.demand_templates import RENTAL_TENANT_TEMPLATE
        session.template = RENTAL_TENANT_TEMPLATE
        session.values = {"max_price": 500}

        result = engine._apply_modification(session, "把max_price改成600")
        assert result is True
        assert session.values["max_price"] == "600"


class TestDemandDefinitionIntegration:
    """集成测试 - 完整的需求定义流程"""

    @pytest.fixture
    def engine(self):
        return DemandDefinitionEngine(llm_client=None)

    def test_complete_rental_tenant_flow(self, engine):
        """测试完整的租客需求定义流程"""
        session = engine.create_session("user_123", "task_456")

        # 1. 初始状态 - 表达需求
        result = engine.process_message(session.session_id, "我想在墨尔本租个房子")
        assert result["success"] is True
        assert session.state == DemandState.IDENTIFYING_ROLE

        # 2. 选择角色
        result = engine.process_message(session.session_id, "我是租客")
        assert result["success"] is True
        assert session.state == DemandState.FILLING_REQUIRED
        assert session.template is not None

        # 3. 填写必填字段
        # property_type
        result = engine.process_message(session.session_id, "公寓")
        assert "bedrooms" in result.get("current_field", "")

        # bedrooms
        result = engine.process_message(session.session_id, "2间")
        assert "max_price" in result.get("current_field", "")

        # max_price
        result = engine.process_message(session.session_id, "600")
        assert "location" in result.get("current_field", "")

        # location
        result = engine.process_message(session.session_id, "墨尔本CBD")
        assert "move_in_date" in result.get("current_field", "")

        # move_in_date
        result = engine.process_message(session.session_id, "下个月")
        assert result["state"] == DemandState.FILLING_OPTIONAL.value

        # 4. 跳过选填字段
        result = engine.process_message(session.session_id, "跳过")
        assert result["state"] == DemandState.CUSTOM_REQUIREMENTS.value

        # 5. 添加自定义需求
        result = engine.process_message(session.session_id, "必须有北阳台")
        assert "已记录" in result["message"]

        # 6. 完成自定义需求
        result = engine.process_message(session.session_id, "没有了")
        assert result["state"] == DemandState.CONFIRMING.value

        # 7. 确认需求
        result = engine.process_message(session.session_id, "确认")
        assert result["completed"] is True
        assert result["state"] == DemandState.COMPLETED.value

        # 验证最终数据
        demand_data = result["demand_data"]
        assert demand_data["type"] == TaskType.RENTAL
        assert demand_data["role"] == "tenant"
        assert demand_data["values"]["property_type"] == "apartment"
        assert demand_data["values"]["bedrooms"] == 2
        assert len(demand_data["custom_requirements"]) == 1

    def test_complete_dating_flow(self, engine):
        """测试完整的相亲需求定义流程"""
        session = engine.create_session("user_123", "task_456")

        # 1. 表达需求
        result = engine.process_message(session.session_id, "我想找个女朋友")
        assert session.demand_type == TaskType.DATING
        assert session.role == "seeker"  # 相亲直接设置角色

        # 2. 填写必填字段
        result = engine.process_message(session.session_id, "女性")
        result = engine.process_message(session.session_id, "25到30岁")
        result = engine.process_message(session.session_id, "墨尔本")
        result = engine.process_message(session.session_id, "长期交往")

        # 3. 跳过选填
        result = engine.process_message(session.session_id, "跳过")

        # 4. 无自定义需求
        result = engine.process_message(session.session_id, "没有了")

        # 5. 确认
        result = engine.process_message(session.session_id, "确认")

        assert result["completed"] is True
        assert result["demand_data"]["type"] == TaskType.DATING
