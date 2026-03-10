"""
需求定义模块 V2 - 支持ACP协议、动态提示词、多字段提取
"""
import json
import uuid
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from backend.demand_templates import (
    DemandTemplate, TemplateField, FieldType,
    get_template, get_template_for_role, list_all_templates, TEMPLATE_REGISTRY
)
from backend.config import TaskType, TASK_TYPE_NAMES, TASK_TYPE_DESCRIPTIONS

logger = logging.getLogger(__name__)


class PromptMode(Enum):
    """提示词模式"""
    SEPARATE = "separate"  # 独立提示词（默认）
    MERGED = "merged"      # 合并提示词


class DemandState(Enum):
    """需求定义状态"""
    INITIAL = "initial"                    # 初始状态
    IDENTIFYING_TYPE = "identifying_type"  # 识别需求类型
    IDENTIFYING_ROLE = "identifying_role"  # 识别用户角色
    COLLECTING = "collecting"              # 收集需求信息（合并了filling_required和filling_optional）
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
    turn_count: int = 0
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
            "turn_count": self.turn_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DemandDefinitionEngineV2:
    """需求定义引擎 V2 - 支持ACP协议"""

    def __init__(self, llm_client=None, prompt_mode: Optional[str] = None):
        self.llm_client = llm_client
        self.sessions: Dict[str, DemandDefinitionSession] = {}

        # 从环境变量或参数获取提示词模式
        env_mode = os.getenv("DEMAND_PROMPT_MODE", "separate")
        self.prompt_mode = PromptMode(prompt_mode or env_mode)

    def _get_dynamic_type_prompt(self) -> str:
        """动态生成需求类型识别提示词"""
        templates = list_all_templates()

        # 按类型分组
        type_groups: Dict[str, List[str]] = {}
        for template_id, info in templates.items():
            demand_type = info["type"]
            if demand_type not in type_groups:
                type_groups[demand_type] = []
            type_groups[demand_type].append(info["name"])

        # 生成提示词
        lines = [
            "你是需求类型识别专家。根据用户的输入，判断用户想要创建什么类型的需求。\n",
            "可选类型："
        ]

        for demand_type, names in type_groups.items():
            type_name = TASK_TYPE_NAMES.get(demand_type, demand_type)
            type_desc = TASK_TYPE_DESCRIPTIONS.get(demand_type, "")
            lines.append(f"- {demand_type.upper()}: {type_name}（{type_desc}）")

        lines.append("\n请按以下JSON格式输出：")
        lines.append("{")
        lines.append(f'  "demand_type": "{"/".join([t.upper() for t in type_groups.keys()])}/UNKNOWN",')
        lines.append('  "confidence": 0.0-1.0,')
        lines.append('  "to_user": "如果confidence较低，向用户询问以明确意图的回复"')
        lines.append("}")
        lines.append("\n规则：")
        lines.append("- 如果用户意图明确，返回对应类型和confidence > 0.7")
        lines.append("- 如果用户意图不明确（如只说'你好'、'在吗'），返回UNKNOWN和confidence < 0.5")
        lines.append("- to_user字段用于在不确定时与用户交互，明确其需求")

        return "\n".join(lines)

    def _get_dynamic_role_prompt(self, demand_type: str) -> str:
        """动态生成角色识别提示词"""
        templates = [t for t in TEMPLATE_REGISTRY.values() if t.demand_type == demand_type]

        lines = [
            f"你是角色识别专家。用户想要进行{TASK_TYPE_NAMES.get(demand_type, demand_type)}相关的需求。\n",
            "请判断用户在这次需求中扮演什么角色："
        ]

        for template in templates:
            lines.append(f"- {template.role}: {template.name}")

        lines.append(f"\n请只回复角色代码（如 {templates[0].role if templates else 'tenant'} 等），不要包含任何解释。")

        return "\n".join(lines)

    def _build_acp_prompt(self, session: DemandDefinitionSession, current_message: str = "") -> str:
        """构建ACP协议格式的提示词

        使用会话中的所有历史用户消息来构建完整的上下文。
        """
        timestamp = datetime.now().isoformat()

        # 构建上下文
        completed_required = len([f for f in session.filled_fields if session.template and any(
            tf.name == f and tf.required for tf in session.template.fields
        )])
        total_required = len([f for f in session.template.fields if f.required]) if session.template else 0

        # 构建已提取信息
        extracted_info = json.dumps(session.values, ensure_ascii=False, indent=2)

        # 构建待填字段
        pending_fields_str = "\n".join([
            f"  - {f.name} ({f.display_name}): {f.prompt}"
            for f in session.pending_fields[:5]  # 最多显示5个
        ])

        # 构建历史对话记录
        conversation_history_str = ""
        if session.conversation_history:
            history_lines = []
            for entry in session.conversation_history:
                role = entry.get("role", "user")
                message = entry.get("message", "")
                if role == "user":
                    history_lines.append(f"  <user>\n    {message}\n  </user>")
                else:
                    history_lines.append(f"  <assistant>\n    {message}\n  </assistant>")
            conversation_history_str = "\n".join(history_lines)

        # 如果当前消息不在历史记录中，添加它
        if current_message and not any(
            entry.get("message") == current_message and entry.get("role") == "user"
            for entry in session.conversation_history
        ):
            conversation_history_str += f"\n  <user>\n    {current_message}\n  </user>"

        prompt = f"""[ACP v1.0]
<session>
  session_id: {session.session_id}
  timestamp: {timestamp}
  turn_count: {session.turn_count}
</session>

<context>
  demand_type: {session.demand_type or 'unknown'}
  role: {session.role or 'unknown'}
  current_state: {session.state.value}
  completed_required: {completed_required}/{total_required}
  pending_fields_count: {len(session.pending_fields)}
</context>

<conversation_history>
{conversation_history_str}
</conversation_history>

<system>
  <instruction priority="high">
    分析用户的历史消息和当前消息，提取所有提到的需求信息。
    判断用户是否提供了足够信息进入下一步。
    基于完整的历史对话上下文，生成自然的回复。
  </instruction>

  <constraints>
    - 自然、灵活地与用户对话，不要机械地一问一答
    - 一次可以询问多个相关字段
    - 从用户的自然表述中提取多个字段值
    - 如果用户表达不清楚，友好地追问
    - 考虑历史对话的上下文，保持对话的连贯性
  </constraints>
</system>

<memory>
  <extracted_info>
    {extracted_info}
  </extracted_info>

  <pending_fields>
{pending_fields_str}
  </pending_fields>
</memory>

请按以下JSON格式输出：
{{
  "to_user": "对用户的自然回复，可以询问多个字段，保持对话流畅",
  "extracted": {{"字段名": "提取的值", ...}},
  "next_action": "continue|confirm|complete",
  "asked_fields": ["询问的字段名"],
  "confidence": 0.9
}}"""

        return prompt

    def _build_separate_prompt(self, session: DemandDefinitionSession, user_message: str) -> str:
        """构建独立提示词（传统模式）"""
        if session.state == DemandState.INITIAL or session.state == DemandState.IDENTIFYING_TYPE:
            return self._get_dynamic_type_prompt()
        elif session.state == DemandState.IDENTIFYING_ROLE:
            return self._get_dynamic_role_prompt(session.demand_type)
        else:
            # 使用字段提取提示词
            return self._build_field_extraction_prompt(session, user_message)

    def _build_field_extraction_prompt(self, session: DemandDefinitionSession, user_message: str) -> str:
        """构建多字段提取提示词"""
        if not session.template:
            return ""

        # 构建字段定义
        fields_def = []
        for field in session.template.fields:
            field_info = f"- {field.name} ({field.display_name}): {field.field_type.value}"
            if field.options:
                field_info += f", 选项: {', '.join(field.options)}"
            fields_def.append(field_info)

        fields_str = "\n".join(fields_def)

        # 构建已提取信息
        extracted_str = json.dumps(session.values, ensure_ascii=False, indent=2)

        prompt = f"""你是信息提取专家。从用户的自然语言表述中提取需求字段信息。

当前需求类型: {session.template.name}

所有可用字段：
{fields_str}

已提取的信息：
{extracted_str}

用户消息：
{user_message}

请分析用户消息，提取所有明确提到的字段值，并以JSON格式返回：
{{
  "extracted": {{"字段名": "提取的值", ...}},
  "mentioned_but_unclear": ["提到但不明确的字段名"],
  "next_questions": ["需要进一步确认的问题"],
  "is_complete": true/false,
  "response_to_user": "对用户的友好回复，可以询问多个未填字段"
}}

注意：
1. 从用户的自然表述中提取多个字段，不要只提取一个
2. 如果用户说"两室一厅600刀"，同时提取 bedrooms=2 和 max_price=600
3. 保持对话自然，不要机械地一问一答"""

        return prompt

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
        """处理用户消息"""
        logger.info(f"[DemandEngine] New user message received: session_id={session_id}, message='{user_message[:50]}...'")

        session = self.get_session(session_id)
        if not session:
            logger.warning(f"[DemandEngine] Session not found: session_id={session_id}")
            return {
                "success": False,
                "error": "Session not found",
                "message": "会话不存在，请重新开始"
            }

        session.turn_count += 1
        session.updated_at = datetime.now()

        # 记录用户消息
        session.conversation_history.append({
            "role": "user",
            "message": user_message,
            "timestamp": datetime.now().isoformat()
        })

        # 使用流水线模式处理 - 尽可能在一次消息中推进多个阶段
        result = self._process_pipeline(session, user_message)

        # 记录助手回复到对话历史（用于提供完整上下文给LLM）
        if result.get("success") and "message" in result:
            session.conversation_history.append({
                "role": "assistant",
                "message": result["message"],
                "timestamp": datetime.now().isoformat()
            })

        logger.info(f"[DemandEngine] Response generated: session_id={session_id}, state={result.get('state')}, pending_count={result.get('pending_count')}")
        return result

    def _process_pipeline(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """
        流水线处理模式
        在一次消息处理中，尽可能连续推进多个阶段：
        类型识别 -> 角色识别 -> 必填字段收集 -> 选填字段收集 -> 确认
        """
        extracted_info = {}  # 记录本次提取的所有信息
        progress_messages = []  # 记录处理过程中的反馈

        # ========== 阶段1: 类型识别 ==========
        if session.state in [DemandState.INITIAL, DemandState.IDENTIFYING_TYPE]:
            if not session.demand_type:
                type_result = self._detect_demand_type(user_message)
                demand_type = type_result.get("demand_type")
                if demand_type:
                    session.demand_type = demand_type
                    session.state = DemandState.IDENTIFYING_ROLE
                    extracted_info["demand_type"] = demand_type
                else:
                    # 无法识别类型，使用 LLM 提供的回复或询问用户
                    to_user = type_result.get("to_user")
                    if to_user:
                        return {
                            "success": True,
                            "state": session.state.value,
                            "message": to_user,
                            "pending_count": 0,
                            "can_complete": False
                        }
                    return self._ask_for_type()

        # ========== 阶段2: 角色识别 ==========
        if session.state == DemandState.IDENTIFYING_ROLE:
            if not session.role:
                role = self._detect_role(user_message, session.demand_type)
                if role:
                    session.role = role
                    extracted_info["role"] = role
                    # 加载模板并开始收集
                    self._load_template(session)
                    session.state = DemandState.COLLECTING
                else:
                    # 检查是否只有一个可选角色
                    templates = [t for t in TEMPLATE_REGISTRY.values() if t.demand_type == session.demand_type]
                    if len(templates) == 1:
                        session.role = templates[0].role
                        self._load_template(session)
                        session.state = DemandState.COLLECTING
                    else:
                        # 需要询问角色
                        return self._ask_for_role(session)

        # ========== 阶段3: 收集需求字段 ==========
        if session.state == DemandState.COLLECTING:
            if session.template:
                # 提取多个字段
                fields_extracted = self._extract_multiple_fields(user_message, session)
                extracted_info.update(fields_extracted)

                # 更新会话状态
                for field_name, value in fields_extracted.items():
                    session.values[field_name] = value
                    if field_name not in session.filled_fields:
                        session.filled_fields.append(field_name)

                # 更新待填字段列表
                session.pending_fields = [
                    f for f in session.template.fields
                    if f.name not in session.values
                ]

                # 检查是否可以进入确认阶段
                if self._is_required_complete(session):
                    context = {
                        "filled_fields": session.filled_fields,
                        "pending_fields": [f.name for f in session.pending_fields]
                    }
                    if not session.pending_fields or self._is_completion_intent(user_message, context):
                        session.state = DemandState.CONFIRMING
                        return self._move_to_confirming(session)

        # ========== 阶段4: 确认阶段 ==========
        if session.state == DemandState.CONFIRMING:
            return self._handle_confirming(session, user_message)

        # ========== 阶段5: 修改阶段 ==========
        if session.state == DemandState.MODIFYING:
            return self._handle_modifying(session, user_message)

        # ========== 生成回复 ==========
        if session.state == DemandState.COLLECTING:
            response = self._generate_pipeline_response(session, extracted_info)
            return {
                "success": True,
                "state": session.state.value,
                "message": response,
                "extracted": extracted_info,
                "pending_count": len(session.pending_fields),
                "can_complete": self._is_required_complete(session)
            }

        # 默认返回
        return {
            "success": True,
            "state": session.state.value,
            "message": "请继续提供信息。",
            "extracted": extracted_info
        }

    def _detect_role(self, user_message: str, demand_type: str) -> Optional[str]:
        """
        从用户消息中检测角色
        优先使用LLM，回退到关键词匹配
        """
        # 获取该类型的所有可用角色
        templates = [t for t in TEMPLATE_REGISTRY.values() if t.demand_type == demand_type]
        available_roles = [(t.role, t.name) for t in templates]

        # 如果只有一个角色，直接返回
        if len(available_roles) == 1:
            return available_roles[0][0]

        # 尝试使用LLM检测（如果可用）
        if self.llm_client:
            try:
                role = self._detect_role_with_llm(user_message, demand_type, available_roles)
                if role:
                    return role
            except Exception:
                pass  # LLM失败时回退到规则匹配

        # 回退到关键词匹配
        return self._detect_role_rule_based(user_message, demand_type, available_roles)

    def _detect_role_with_llm(
        self,
        user_message: str,
        demand_type: str,
        available_roles: List[Tuple[str, str]]
    ) -> Optional[str]:
        """使用LLM检测用户角色"""
        type_name = TASK_TYPE_NAMES.get(demand_type, demand_type)

        # 构建角色选项描述
        role_descriptions = []
        for role, name in available_roles:
            role_descriptions.append(f"- {role}: {name}")

        prompt = f"""你是角色识别专家。根据用户的输入，判断用户在{type_name}场景中的角色。

用户消息："{user_message}"

可选角色：
{chr(10).join(role_descriptions)}

请只回复角色代码（如：tenant, landlord等），不要包含任何解释。
如果无法确定角色，请回复"unknown"。"""

        response = self.llm_client.generate_response(
            "You are a helpful assistant that identifies user roles.",
            prompt
        ).strip().lower()

        # 验证返回的角色是否有效
        valid_roles = [role for role, _ in available_roles]
        if response in valid_roles:
            return response

        # 尝试从回复中提取角色
        for role, _ in available_roles:
            if role in response:
                return role

        return None

    def _detect_role_rule_based(
        self,
        user_message: str,
        demand_type: str,
        available_roles: List[Tuple[str, str]]
    ) -> Optional[str]:
        """基于规则的角色检测（回退方案）"""
        message_lower = user_message.lower()

        # 角色关键词映射
        role_keywords = {
            "tenant": ["租客", "租户", "租房", "我想租", "我要租", "承租人", "求租"],
            "landlord": ["房东", "出租", "我有房", "业主", "房主", "房源"],
            "seeker": ["找对象", "相亲", "我是男生", "我是女生", "我想找", "征友"],
            "matchmaker": ["红娘", "媒人", "帮别人", "介绍对象", "牵线"],
            "player": ["玩家", "找队友", "组队", "开黑", "求带"],
            "team_leader": ["队长", "招队员", "招募", "战队", "公会"],
        }

        for role, name in available_roles:
            keywords = role_keywords.get(role, [])
            if any(kw in message_lower for kw in keywords):
                return role

        return None

    def _load_template(self, session: DemandDefinitionSession) -> None:
        """加载模板（不返回结果）"""
        if session.demand_type and session.role:
            template = get_template_for_role(session.demand_type, session.role)
            if template:
                session.template = template
                session.pending_fields = list(template.fields)

    def _is_completion_intent(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        判断用户是否有完成意图
        优先使用LLM，回退到关键词匹配
        """
        # 尝试使用LLM判断（如果可用）
        if self.llm_client:
            try:
                result = self._detect_completion_intent_with_llm(user_message, context)
                if result is not None:
                    return result
            except Exception:
                pass  # LLM失败时回退到规则匹配

        # 回退到关键词匹配
        return self._is_completion_intent_rule_based(user_message)

    def _detect_completion_intent_with_llm(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[bool]:
        """使用LLM检测完成意图"""
        context_str = ""
        if context:
            filled_count = len(context.get("filled_fields", []))
            pending_count = len(context.get("pending_fields", []))
            context_str = f"\n已填写字段数：{filled_count}\n待填写字段数：{pending_count}"

        prompt = f"""你是意图识别专家。判断用户消息是否表示想要完成当前任务或确认信息。

用户消息："{user_message}"{context_str}

请判断用户意图：
- "complete": 用户明确表示完成、确认、结束
- "continue": 用户想继续提供信息或询问问题
- "unclear": 意图不明确

请只回复一个单词（complete/continue/unclear），不要包含任何解释。"""

        response = self.llm_client.generate_response(
            "You are a helpful assistant that detects user intent.",
            prompt
        ).strip().lower()

        if "complete" in response:
            return True
        elif "continue" in response:
            return False

        return None  # unclear 时返回None，让系统回退到规则匹配

    def _is_completion_intent_rule_based(self, user_message: str) -> bool:
        """基于规则的完成意图检测（回退方案）"""
        completion_keywords = [
            "完成", "done", "没有了", "就这些", "确认", "可以了", "ok", "好的",
            "就这样", "没问题", "行", "嗯", "对", "是的", "没错", "结束"
        ]
        message_lower = user_message.lower()
        return any(kw in message_lower for kw in completion_keywords)

    def _generate_pipeline_response(self, session: DemandDefinitionSession, extracted_info: Dict[str, Any]) -> str:
        """生成流水线模式的回复

        优先使用LLM生成回复，如果没有LLM则回退到规则。
        注意：不在确认环节之前显示已提取的信息，避免重复输出干扰聊天。
        """
        # 优先使用LLM生成回复（如果可用）
        if self.llm_client:
            try:
                # _build_acp_prompt 会自动使用 session.conversation_history 中的所有历史消息
                prompt = self._build_acp_prompt(session)
                response = self.llm_client.generate_response(
                    "You are a helpful assistant that helps users define their demands naturally.",
                    prompt
                )

                logger.debug(f"[DemandEngine] LLM raw response for pipeline: '{response[:200]}...'")

                # 尝试解析JSON，获取to_user字段
                try:
                    result = json.loads(response)
                    if "to_user" in result:
                        logger.info(f"[DemandEngine] Generated response via LLM: '{result['to_user'][:50]}...'")
                        return result["to_user"]
                except json.JSONDecodeError:
                    # 如果不是JSON，直接使用回复内容
                    logger.info(f"[DemandEngine] Generated response via LLM (non-JSON): '{response[:50]}...'")
                    return response.strip()
            except Exception as e:
                logger.warning(f"[DemandEngine] LLM response generation failed: {e}, falling back to rules")

        # 回退到规则生成回复
        responses = []
        if session.pending_fields:
            required_pending = [f for f in session.pending_fields if f.required]
            optional_pending = [f for f in session.pending_fields if not f.required]

            if required_pending:
                # 一次最多询问2个必填字段
                to_ask = required_pending[:2]
                questions = [f.prompt for f in to_ask]
                responses.append("\n".join(questions))
            elif optional_pending and len(session.filled_fields) >= 3:
                # 必填都填完了，简单询问是否有其他要求
                responses.append(f"还有其他要求吗？（如：{optional_pending[0].prompt}）")

        result = "\n\n".join(responses) if responses else "请继续提供信息。"
        logger.info(f"[DemandEngine] Generated response via rules: '{result[:50]}...'")
        return result

    def _handle_initial_state(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理初始状态"""
        # 尝试识别需求类型
        type_result = self._detect_demand_type(user_message)
        demand_type = type_result.get("demand_type")

        if demand_type:
            session.demand_type = demand_type
            session.state = DemandState.IDENTIFYING_ROLE
            return self._ask_for_role(session)
        else:
            session.state = DemandState.IDENTIFYING_TYPE
            # 使用 LLM 提供的回复或默认询问
            to_user = type_result.get("to_user")
            if to_user:
                return {
                    "success": True,
                    "state": session.state.value,
                    "message": to_user,
                    "pending_count": 0,
                    "can_complete": False
                }
            return self._ask_for_type()

    def _ask_for_type(self) -> Dict[str, Any]:
        """询问需求类型"""
        templates = list_all_templates()
        type_groups: Dict[str, List[str]] = {}

        for template_id, info in templates.items():
            demand_type = info["type"]
            if demand_type not in type_groups:
                type_groups[demand_type] = []
            if info["name"] not in type_groups[demand_type]:
                type_groups[demand_type].append(info["name"])

        options = []
        for i, (demand_type, names) in enumerate(type_groups.items(), 1):
            type_name = TASK_TYPE_NAMES.get(demand_type, demand_type)
            options.append(f"{i}. {type_name}")

        return {
            "success": True,
            "state": DemandState.IDENTIFYING_TYPE.value,
            "message": f"您好！我来帮您创建需求。请问您想要：\n\n" + "\n".join(options) + "\n\n请告诉我您的需求类型。"
        }

    def _handle_type_identification(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理类型识别状态"""
        type_result = self._detect_demand_type(user_message)
        demand_type = type_result.get("demand_type")

        if demand_type:
            session.demand_type = demand_type
            session.state = DemandState.IDENTIFYING_ROLE
            return self._ask_for_role(session)
        else:
            # 使用 LLM 提供的回复或默认询问
            to_user = type_result.get("to_user")
            if to_user:
                return {
                    "success": True,
                    "state": session.state.value,
                    "message": to_user,
                    "pending_count": 0,
                    "can_complete": False
                }
            return self._ask_for_type()

    def _ask_for_role(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """询问用户角色"""
        templates = [t for t in TEMPLATE_REGISTRY.values() if t.demand_type == session.demand_type]

        if len(templates) == 1:
            # 只有一个角色，直接设置
            session.role = templates[0].role
            return self._load_template_and_start_collecting(session)

        # 多个角色，询问用户
        options = []
        for i, template in enumerate(templates, 1):
            options.append(f"{i}. {template.name}")

        return {
            "success": True,
            "state": DemandState.IDENTIFYING_ROLE.value,
            "message": f"好的，您需要{TASK_TYPE_NAMES.get(session.demand_type, '')}服务。\n\n请问您是：\n" + "\n".join(options) + "\n\n请告诉我您的角色。"
        }

    def _handle_role_identification(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理角色识别"""
        role = self._detect_role(user_message, session.demand_type)

        if role:
            session.role = role
            return self._load_template_and_start_collecting(session)
        else:
            return self._ask_for_role(session)

    def _load_template_and_start_collecting(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """加载模板并开始收集"""
        template = get_template_for_role(session.demand_type, session.role)

        if not template:
            return {
                "success": False,
                "error": "Template not found",
                "message": "抱歉，暂时不支持该类型的需求"
            }

        session.template = template
        session.state = DemandState.COLLECTING

        # 获取所有未填字段
        all_fields = template.fields
        session.pending_fields = all_fields

        # 生成初始提示
        field_names = ", ".join([f.display_name for f in all_fields[:3]])

        return {
            "success": True,
            "state": session.state.value,
            "message": f"好的！我来帮您创建{TASK_TYPE_NAMES.get(session.demand_type, '')}需求。\n\n请告诉我您的需求，比如：{field_names}等。您可以一次告诉我多个信息。",
            "can_provide_multiple": True
        }

    def _handle_collecting(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理需求收集 - 支持多字段提取"""
        if not session.template:
            return {
                "success": False,
                "error": "No template",
                "message": "请先选择需求类型"
            }

        # 检查是否是完成指令
        if any(kw in user_message for kw in ["完成", "done", "没有了", "确认"]):
            if self._is_required_complete(session):
                return self._move_to_confirming(session)

        # 提取字段值
        extracted = self._extract_multiple_fields(user_message, session)

        # 更新会话
        for field_name, value in extracted.items():
            session.values[field_name] = value
            if field_name not in session.filled_fields:
                session.filled_fields.append(field_name)

        # 更新待填字段
        session.pending_fields = [
            f for f in session.template.fields
            if f.name not in session.values
        ]

        # 生成回复
        response = self._generate_collecting_response(session, extracted)

        # 检查是否可以进入确认
        if self._is_required_complete(session) and not session.pending_fields:
            return self._move_to_confirming(session)

        return {
            "success": True,
            "state": session.state.value,
            "message": response,
            "extracted": extracted,
            "pending_count": len(session.pending_fields),
            "can_complete": self._is_required_complete(session)
        }

    def _extract_multiple_fields(self, user_message: str, session: DemandDefinitionSession) -> Dict[str, Any]:
        """从用户消息中提取多个字段

        优先使用LLM提取，无论prompt mode是merged还是separate。
        使用完整的历史对话上下文进行提取。
        """
        extracted = {}
        logger.debug(f"[DemandEngine] Extracting fields from message: '{user_message[:50]}...'")

        # 优先使用LLM提取（如果可用）
        if self.llm_client:
            try:
                # _build_acp_prompt 会自动使用 session.conversation_history 中的所有历史消息
                # current_message 用于确保当前消息被包含（如果尚未在历史记录中）
                prompt = self._build_acp_prompt(session, current_message=user_message)
                response = self.llm_client.generate_response(
                    "You are a helpful assistant that extracts structured data from user messages.",
                    prompt
                )

                logger.debug(f"[DemandEngine] LLM raw response for extraction: '{response[:200]}...'")

                # 尝试解析JSON
                try:
                    result = json.loads(response)
                    if "extracted" in result:
                        extracted = result["extracted"]
                        logger.info(f"[DemandEngine] Fields extracted by LLM: {extracted}")
                        return extracted
                except json.JSONDecodeError:
                    logger.debug("[DemandEngine] Failed to parse LLM response as JSON")
            except Exception as e:
                logger.warning(f"[DemandEngine] LLM field extraction failed: {e}, falling back to rules")

        # 回退到规则提取
        for field in session.pending_fields:
            value = self._extract_field_value_rule_based(user_message, field)
            if value is not None:
                extracted[field.name] = value

        if extracted:
            logger.info(f"[DemandEngine] Fields extracted by rules: {extracted}")
        else:
            logger.debug("[DemandEngine] No fields extracted by rules")
        return extracted

    def _extract_field_value_rule_based(self, message: str, field: TemplateField) -> Any:
        """基于规则的字段提取"""
        message_lower = message.lower()

        if field.field_type == FieldType.ENUM and field.options:
            for option in field.options:
                if option.lower() in message_lower:
                    return option
                # 中文关键词匹配
                if option == "apartment" and any(kw in message_lower for kw in ["公寓"]):
                    return option
                if option == "house" and any(kw in message_lower for kw in ["别墅", "house"]):
                    return option

        elif field.field_type == FieldType.INTEGER:
            import re

            # 中文数字映射
            chinese_numbers = {
                '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
            }

            # 针对卧室数量的特殊处理
            if field.name == 'bedrooms':
                # 匹配 "两室"、"三居室"、"2室"、"两室一厅"等模式
                patterns = [
                    r'(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*室',  # "两室"、"3室"
                    r'(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*居',  # "三居"、"两居室"
                    r'(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*房',  # "三房"、"两房"
                    r'(\d+|一|二|两|三|四|五|六|七|八|九|十)\s*卧',  # "两卧"、"2卧室"
                ]
                for pattern in patterns:
                    match = re.search(pattern, message_lower)
                    if match:
                        num_str = match.group(1)
                        if num_str.isdigit():
                            return int(num_str)
                        return chinese_numbers.get(num_str, 2)  # 默认返回2

            # 查找数字+单位模式
            patterns = [
                rf'(\d+)\s*{field.display_name}',  # "2间卧室"
                rf'{field.display_name}\s*(\d+)',  # "卧室2间"
            ]
            for pattern in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    return int(match.group(1))

            # 通用数字提取
            numbers = re.findall(r'\d+', message)
            if numbers:
                return int(numbers[0])

        elif field.field_type == FieldType.PRICE:
            import re
            # 查找价格模式
            match = re.search(r'(\d+)\s*(刀|元|\$|aud)?', message_lower)
            if match:
                return int(match.group(1))

        elif field.field_type == FieldType.LOCATION:
            # 简单位置提取（实际应用中可以使用NER）
            if any(kw in message_lower for kw in ["cbd", "市中心"]):
                return "CBD"
            # 提取大写地点
            import re
            places = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', message)
            if places:
                return places[0]

        elif field.field_type == FieldType.BOOLEAN:
            yes_keywords = ["是", "有", "要", "需要", "yes", "true"]
            no_keywords = ["否", "没有", "不要", "不需要", "no", "false"]

            if any(kw in message_lower for kw in no_keywords):
                return False
            elif any(kw in message_lower for kw in yes_keywords):
                return True

        elif field.field_type == FieldType.RANGE:
            import re
            numbers = re.findall(r'\d+', message)
            if len(numbers) >= 2:
                return {"min": int(numbers[0]), "max": int(numbers[1])}

        return None

    def _generate_collecting_response(self, session: DemandDefinitionSession, extracted: Dict[str, Any]) -> str:
        """生成收集阶段的回复

        注意：不在确认环节之前显示已提取的信息，避免重复输出干扰聊天。
        """
        response_parts = []

        # 询问剩余字段（一次问多个），不显示已记录的中间信息
        pending_required = [f for f in session.pending_fields if f.required][:2]  # 最多问2个
        if pending_required:
            questions = [f.prompt for f in pending_required]
            response_parts.append("\n".join(questions))
        else:
            pending_optional = [f for f in session.pending_fields if not f.required][:2]
            if pending_optional:
                questions = [f.prompt for f in pending_optional]
                response_parts.append(f"还有其他要求吗？（如：{questions[0]}）")

        if not pending_required and not [f for f in session.pending_fields if f.required]:
            response_parts.append("所有必填信息已收集完成！回复\"确认\"完成需求定义，或继续补充其他信息。")

        return "\n".join(response_parts) if response_parts else "请继续提供信息。"

    def _is_required_complete(self, session: DemandDefinitionSession) -> bool:
        """检查必填字段是否完成"""
        if not session.template:
            return False

        required_fields = [f.name for f in session.template.fields if f.required]
        return all(field in session.values for field in required_fields)

    def _move_to_confirming(self, session: DemandDefinitionSession) -> Dict[str, Any]:
        """移动到确认状态"""
        session.state = DemandState.CONFIRMING

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
        if any(kw in user_message for kw in ["确认", "是的", "正确", "ok", "yes"]):
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
            session.state = DemandState.MODIFYING
            return {
                "success": True,
                "state": session.state.value,
                "message": "好的，请告诉我需要修改哪里？比如\"修改预算为800\"",
                "current_values": session.values
            }

    def _handle_modifying(self, session: DemandDefinitionSession, user_message: str) -> Dict[str, Any]:
        """处理修改"""
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

    def _detect_demand_type(self, message: str) -> Dict[str, Any]:
        """检测需求类型

        优先使用LLM进行识别，如果没有LLM则回退到规则匹配。
        返回包含 demand_type, confidence, to_user 的字典。
        """
        message_lower = message.lower().strip()
        logger.debug(f"[DemandEngine] Detecting demand type for message: '{message[:50]}...'")

        # 动态获取所有类型的关键词
        type_keywords = {
            TaskType.RENTAL: ["租", "房", "住", "室友", "公寓", "housing", "rent", "出租"],
            TaskType.DATING: ["相亲", "交友", "对象", "恋爱", "dating", "relationship", "friendship", "女朋", "男朋", "女票", "男票"],
            TaskType.GAMING: ["游戏", "王者", "lol", "吃鸡", "game", "gaming", "队友", "开黑", "play"]
        }

        # 优先使用LLM识别（如果可用）
        if self.llm_client:
            try:
                response = self.llm_client.generate_response(
                    self._get_dynamic_type_prompt(),
                    message
                )
                logger.debug(f"[DemandEngine] LLM raw response for type detection: '{response}'")

                # 尝试解析JSON响应
                try:
                    result = json.loads(response)
                    demand_type = result.get("demand_type", "UNKNOWN").upper()
                    confidence = result.get("confidence", 0.0)
                    to_user = result.get("to_user", "")

                    # 检查是否是有效类型
                    if demand_type in [t.upper() for t in type_keywords.keys()] and confidence >= 0.5:
                        logger.info(f"[DemandEngine] Demand type detected by LLM: {demand_type}, confidence: {confidence}")
                        return {
                            "demand_type": demand_type.lower(),
                            "confidence": confidence,
                            "to_user": to_user
                        }
                    else:
                        # 不确定的情况
                        logger.info(f"[DemandEngine] Demand type uncertain: {demand_type}, confidence: {confidence}")
                        return {
                            "demand_type": None,
                            "confidence": confidence,
                            "to_user": to_user or "您好！我可以帮您创建租房或相亲相关的需求。请告诉我您需要什么服务？"
                        }
                except json.JSONDecodeError:
                    # 回退到旧格式解析
                    response_upper = response.strip().upper()
                    for demand_type in type_keywords.keys():
                        if response_upper == demand_type.upper():
                            logger.info(f"[DemandEngine] Demand type detected by LLM (legacy format): {demand_type}")
                            return {
                                "demand_type": demand_type,
                                "confidence": 1.0,
                                "to_user": ""
                            }
            except Exception as e:
                logger.warning(f"[DemandEngine] LLM type detection failed: {e}, falling back to rules")

        # 回退到规则匹配：检查是否包含明确的需求关键词
        for demand_type, keywords in type_keywords.items():
            if any(kw in message_lower for kw in keywords):
                logger.info(f"[DemandEngine] Demand type detected by rules: {demand_type}")
                return {
                    "demand_type": demand_type,
                    "confidence": 1.0,
                    "to_user": ""
                }

        logger.debug("[DemandEngine] No demand type detected")
        return {
            "demand_type": None,
            "confidence": 0.0,
            "to_user": "您好！我可以帮您创建租房或相亲相关的需求。请告诉我您需要什么服务？"
        }

    def _detect_role(self, message: str, demand_type: str) -> Optional[str]:
        """检测用户角色"""
        message_lower = message.lower()

        templates = [t for t in TEMPLATE_REGISTRY.values() if t.demand_type == demand_type]

        for template in templates:
            # 为每个角色定义关键词
            role_keywords = {
                "tenant": ["租客", "租房", "找房", "tenant", "rent", "找房子"],
                "landlord": ["房东", "出租", "landlord", "有房", "房子出租"],
                "seeker": ["找", "寻求", "seeking", "需要", "想要"],
                "provider": ["提供", "招募", "provider", "供应"]
            }

            keywords = role_keywords.get(template.role, [template.role])
            if any(kw in message_lower for kw in keywords):
                return template.role

        # 使用LLM识别
        if self.llm_client:
            try:
                prompt = self._get_dynamic_role_prompt(demand_type)
                response = self.llm_client.generate_response(prompt, message)
                return response.strip().lower()
            except Exception:
                pass

        # 默认返回第一个角色
        if templates:
            return templates[0].role

        return None

    def _generate_demand_summary(self, session: DemandDefinitionSession) -> str:
        """生成需求摘要"""
        if not session.template:
            return "暂无需求信息"

        lines = [f"【{session.template.name}】", ""]

        for field in session.template.fields:
            if field.name in session.values:
                value = session.values[field.name]
                marker = "*" if field.required else ""
                lines.append(f"{marker}{field.display_name}: {value}")

        if session.custom_requirements:
            lines.append("\n特殊要求:")
            for req in session.custom_requirements:
                lines.append(f"  • {req}")

        return "\n".join(lines)

    def _apply_modification(self, session: DemandDefinitionSession, message: str) -> bool:
        """应用修改"""
        import re

        patterns = [
            r"修改\s*(\w+)\s*为\s*(.+)",
            r"(\w+)\s*改为\s*(.+)",
            r"把\s*(\w+)\s*改成\s*(.+)",
            r"(\w+)\s*变成\s*(.+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                field_name = match.group(1)
                new_value = match.group(2).strip()

                for field in session.template.fields:
                    if field.name == field_name or field.display_name in field_name:
                        session.values[field.name] = new_value
                        return True

        return False

    def is_demand_complete(self, session_id: str) -> bool:
        """检查需求是否完成"""
        session = self.get_session(session_id)
        return self._is_required_complete(session) if session else False

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
            "state": session.state.value,
            "turn_count": session.turn_count
        }
