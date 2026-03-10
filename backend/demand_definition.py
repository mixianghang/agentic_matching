"""
需求定义模块 - 实现多轮对话式的需求收集
"""
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from backend.demand_templates import (
    DemandTemplate, TemplateField, FieldType,
    get_template, get_template_for_role, list_all_templates
)
from backend.config import TaskType, TASK_TYPE_NAMES


class DemandState(Enum):
    """需求定义状态"""
    INITIAL = "initial"                    # 初始状态
    IDENTIFYING_TYPE = "identifying_type"  # 识别需求类型
    IDENTIFYING_ROLE = "identifying_role"  # 识别用户角色
    FILLING_REQUIRED = "filling_required"  # 填充必填字段
    FILLING_OPTIONAL = "filling_optional"  # 填充选填字段
    CUSTOM_REQUIREMENTS = "custom_requirements"  # 收集自定义需求
    CONFIRMING = "confirming"              # 确认需求
    COMPLETED = "completed"                # 已完成
    MODIFYING = "modifying"                # 修改中


@dataclass
class DemandDefinitionSession:
    """需求定义会话"""
    session_id: str
    user_id: str
    task_id: Optional[str] = None
    state: DemandState = DemandState.INITIAL
    demand_type: Optional[str] = None
    role: Optional[str] = None
    template: Optional[DemandTemplate] = None
    values: Dict[str, Any] = field(default_factory=dict)
    custom_requirements: List[str] = field(default_factory=list)
    filled_fields: List[str] = field(default_factory=list)
    pending_fields: List[TemplateField] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "state": self.state.value,
            "demand_type": self.demand_type,
            "role": self.role,
            "template_id": self.template.template_id if self.template else None,
            "values": self.values,
            "custom_requirements": self.custom_requirements,
            "filled_fields": self.filled_fields,
            "pending_fields": [f.name for f in self.pending_fields],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DemandDefinitionEngine:
    """需求定义引擎"""

    # 需求类型识别提示词
    TYPE_IDENTIFICATION_PROMPT = """你是需求类型识别专家。根据用户的输入，判断用户想要创建什么类型的需求。

可选类型：
- RENTAL: 租房相关（找房子、出租房子、合租等）
- DATING: 婚恋交友（找对象、相亲、交友等）
- GAMING: 游戏组队（找游戏队友、开黑等）

请只回复一个单词：RENTAL、DATING 或 GAMING。不要包含任何解释。"""

    # 角色识别提示词
    ROLE_IDENTIFICATION_PROMPT = """你是角色识别专家。用户想要进行{demand_type}相关的需求。

请判断用户在这次需求中扮演什么角色：
{role_options}

请只回复角色代码（如 tenant、landlord 等），不要包含任何解释。"""

    # 字段提取提示词
    FIELD_EXTRACTION_PROMPT = """你是信息提取专家。从用户的回答中提取指定字段的值。

字段名称: {field_name}
字段类型: {field_type}
字段说明: {field_description}

用户回答: {user_message}

请提取字段值并以JSON格式返回：
{{
    "value": 提取的值,
    "confidence": "high/medium/low",
    "needs_clarification": true/false,
    "clarification_question": "如果需要澄清，提供追问问题"
}}

注意：
1. 如果用户回答明确包含所需信息，直接提取
2. 如果信息不完整或模糊，设置 needs_clarification 为 true
3. 对于枚举类型，返回选项中的值
4. 对于范围类型，返回 {{"min": x, "max": y}} 格式"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.sessions: Dict[str, DemandDefinitionSession] = {}

    def create_session(self, user_id: str, task_id: Optional[str] = None) -> DemandDefinitionSession:
        """创建新的需求定义会话"""
        session = DemandDefinitionSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            task_id=task_id,
            state=DemandState.INITIAL
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[DemandDefinitionSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def process_message(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """处理用户消息，返回助手回复"""
        session = self.get_session(session_id)
        if not session:
            return {
                "success": False,
                "error": "Session not found",
                "message": "会话不存在，请重新开始"
            }

        # 记录用户消息
        session.conversation_history.append({
            "role": "user",
            "message": user_message,
            "timestamp": datetime.now().isoformat()
        })

        # 根据当前状态处理
        if session.state == DemandState.INITIAL:
            return self._handle_initial_state(session, user_message)
        elif session.state == DemandState.IDENTIFYING_TYPE:
            return self._handle_type_identification(session, user_message)
        elif session.state == DemandState.IDENTIFYING_ROLE:
            return self._handle_role_identification(session, user_message)
        elif session.state == DemandState.FILLING_REQUIRED:
            return self._handle_filling_required(session, user_message)
        elif session.state == DemandState.FILLING_OPTIONAL:
            return self._handle_filling_optional(session, user_message)
        elif session.state == DemandState.CUSTOM_REQUIREMENTS:
            return self._handle_custom_requirements(session, user_message)
        elif session.state == DemandState.CONFIRMING:
            return self._handle_confirming(session, user_message)
        elif session.state == DemandState.MODIFYING:
            return self._handle_modifying(session, user_message)
        else:
            return {
                "success": False,
                "error": "Unknown state",
                "message": "未知状态"
            }

    def _handle_initial_state(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理初始状态"""
        # 尝试识别需求类型
        demand_type = self._detect_demand_type(user_message)

        if demand_type:
            session.demand_type = demand_type
            session.state = DemandState.IDENTIFYING_ROLE
            return self._ask_for_role(session)
        else:
            session.state = DemandState.IDENTIFYING_TYPE
            return {
                "success": True,
                "state": session.state.value,
                "message": "您好！我来帮您创建需求。请问您想要：\n\n1. 🏠 租房/出租房子\n2. 💕 寻找交友/相亲对象\n3. 🎮 找游戏队友\n\n请告诉我您的需求类型。"
            }

    def _handle_type_identification(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理类型识别状态"""
        demand_type = self._detect_demand_type(user_message)

        if demand_type:
            session.demand_type = demand_type
            session.state = DemandState.IDENTIFYING_ROLE
            return self._ask_for_role(session)
        else:
            return {
                "success": True,
                "state": session.state.value,
                "message": "抱歉，我没有理解您的需求类型。请从以下选项中选择：\n\n1. 🏠 租房/出租房子\n2. 💕 寻找交友/相亲对象\n3. 🎮 找游戏队友"
            }

    def _ask_for_role(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """询问用户角色"""
        if session.demand_type == TaskType.RENTAL:
            return {
                "success": True,
                "state": session.state.value,
                "message": f"好的，您需要{TASK_TYPE_NAMES.get(session.demand_type, '相关')}服务。\n\n请问您是：\n1. 🏃 租客（找房子）\n2. 🏠 房东（出租房子）\n\n请告诉我您的角色。"
            }
        elif session.demand_type == TaskType.DATING:
            # 相亲只有寻求方
            session.role = "seeker"
            return self._load_template_and_start_filling(session)
        elif session.demand_type == TaskType.GAMING:
            return {
                "success": True,
                "state": session.state.value,
                "message": f"好的，您需要{TASK_TYPE_NAMES.get(session.demand_type, '相关')}服务。\n\n请问您是：\n1. 🎮 寻找队友\n2. 👥 招募队友\n\n请告诉我您的角色。"
            }
        else:
            return {
                "success": False,
                "error": "Unknown demand type",
                "message": "未知的需求类型"
            }

    def _handle_role_identification(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理角色识别"""
        role = self._detect_role(user_message, session.demand_type)

        if role:
            session.role = role
            return self._load_template_and_start_filling(session)
        else:
            return self._ask_for_role(session)

    def _load_template_and_start_filling(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """加载模板并开始填充"""
        template = get_template_for_role(session.demand_type, session.role)

        if not template:
            return {
                "success": False,
                "error": "Template not found",
                "message": "抱歉，暂时不支持该类型的需求"
            }

        session.template = template
        session.state = DemandState.FILLING_REQUIRED

        # 获取必填字段
        required_fields = [f for f in template.fields if f.required]
        session.pending_fields = required_fields

        # 询问第一个必填字段
        if required_fields:
            first_field = required_fields[0]
            return {
                "success": True,
                "state": session.state.value,
                "message": f"好的！我来帮您创建{TASK_TYPE_NAMES.get(session.demand_type, '')}需求。\n\n{first_field.prompt}",
                "current_field": first_field.name,
                "field_type": first_field.field_type.value,
                "options": first_field.options if first_field.options else None
            }
        else:
            return self._move_to_optional_filling(session)

    def _handle_filling_required(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理必填字段填充"""
        if not session.pending_fields:
            return self._move_to_optional_filling(session)

        current_field = session.pending_fields[0]

        # 尝试提取字段值
        value, success = self._extract_field_value(user_message, current_field)

        if success:
            # 保存字段值
            session.values[current_field.name] = value
            session.filled_fields.append(current_field.name)
            session.pending_fields.pop(0)

            # 检查是否还有未填的必填字段
            if session.pending_fields:
                next_field = session.pending_fields[0]
                return {
                    "success": True,
                    "state": session.state.value,
                    "message": f"已记录！{next_field.prompt}",
                    "current_field": next_field.name,
                    "field_type": next_field.field_type.value,
                    "options": next_field.options if next_field.options else None
                }
            else:
                return self._move_to_optional_filling(session)
        else:
            # 提取失败，重新询问
            return {
                "success": True,
                "state": session.state.value,
                "message": f"抱歉，我没有理解您的回答。{current_field.prompt}",
                "current_field": current_field.name,
                "field_type": current_field.field_type.value,
                "options": current_field.options if current_field.options else None
            }

    def _move_to_optional_filling(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """移动到选填字段填充"""
        optional_fields = [f for f in session.template.fields if not f.required]

        if optional_fields:
            session.state = DemandState.FILLING_OPTIONAL
            session.pending_fields = optional_fields

            return {
                "success": True,
                "state": session.state.value,
                "message": f"必填信息已收集完成！\n\n您还可以补充一些选填信息（直接回复\"跳过\"进入下一步）：\n\n{session.pending_fields[0].prompt}",
                "current_field": session.pending_fields[0].name,
                "field_type": session.pending_fields[0].field_type.value,
                "options": session.pending_fields[0].options if session.pending_fields[0].options else None,
                "can_skip": True
            }
        else:
            return self._move_to_custom_requirements(session)

    def _handle_filling_optional(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理选填字段填充"""
        # 检查是否跳过
        if "跳过" in user_message or "skip" in user_message.lower():
            return self._move_to_custom_requirements(session)

        if not session.pending_fields:
            return self._move_to_custom_requirements(session)

        current_field = session.pending_fields[0]
        value, success = self._extract_field_value(user_message, current_field)

        if success:
            session.values[current_field.name] = value
            session.filled_fields.append(current_field.name)

        session.pending_fields.pop(0)

        if session.pending_fields:
            next_field = session.pending_fields[0]
            return {
                "success": True,
                "state": session.state.value,
                "message": f"{next_field.prompt}（回复\"跳过\"可跳过此项）",
                "current_field": next_field.name,
                "field_type": next_field.field_type.value,
                "options": next_field.options if next_field.options else None,
                "can_skip": True
            }
        else:
            return self._move_to_custom_requirements(session)

    def _move_to_custom_requirements(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """移动到自定义需求收集"""
        if session.template.custom_allowed:
            session.state = DemandState.CUSTOM_REQUIREMENTS
            return {
                "success": True,
                "state": session.state.value,
                "message": f"{session.template.custom_prompt}\n\n（如果没有其他要求，请回复\"没有了\"或\"完成\"）",
                "can_finish": True
            }
        else:
            return self._move_to_confirming(session)

    def _handle_custom_requirements(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理自定义需求"""
        # 检查是否完成
        if any(keyword in user_message for keyword in ["没有了", "完成", "done", "no more"]):
            return self._move_to_confirming(session)

        # 保存自定义需求
        session.custom_requirements.append(user_message)

        return {
            "success": True,
            "state": session.state.value,
            "message": "已记录！还有其他要求吗？（回复\"没有了\"完成）",
            "can_finish": True
        }

    def _move_to_confirming(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """移动到确认状态"""
        session.state = DemandState.CONFIRMING

        # 生成需求摘要
        summary = self._generate_demand_summary(session)

        return {
            "success": True,
            "state": session.state.value,
            "message": f"请确认您的需求：\n\n{summary}\n\n信息准确吗？（回复\"确认\"完成，或告诉我需要修改的地方）",
            "demand_summary": session.values,
            "custom_requirements": session.custom_requirements
        }

    def _handle_confirming(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理确认"""
        if any(keyword in user_message for keyword in ["确认", "是的", "正确", "ok", "yes"]):
            session.state = DemandState.COMPLETED
            return {
                "success": True,
                "state": session.state.value,
                "completed": True,
                "message": "需求创建完成！正在为您寻找匹配...",
                "demand_data": {
                    "type": session.demand_type,
                    "role": session.role,
                    "values": session.values,
                    "custom_requirements": session.custom_requirements
                }
            }
        else:
            # 用户要修改，进入修改状态
            session.state = DemandState.MODIFYING
            return {
                "success": True,
                "state": session.state.value,
                "message": "好的，请告诉我需要修改哪里？",
                "current_values": session.values
            }

    def _handle_modifying(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理修改"""
        # 尝试识别要修改的字段
        modified = self._apply_modification(session, user_message)

        if modified:
            return self._move_to_confirming(session)
        else:
            return {
                "success": True,
                "state": session.state.value,
                "message": "抱歉，我没有理解您要修改的内容。请告诉我具体要修改哪个字段，比如\"修改预算为800\"",
                "current_values": session.values
            }

    def _detect_demand_type(self, message: str) -> Optional[str]:
        """检测需求类型"""
        message_lower = message.lower()

        # 关键词匹配
        rental_keywords = ["租", "房", "住", "室友", "公寓", "housing", "rent", "出租"]
        dating_keywords = ["相亲", "交友", "对象", "恋爱", "认识", "dating", "relationship", "friendship", "女朋", "男朋", "女票", "男票", "老婆", "老公"]
        gaming_keywords = ["游戏", "王者", "lol", "吃鸡", "game", "gaming", "队友", "开黑", "play"]

        if any(kw in message_lower for kw in rental_keywords):
            return TaskType.RENTAL
        elif any(kw in message_lower for kw in dating_keywords):
            return TaskType.DATING
        elif any(kw in message_lower for kw in gaming_keywords):
            return TaskType.GAMING

        # 使用LLM识别
        if self.llm_client:
            try:
                response = self.llm_client.generate_response(
                    self.TYPE_IDENTIFICATION_PROMPT,
                    message
                )
                response = response.strip().upper()
                if response == "RENTAL":
                    return TaskType.RENTAL
                elif response == "DATING":
                    return TaskType.DATING
                elif response == "GAMING":
                    return TaskType.GAMING
            except Exception:
                pass

        return None

    def _detect_role(self, message: str, demand_type: str) -> Optional[str]:
        """检测用户角色"""
        message_lower = message.lower()

        if demand_type == TaskType.RENTAL:
            tenant_keywords = ["租客", "租房", "找房", "tenant", "rent", "找房子"]
            landlord_keywords = ["房东", "出租", "landlord", "有房", "房子出租"]

            if any(kw in message_lower for kw in tenant_keywords):
                return "tenant"
            elif any(kw in message_lower for kw in landlord_keywords):
                return "landlord"

        elif demand_type == TaskType.DATING:
            return "seeker"

        elif demand_type == TaskType.GAMING:
            seeker_keywords = ["找队友", "寻找", "seeking", "找", "缺"]
            provider_keywords = ["招募", "组队", "找玩家", "recruiting"]

            if any(kw in message_lower for kw in seeker_keywords):
                return "seeker"
            elif any(kw in message_lower for kw in provider_keywords):
                return "provider"

        # 使用LLM识别
        if self.llm_client:
            try:
                role_options = self._get_role_options(demand_type)
                prompt = self.ROLE_IDENTIFICATION_PROMPT.format(
                    demand_type=demand_type,
                    role_options=role_options
                )
                response = self.llm_client.generate_response(prompt, message)
                return response.strip().lower()
            except Exception:
                pass

        return None

    def _get_role_options(self, demand_type: str) -> str:
        """获取角色选项描述"""
        if demand_type == TaskType.RENTAL:
            return "- tenant: 租客（找房子）\n- landlord: 房东（出租房子）"
        elif demand_type == TaskType.DATING:
            return "- seeker: 寻找对象"
        elif demand_type == TaskType.GAMING:
            return "- seeker: 寻找队友\n- provider: 招募队友"
        return ""

    def _extract_field_value(self, message: str, field: TemplateField) -> Tuple[Any, bool]:
        """从用户消息中提取字段值"""
        # 使用LLM提取
        if self.llm_client:
            try:
                prompt = self.FIELD_EXTRACTION_PROMPT.format(
                    field_name=field.name,
                    field_type=field.field_type.value,
                    field_description=field.display_name,
                    user_message=message
                )
                response = self.llm_client.generate_response(
                    "You are a helpful assistant that extracts structured data from user messages.",
                    prompt
                )

                # 尝试解析JSON
                try:
                    result = json.loads(response)
                    if result.get("needs_clarification"):
                        return None, False
                    return result.get("value"), True
                except json.JSONDecodeError:
                    pass
            except Exception:
                pass

        # 回退到简单提取
        return self._simple_extract(message, field)

    def _simple_extract(self, message: str, field: TemplateField) -> Tuple[Any, bool]:
        """简单字段提取"""
        message = message.strip().lower()

        if field.field_type == FieldType.ENUM and field.options:
            # 尝试匹配选项
            for option in field.options:
                option_lower = option.lower()
                # 直接匹配选项值
                if option_lower in message:
                    return option, True
                # 匹配中文关键词
                if option_lower == "apartment" and any(kw in message for kw in ["公寓", "apartment"]):
                    return option, True
                if option_lower == "house" and any(kw in message for kw in ["house", "别墅", "独栋"]):
                    return option, True
                if option_lower == "studio" and any(kw in message for kw in ["studio", "单间", "开间"]):
                    return option, True
                if option_lower == "room" and any(kw in message for kw in ["room", "房间", "卧室"]):
                    return option, True
                if option_lower == "any" and any(kw in message for kw in ["any", "任意", "都可以", "无所谓"]):
                    return option, True
            # 如果只有一个选项匹配或模糊匹配，返回第一个选项
            if len(field.options) > 0:
                return field.options[0], True
            return None, False

        elif field.field_type == FieldType.INTEGER:
            # 提取数字
            import re
            numbers = re.findall(r'\d+', message)
            if numbers:
                return int(numbers[0]), True
            return None, False

        elif field.field_type == FieldType.BOOLEAN:
            # 检测是/否
            yes_keywords = ["是", "有", "要", "需要", "yes", "y", "true", "想", "希望"]
            no_keywords = ["否", "没有", "不要", "不需要", "no", "n", "false", "不想"]

            message_lower = message.lower()
            # 优先检测否定词
            if any(kw in message_lower for kw in no_keywords):
                return False, True
            elif any(kw in message_lower for kw in yes_keywords):
                return True, True
            # 默认返回True（假设用户回答表示肯定）
            return True, True

        elif field.field_type == FieldType.RANGE:
            # 提取范围
            import re
            numbers = re.findall(r'\d+', message)
            if len(numbers) >= 2:
                return {"min": int(numbers[0]), "max": int(numbers[1])}, True
            elif len(numbers) == 1:
                return {"min": int(numbers[0]), "max": int(numbers[0]) + 10}, True
            return None, False

        else:
            # 其他类型直接返回文本
            return message, True

    def _generate_demand_summary(self, session: DemandDefinitionSession) -> str:
        """生成需求摘要"""
        if not session.template:
            return "暂无需求信息"

        lines = [f"【{session.template.name}】", ""]

        # 必填字段
        for field in session.template.fields:
            if field.required and field.name in session.values:
                value = session.values[field.name]
                lines.append(f"• {field.display_name}: {value}")

        # 选填字段
        optional_filled = []
        for field in session.template.fields:
            if not field.required and field.name in session.values:
                optional_filled.append(f"{field.display_name}: {session.values[field.name]}")

        if optional_filled:
            lines.append("")
            lines.append("【选填信息】")
            for item in optional_filled:
                lines.append(f"• {item}")

        # 自定义需求
        if session.custom_requirements:
            lines.append("")
            lines.append("【特殊要求】")
            for req in session.custom_requirements:
                lines.append(f"• {req}")

        return "\n".join(lines)

    def _apply_modification(self, session: DemandDefinitionSession, message: str) -> bool:
        """应用修改"""
        # 简单实现：检测 "修改xxx为yyy" 或 "xxx改为yyy"
        import re

        # 尝试匹配修改模式
        patterns = [
            r"修改\s*(\w+)\s*为\s*(.+)",
            r"(\w+)\s*改为\s*(.+)",
            r"把\s*(\w+)\s*改成\s*(.+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                field_name = match.group(1)
                new_value = match.group(2).strip()

                # 查找匹配的字段
                for field in session.template.fields:
                    if field.name == field_name or field.display_name in field_name:
                        session.values[field.name] = new_value
                        return True

        return False

    def is_demand_complete(self, session_id: str) -> bool:
        """检查需求是否完成"""
        session = self.get_session(session_id)
        if not session or not session.template:
            return False

        # 检查所有必填字段是否已填
        required_fields = [f.name for f in session.template.fields if f.required]
        return all(field in session.values for field in required_fields)

    def get_demand_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取完整的需求数据"""
        session = self.get_session(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "task_id": session.task_id,
            "demand_type": session.demand_type,
            "role": session.role,
            "template_id": session.template.template_id if session.template else None,
            "values": session.values,
            "custom_requirements": session.custom_requirements,
            "is_complete": self.is_demand_complete(session_id),
            "state": session.state.value
        }
