"""
Demand Extraction Engine — core of the agentic matching system.

Implements a schema-on-read architecture where demand types are discovered dynamically
rather than hardcoded. The engine runs a three-layer pipeline:

    Layer 1 — Content Safety: blocklist + LLM classifier rejects disallowed content before
        any demand processing begins.
    Layer 2 — Intent Classify & Schema Lookup: identifies the demand type and role from the
        full session conversation history, then loads the corresponding DemandSchema from
        the SchemaRegistry. If no schema exists, triggers on-demand Schema proposal via LLM.
    Layer 3 — Schema-aware Field Extraction: extracts structured fields from natural-language
        conversation using an ACP-formatted extraction prompt. Normalizes values against the
        active schema's field definitions and enum constraints.

Architecture doc: design/demand_definition_design_v2.0.md
Integration: backend/agent_system.py wires DemandEngine into the task lifecycle.
"""
import json
import uuid
import logging
import re
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from backend.demand_models import (
    DemandSchema, SchemaField, MatchingDimension, FieldValue,
    Constraint, SemanticRequirement, StructuredDemand, ExtractionState,
)
from backend.schema_registry import schema_registry
from backend.content_safety import ContentSafetyFilter
from backend.config import TaskType, TASK_TYPE_NAMES

logger = logging.getLogger(__name__)


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM responses before JSON parsing."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[: text.rfind("```")].rstrip()
    return text.strip()


@dataclass
class ExtractionSession:
    session_id: str
    user_id: str
    task_id: Optional[str] = None
    state: ExtractionState = ExtractionState.INIT
    demand_type: Optional[str] = None
    role: Optional[str] = None
    schema: Optional[DemandSchema] = None
    values: Dict[str, Any] = field(default_factory=dict)
    custom_requirements: List[str] = field(default_factory=list)
    filled_fields: List[str] = field(default_factory=list)
    pending_fields: List[SchemaField] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    demand_id: Optional[str] = None
    safety_label: str = "safe"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class DemandEngine:
    """Schema-on-read demand extraction engine.

    Replaces the V1/V2 template-driven approach with dynamic schema discovery.
    Each demand type is represented as a DemandSchema record in the SchemaRegistry,
    enabling new types to be added at runtime without code changes.

    State machine: INIT -> SAFETY_CHECK -> INTENT_DETECT -> (PROPOSE_SCHEMA?) ->
    COLLECTING -> CONFIRMING -> (MODIFYING?) -> COMPLETED (or REJECT).

    Key design decisions (see design/demand_definition_design_v2.0.md):
    - Safety runs first: blocklisted content is rejected before any LLM call.
    - Intent classification uses full session conversation history, not just
      the current message.
    - Speculative extraction: the LLM re-extracts ALL fields from the full
      conversation history on each turn, not just the latest message.
    - Schema proposals: when a novel demand type is encountered, the LLM
      auto-generates a DemandSchema (fields + matching dimensions), stored
      as "pending" and auto-activated after 3 successful uses.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.safety_filter = ContentSafetyFilter(llm_client=llm_client)
        self.registry = schema_registry()
        self.sessions: Dict[str, ExtractionSession] = {}

    def create_session(self, user_id: str, task_id: Optional[str] = None) -> ExtractionSession:
        session = ExtractionSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            task_id=task_id,
            state=ExtractionState.INIT,
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ExtractionSession]:
        return self.sessions.get(session_id)

    def process_message(self, session_id: str, user_message: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found", "message": "会话不存在"}

        session.turn_count += 1
        session.updated_at = datetime.now()
        session.conversation_history.append({
            "role": "user", "message": user_message, "timestamp": datetime.now().isoformat(),
        })

        if session.state == ExtractionState.REJECT:
            return {"success": True, "state": "reject", "message": "该会话已被终止", "rejected": True}

        if session.state in (ExtractionState.INIT, ExtractionState.SAFETY_CHECK):
            return self._run_safety_check(session, user_message)

        if session.state == ExtractionState.INTENT_DETECT:
            return self._run_intent_detect(session, user_message)

        if session.state == ExtractionState.PROPOSE_SCHEMA:
            return self._run_propose_schema(session, user_message)

        if session.state == ExtractionState.COLLECTING:
            return self._run_collecting(session, user_message)

        if session.state == ExtractionState.CONFIRMING:
            return self._run_confirming(session, user_message)

        if session.state == ExtractionState.MODIFYING:
            return self._run_modifying(session, user_message)

        return {"success": True, "state": session.state.value, "message": "请继续提供信息。"}

    def _run_safety_check(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        safety = self.safety_filter.check(user_message, session.conversation_history)
        session.safety_label = safety["safety_label"]

        if not safety["is_safe"]:
            session.state = ExtractionState.REJECT
            return {
                "success": True, "state": "reject", "rejected": True,
                "message": self.safety_filter.get_reject_message(safety["safety_label"]),
            }

        session.state = ExtractionState.INTENT_DETECT
        return self._run_intent_detect(session, user_message)

    def _run_intent_detect(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        intent = self._classify_intent(user_message, session)
        demand_type = intent.get("demand_type")
        role = intent.get("role")

        if not demand_type:
            to_user = intent.get("to_user", "") or self._ask_for_type()
            return {
                "success": True, "state": session.state.value,
                "message": to_user,
                "pending_count": 0, "can_complete": False,
            }

        session.demand_type = demand_type

        schemas = self.registry.get_by_type(demand_type)
        if schemas:
            schema = schemas[0]
            session.schema = schema
            session.demand_id = str(uuid.uuid4())

            if role and role in schema.roles:
                session.role = role
            elif len(schema.roles) == 1:
                session.role = schema.roles[0]
            else:
                session.state = ExtractionState.COLLECTING
                return self._ask_for_role(session)

            session.pending_fields = list(schema.fields)
            session.state = ExtractionState.COLLECTING
            return self._start_collecting(session, user_message)
        else:
            session.state = ExtractionState.PROPOSE_SCHEMA
            return self._ask_schema_proposal(session)

    def _run_propose_schema(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        if self.llm_client:
            proposed = self._llm_propose_schema(session)
            if proposed:
                proposed.usage_count = 0
                proposed.status = "pending"
                self.registry.register(proposed)
                session.schema = proposed
                session.demand_type = proposed.demand_type
                session.demand_id = str(uuid.uuid4())
                if proposed.roles:
                    session.role = proposed.roles[0]
                session.pending_fields = list(proposed.fields)
                session.state = ExtractionState.COLLECTING
                schema_name = proposed.demand_type
                return {
                    "success": True, "state": "collecting",
                    "message": f"好的，我来帮您创建{schema_name}需求。请告诉我您的具体要求。",
                    "schema_proposed": proposed.schema_id,
                }

        to_user = intent.get("to_user", "") if (intent := self._classify_intent(user_message, session)) else ""
        return {
            "success": True, "state": session.state.value,
            "message": to_user or "我不太确定您的需求类型，能否详细描述一下？",
            "can_complete": False,
        }

    def _run_collecting(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        if not session.schema:
            return {"success": False, "message": "请先确认需求类型"}

        extracted = self._extract_fields_with_llm(session, user_message)

        for field_name, val in extracted.items():
            session.values[field_name] = val
            if field_name not in session.filled_fields:
                session.filled_fields.append(field_name)

        session.pending_fields = [f for f in session.schema.fields if f.key not in session.values]

        if self._is_required_complete(session):
            if self._detect_completion_intent(session, user_message):
                session.state = ExtractionState.CONFIRMING
                return self._move_to_confirming(session)
        else:
            if self._detect_completion_intent(session, user_message):
                missing = [f for f in session.schema.fields if f.required and f.key not in session.values]
                missing_names = "、".join(f.display_name for f in missing)
                return {
                    "success": True, "state": "collecting",
                    "message": f"还有几个必填信息需要补充：{missing_names}。请继续提供。",
                    "extracted": extracted, "pending_count": len(session.pending_fields),
                    "can_complete": False,
                }

        response = self._generate_collecting_response(session, extracted)
        return {
            "success": True, "state": "collecting", "message": response,
            "extracted": extracted, "pending_count": len(session.pending_fields),
            "can_complete": self._is_required_complete(session),
        }

    def _run_confirming(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        if self._is_confirmation(session, user_message):
            session.state = ExtractionState.COMPLETED
            self.registry.increment_usage(session.schema.schema_id) if session.schema else None
            demand = self.build_structured_demand(session)
            return {
                "success": True, "state": "completed", "completed": True,
                "message": "需求创建完成！正在为您寻找匹配...",
                "structured_demand": demand.to_dict(),
            }
        else:
            session.state = ExtractionState.MODIFYING
            return {
                "success": True, "state": "modifying",
                "message": "好的，请告诉我需要修改什么？",
                "current_values": session.values,
            }

    def _run_modifying(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        if self._is_confirmation(session, user_message) or self._is_no_modification(session, user_message):
            session.state = ExtractionState.COMPLETED
            self.registry.increment_usage(session.schema.schema_id) if session.schema else None
            demand = self.build_structured_demand(session)
            return {
                "success": True, "state": "completed", "completed": True,
                "message": "需求创建完成！正在为您寻找匹配...",
                "structured_demand": demand.to_dict(),
            }

        modified = self._apply_modification(session, user_message)
        if modified:
            return self._move_to_confirming(session)
        return {
            "success": True, "state": "modifying",
            "message": "请具体说明需要修改哪个字段，比如\"修改预算为800\"。",
        }

    def _classify_intent(self, user_message: str, session: ExtractionSession) -> Dict[str, Any]:
        if not self.llm_client:
            return {"demand_type": None, "role": None}
        try:
            types_list = ", ".join([s.demand_type for s in self.registry.list_active()]) or "rental, dating, gaming"

            history_block = ""
            if session.conversation_history:
                recent = session.conversation_history[-8:]
                history_lines = []
                for entry in recent:
                    role_tag = entry.get("role", "user")
                    msg = entry.get("message", "")
                    history_lines.append(f"  {role_tag}: {msg}")
                if history_lines:
                    history_block = "\nConversation history:\n" + "\n".join(history_lines)

            prompt = f"""Classify the user's demand type and role based on the FULL conversation history.

Available types: {types_list}
{history_block}

The latest user message: "{user_message}"

Consider the ENTIRE conversation to determine the demand type and role.
Return JSON:
{{"demand_type": "type_or_null", "role": "role_or_null", "confidence": 0.0-1.0, "to_user": "clarifying question if unclear"}}"""

            raw = self.llm_client.generate_response(
                "You classify user intents for a demand matching platform. Output JSON only.", prompt)
            result = json.loads(_strip_json_fences(raw))
            dt = result.get("demand_type", "").strip().lower()
            if dt in ("null", "none", ""):
                return {"demand_type": None, "role": None, "confidence": result.get("confidence", 0), "to_user": result.get("to_user", "")}
            return {
                "demand_type": dt,
                "role": result.get("role", "").strip().lower() or None,
                "confidence": result.get("confidence", 0.5),
                "to_user": result.get("to_user", ""),
            }
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")
            return {"demand_type": None, "role": None}

    def _extract_fields_with_llm(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        if not self.llm_client or not session.schema:
            return self._extract_fields_rule_based(user_message, session)

        try:
            prompt = self._build_acp_extraction_prompt(session, user_message)
            raw = self.llm_client.generate_response(
                "You extract structured fields from user messages. Output JSON only.", prompt)
            result = json.loads(_strip_json_fences(raw))
            extracted = result.get("extracted", {})
            normalized = self._normalize_extracted(session, extracted, user_message)
            logger.info(f"Extracted fields: {normalized}")
            return normalized
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return self._extract_fields_rule_based(user_message, session)

    def _build_acp_extraction_prompt(self, session: ExtractionSession, current_message: str) -> str:
        schema = session.schema
        field_descs = []
        for f in session.pending_fields[:8]:
            desc = f"- {f.key} ({f.display_name}): {f.value_type}"
            if f.options:
                desc += f" [options: {', '.join(f.options)}]"
            field_descs.append(desc)

        history_lines = []
        for entry in session.conversation_history[-10:]:
            role_tag = entry.get("role", "user")
            msg = entry.get("message", "")
            history_lines.append(f"  <{role_tag}>{msg}</{role_tag}>")

        return f"""[ACP v3.0]
<context>
  demand_type: {schema.demand_type}
  role: {session.role or 'unknown'}
  turn: {session.turn_count}
</context>

<conversation>
{chr(10).join(history_lines)}
</conversation>

<schema_fields>
{chr(10).join(field_descs)}
</schema_fields>

<already_filled>
{json.dumps(session.values, ensure_ascii=False, indent=2)}
</already_filled>

Extract ALL mentioned fields from the entire conversation. Map Chinese to enum options.
For prices, include currency and period if mentioned.
For locations, extract city name.

Return JSON:
{{"extracted": {{"field_key": "normalized_value", ...}}, "confidence": 0.9}}"""

    def _normalize_extracted(self, session: ExtractionSession, extracted: Dict, message: str) -> Dict[str, Any]:
        normalized = {}
        schema = session.schema
        if not schema:
            return extracted or {}
        field_map = {f.key: f for f in schema.fields}
        for key, val in extracted.items():
            field = field_map.get(key)
            if not field:
                field = self._find_field_by_alias(key, schema)
            if not field:
                normalized[key] = val
                continue

            if field.value_type in ("integer", "price"):
                if isinstance(val, (int, float)):
                    normalized[key] = int(val)
                elif isinstance(val, str):
                    match = re.search(r'\d+', val)
                    if match:
                        normalized[key] = int(match.group(0))
                    else:
                        normalized[key] = val
            elif field.value_type == "boolean":
                normalized[key] = self._normalize_bool(val)
            elif field.value_type == "enum" and field.options:
                lowered = str(val).strip().lower()
                if lowered in field.options:
                    normalized[key] = lowered
                else:
                    normalized[key] = val
            elif field.value_type == "range":
                if isinstance(val, dict) and "min" in val and "max" in val:
                    normalized[key] = val
                elif isinstance(val, str):
                    nums = re.findall(r'\d+', val)
                    if len(nums) >= 2:
                        normalized[key] = {"min": int(nums[0]), "max": int(nums[1])}
                    else:
                        normalized[key] = val
                else:
                    normalized[key] = val
            else:
                normalized[key] = val
        return normalized

    def _find_field_by_alias(self, key: str, schema: DemandSchema) -> Optional[SchemaField]:
        aliases = {
            "price": "max_price",
            "address": "location",
            "budget": "max_price",
        }
        real_key = aliases.get(key, key)
        for f in schema.fields:
            if f.key == real_key:
                return f
        return None

    def _normalize_bool(self, val: Any) -> Any:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            lowered = val.strip().lower()
            if lowered in ("yes", "true", "required", "need", "needed", "有", "需要", "要", "是"):
                return True
            if lowered in ("no", "false", "none", "without", "没有", "不需要", "不要", "否"):
                return False
        return val

    def _extract_fields_rule_based(self, message: str, session: ExtractionSession) -> Dict[str, Any]:
        extracted = {}
        if not session.schema:
            return extracted
        for field in session.pending_fields[:5]:
            msg_lower = message.lower()
            if field.value_type == "enum" and field.options:
                for opt in field.options:
                    if opt.lower() in msg_lower:
                        extracted[field.key] = opt
                        break
            elif field.value_type in ("integer", "price"):
                nums = re.findall(r'\d+', message)
                if nums:
                    extracted[field.key] = int(nums[0])
        return extracted

    def _detect_completion_intent(self, session: ExtractionSession, user_message: str) -> bool:
        if not self.llm_client:
            return _rule_completion_intent(user_message)
        try:
            prompt = f"""Classify if this user message intends to COMPLETE/CONFIRM the demand.

User: "{user_message}"
Context: {len(session.filled_fields)} fields filled, {len(session.pending_fields)} pending.

Labels: complete, continue, unclear
Return JSON: {{"intent": "label", "confidence": 0.9}}"""

            raw = self.llm_client.generate_response(
                "You are an intent classifier. Output JSON only.", prompt)
            result = json.loads(_strip_json_fences(raw))
            return str(result.get("intent", "")).strip().lower() == "complete"
        except Exception:
            return _rule_completion_intent(user_message)

    def _is_confirmation(self, session: ExtractionSession, user_message: str) -> bool:
        msg = user_message.strip().lower()
        if msg in ("确认", "是的", "对", "没错", "ok", "yes", "confirm", "可以", "好的", "好", "没问题", "完成"):
            return True
        return self._detect_completion_intent(session, user_message)

    def _is_no_modification(self, session: ExtractionSession, user_message: str) -> bool:
        msg = user_message.strip().lower()
        return msg in ("没有了", "不用", "不需要修改", "不修改", "no", "none", "没有")

    def _is_required_complete(self, session: ExtractionSession) -> bool:
        if not session.schema:
            return False
        return all(f.key in session.values for f in session.schema.fields if f.required)

    def _generate_collecting_response(self, session: ExtractionSession, extracted: Dict) -> str:
        if self.llm_client and session.schema:
            try:
                prompt = self._build_conversational_response_prompt(session)
                raw = self.llm_client.generate_response(
                    "You are a helpful demand collection assistant. Reply naturally in Chinese.", prompt)
                try:
                    result = json.loads(_strip_json_fences(raw))
                    if "to_user" in result:
                        return result["to_user"]
                except json.JSONDecodeError:
                    return raw.strip()
            except Exception:
                pass

        pending_req = [f for f in session.pending_fields if f.required][:2]
        if pending_req:
            return "\n".join(f.prompt for f in pending_req)
        pending_opt = [f for f in session.pending_fields if not f.required][:2]
        if pending_opt:
            prompts = [f.prompt for f in pending_opt]
            return f"还有其他要求吗？如：{prompts[0]}"
        if self._is_required_complete(session):
            return "所有必填信息已收集完成！回复\"确认\"完成需求。"
        return "请继续提供信息。"

    def _build_conversational_response_prompt(self, session: ExtractionSession) -> str:
        pending_names = [f"{f.display_name}({f.prompt})" for f in session.pending_fields[:5]]
        history = "\n".join(
            f"{e.get('role','user')}: {e.get('message','')[:100]}"
            for e in session.conversation_history[-6:]
        )
        return f"""Generate a natural Chinese response to collect remaining demand info.

Demand type: {session.schema.demand_type if session.schema else 'unknown'}
Role: {session.role}
Filled: {json.dumps(session.values, ensure_ascii=False)}
Pending: {', '.join(pending_names)}
Recent conversation:
{history}

Keep it concise (1-3 sentences). Ask about 1-2 pending fields naturally.
If all required are done, ask user to confirm.

Return JSON: {{"to_user": "your response"}}"""

    def _move_to_confirming(self, session: ExtractionSession) -> Dict[str, Any]:
        summary = self._build_demand_summary(session)
        return {
            "success": True, "state": "confirming",
            "message": f"请确认您的需求：\n\n{summary}\n\n信息准确吗？回复\"确认\"完成。",
            "demand_summary": session.values,
        }

    def _build_demand_summary(self, session: ExtractionSession) -> str:
        if not session.schema:
            return str(session.values)
        lines = [f"【{session.schema.demand_type.upper()}】"]
        for f in session.schema.fields:
            if f.key in session.values:
                marker = "*" if f.required else ""
                lines.append(f"{marker}{f.display_name}: {session.values[f.key]}")
        return "\n".join(lines)

    def _apply_modification(self, session: ExtractionSession, message: str) -> bool:
        if not self.llm_client or not session.schema:
            return False
        field_names = [{"name": f.key, "display": f.display_name} for f in session.schema.fields]
        try:
            prompt = f"""Parse modification request.

Message: {message}
Fields: {json.dumps(field_names, ensure_ascii=False)}

Return JSON: {{"action": "modify|no_change", "field": "field_key", "value": "new_value"}}"""
            raw = self.llm_client.generate_response(
                "You parse modification requests. Output JSON only.", prompt)
            result = json.loads(_strip_json_fences(raw))
            if result.get("action") != "modify":
                return False
            field = result.get("field", "")
            if field in session.values:
                session.values[field] = result.get("value")
                return True
            return False
        except Exception as e:
            logger.warning(f"Modification parsing failed: {e}")
            return False

    def _llm_propose_schema(self, session: ExtractionSession) -> Optional[DemandSchema]:
        if not self.llm_client:
            return None
        try:
            history = "\n".join(
                f"{e.get('role','user')}: {e.get('message','')}"
                for e in session.conversation_history[-6:]
            )
            prompt = f"""Propose a demand schema for this new type of demand.

Conversation:
{history}

Generate a complete schema definition in JSON:
{{
  "demand_type": "short_english_label",
  "roles": ["role1", "role2"],
  "fields": [
    {{"key": "field_name", "display_name": "中文名", "value_type": "enum|text|price|geo|range|integer|boolean|tags|date", "required": true, "prompt": "向用户询问的自然语言问题", "options": ["option1", "option2"], "matching_dimension": "dimension_id_or_null"}}
  ],
  "matching_dimensions": [
    {{"dimension_id": "id", "name": "中文名", "field_keys": {{"role1": ["field_name"], "role2": ["field_name"]}}, "comparator": "exact|enum_compatible|range_overlap|numeric_compatibility|geo_proximity", "weight": 0.3, "is_hard_filter": false}}
  ]
}}

Include at least 3 required fields. Weights must sum to 1.0. Return ONLY the JSON."""

            raw = self.llm_client.generate_response(
                "You are a schema designer for a demand matching system. Output JSON only.", prompt)
            schema_dict = json.loads(_strip_json_fences(raw))
            from backend.demand_models import SchemaField as SF, MatchingDimension as MD
            fields = [SF.from_dict(f) for f in schema_dict.get("fields", [])]
            dims = [MD.from_dict(d) for d in schema_dict.get("matching_dimensions", [])]
            demand_type = schema_dict.get("demand_type", "custom").lower().replace(" ", "_")
            return DemandSchema(
                schema_id=f"{demand_type}_v1",
                demand_type=demand_type,
                roles=schema_dict.get("roles", ["user"]),
                fields=fields,
                matching_dimensions=dims,
                version=1, status="pending", usage_count=0,
            )
        except Exception as e:
            logger.warning(f"Schema proposal failed: {e}")
            return None

    def _ask_for_type(self) -> str:
        schemas = self.registry.list_active()
        if not schemas:
            return "您好！请告诉我您的需求是什么？比如租房、交友、游戏组队等等。"
        options = []
        for i, s in enumerate(schemas, 1):
            options.append(f"{i}. {TASK_TYPE_NAMES.get(s.demand_type, s.demand_type)}")
        return "您好！请问您想要：\n\n" + "\n".join(options) + "\n\n请告诉我您的需求类型。"

    def _ask_for_role(self, session: ExtractionSession) -> Dict[str, Any]:
        if not session.schema:
            return {"success": False, "message": "请先确认需求类型"}
        roles = session.schema.roles
        if len(roles) == 1:
            session.role = roles[0]
            return {"success": True, "state": "collecting", "message": "好的，请告诉我您的具体需求。"}
        return {
            "success": True, "state": "collecting",
            "message": f"请问您是：{'/'.join(roles)}？",
        }

    def _ask_schema_proposal(self, session: ExtractionSession) -> Dict[str, Any]:
        return {
            "success": True, "state": "propose_schema",
            "message": "我不太确定您的需求类型，能否详细描述一下您想要什么？",
        }

    def _start_collecting(self, session: ExtractionSession, user_message: str) -> Dict[str, Any]:
        if not session.schema:
            return {"success": False, "message": "请先确认需求类型"}

        extracted = self._extract_fields_with_llm(session, user_message)
        for field_name, val in extracted.items():
            session.values[field_name] = val
            if field_name not in session.filled_fields:
                session.filled_fields.append(field_name)

        session.pending_fields = [f for f in session.schema.fields if f.key not in session.values]
        response = self._generate_collecting_response(session, extracted)

        return {
            "success": True, "state": "collecting", "message": response,
            "extracted": extracted, "pending_count": len(session.pending_fields),
            "can_complete": self._is_required_complete(session),
        }

    def build_structured_demand(self, session: ExtractionSession) -> StructuredDemand:
        fields = {}
        for key, val in session.values.items():
            field_def = None
            if session.schema:
                for f in session.schema.fields:
                    if f.key == key:
                        field_def = f
                        break
            vtype = field_def.value_type if field_def else "text"
            fv = FieldValue(raw=val, normalized=val, value_type=vtype, confidence=0.9)
            if vtype in ("price",) and isinstance(val, (int, float)):
                fv.amount = float(val)
                fv.currency = "AUD"
                fv.period = "weekly"
            if vtype in ("geo",):
                fv.city = self._extract_city_text(str(val))
            fields[key] = fv

        universal = {
            "role": session.role,
            "target": session.demand_type,
            "location": fields.get("location", None),
        }

        semantic = [
            SemanticRequirement(text=req)
            for req in session.custom_requirements
        ]

        return StructuredDemand(
            demand_id=session.demand_id or str(uuid.uuid4()),
            schema_id=session.schema.schema_id if session.schema else "",
            demand_type=session.demand_type or "",
            role=session.role or "",
            universal=universal,
            fields=fields,
            hard_constraints=[],
            soft_preferences=[],
            semantic_requirements=semantic,
        )

    def _extract_city_text(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""
        match = re.match(r"([\u4e00-\u9fff]{2,}(?:市)?)", cleaned)
        if match:
            return match.group(1)
        if "," in cleaned:
            return cleaned.split(",", 1)[0].strip().lower()
        return cleaned.lower()

    def get_demand_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "demand_id": session.demand_id,
            "demand_type": session.demand_type,
            "role": session.role,
            "schema_id": session.schema.schema_id if session.schema else None,
            "values": session.values,
            "custom_requirements": session.custom_requirements,
            "is_complete": session.state == ExtractionState.COMPLETED,
            "state": session.state.value,
            "turn_count": session.turn_count,
        }

    def is_demand_complete(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        return session is not None and session.state == ExtractionState.COMPLETED


def _rule_completion_intent(user_message: str) -> bool:
    confirm_words = ["确认", "是的", "对", "没错", "ok", "yes", "confirm", "可以", "好的", "好", "没问题", "完成", "就这样", "行"]
    msg = user_message.strip().lower()
    return any(w in msg for w in confirm_words)
