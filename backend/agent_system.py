import os
import uuid
import re
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from backend.models import User, Task, Message, TaskStatus
from backend.storage import storage
from backend.config import (
    settings,
    TaskType,
    TASK_TYPE_NAMES,
    TASK_TYPE_DESCRIPTIONS,
    TaskWorkflow,
)
from backend.demand_definition_v2 import DemandDefinitionEngineV2, DemandState

# Unset SSLKEYLOGFILE to avoid permission errors
if "SSLKEYLOGFILE" in os.environ:
    del os.environ["SSLKEYLOGFILE"]

load_dotenv()


class AgentSystem:
    """智能体系统 - 集成需求定义引擎"""

    def __init__(self):
        self.storage = storage
        self._init_openai()
        # 初始化需求定义引擎 V2
        self.demand_engine = DemandDefinitionEngineV2(llm_client=self if self.client else None)

    def _init_openai(self):
        self.client = None
        api_key = settings.OPENAI_API_KEY
        if api_key and api_key not in ["dummy_key_for_testing", "dummy_key"]:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=api_key, base_url=settings.BASE_URL)
            except ImportError:
                pass

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=settings.MODEL,
                    temperature=settings.TEMPERATURE,
                    max_tokens=settings.MAX_TOKENS,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return response.choices[0].message.content
            except Exception:
                pass
        return self._fallback_response(user_prompt)

    def _fallback_response(self, user_message: str) -> str:
        return (
            "收到！我正在理解你的需求。为了更好地帮你，请补充两点：\n\n"
            "1. 你希望达成什么目标？\n"
            "2. 你最在意的条件是什么（预算/地点/时间/偏好等）？\n\n"
            "你可以使用任意语言描述，我会继续帮你梳理。"
        )

    def create_user_agent_interaction(self, task_id: str, user_message: str) -> Message:
        """处理用户与智能体的交互 - 使用需求定义引擎"""
        task = self.storage.get_task(task_id)
        user = self.storage.get_user(task.user_id)

        # 保存用户消息
        user_entry = Message(
            id=str(uuid.uuid4()),
            sender_id=user.id,
            receiver_id=task.agent_id,
            content=user_message,
            message_type="user",
        )
        self.storage.add_message_to_task(task_id, user_entry)

        # 检查是否有关联的需求定义会话
        session_id = task.metadata.get("demand_session_id") if task.metadata else None

        if not session_id:
            # 创建新的需求定义会话
            session = self.demand_engine.create_session(user.id, task.id)
            session_id = session.session_id

            # 保存会话ID到任务
            if not task.metadata:
                task.metadata = {}
            task.metadata["demand_session_id"] = session_id
            self.storage.update_task(task)

        # 处理用户消息
        result = self.demand_engine.process_message(session_id, user_message)

        # 构建响应消息
        response_content = result.get("message", "抱歉，我没有理解您的意思。")

        # 获取需求数据
        demand_data = self.demand_engine.get_demand_data(session_id)

        # 如果类型已识别，更新任务类型
        if demand_data and demand_data.get("demand_type"):
            detected_type = demand_data["demand_type"]
            if task.task_type in ["new", "pending"] or task.task_type != detected_type:
                task.task_type = detected_type
                self.storage.update_task(task)

        # 如果需求已完成，更新任务信息
        if result.get("completed"):
            task.task_type = demand_data.get("demand_type", task.task_type) if demand_data else task.task_type
            task.description = self._generate_task_description(demand_data) if demand_data else task.description
            task.status = TaskStatus.ACTIVE

            # 保存结构化需求数据
            task.metadata["structured_demand"] = demand_data
            task.metadata["demand_completed"] = True
            self.storage.update_task(task)

            response_content += "\n\n✅ 需求已保存，您可以随时查看或修改。"

        # 保存助手回复
        message = Message(
            id=str(uuid.uuid4()),
            sender_id=task.agent_id,
            receiver_id=user.id,
            content=response_content,
            message_type="agent",
        )
        self.storage.add_message_to_task(task_id, message)

        return message

    def _generate_task_description(self, demand_data: Dict[str, Any]) -> str:
        """根据需求数据生成任务描述"""
        demand_type = demand_data.get("type", "")
        role = demand_data.get("role", "")
        values = demand_data.get("values", {})

        if demand_type == TaskType.RENTAL:
            if role == "tenant":
                location = values.get("location", "未知区域")
                bedrooms = values.get("bedrooms", "?")
                max_price = values.get("max_price", "?")
                period = self._format_price_period(values.get("max_price_period"))
                return f"租房需求：{bedrooms}卧，预算${max_price}/{period}，{location}"
            else:
                property_type = values.get("property_type", "房源")
                price = values.get("price", "?")
                period = self._format_price_period(values.get("price_period"))
                location = values.get("address") or values.get("location")
                location_part = f"，{location}" if location else ""
                return f"出租{property_type}：${price}/{period}{location_part}"

        elif demand_type == TaskType.DATING:
            gender_pref = values.get("gender_preference", "")
            age_range = values.get("age_range", {})
            location = values.get("location", "")
            min_age = age_range.get("min", "?")
            max_age = age_range.get("max", "?")
            return f"相亲交友：{gender_pref}，{min_age}-{max_age}岁，{location}"

        elif demand_type == TaskType.GAMING:
            return f"游戏组队：{values.get('game_name', '寻找队友')}"

        return "需求定义完成"

    def get_demand_progress(self, task_id: str) -> Dict[str, Any]:
        """获取需求定义进度"""
        task = self.storage.get_task(task_id)
        if not task or not task.metadata:
            return {"has_session": False}

        session_id = task.metadata.get("demand_session_id")
        if not session_id:
            return {"has_session": False}

        session = self.demand_engine.get_session(session_id)
        if not session:
            return {"has_session": False}

        return {
            "has_session": True,
            "state": session.state.value,
            "demand_type": session.demand_type,
            "role": session.role,
            "filled_fields": session.filled_fields,
            "pending_fields": [f.display_name or f.name for f in session.pending_fields],
            "is_complete": self.demand_engine.is_demand_complete(session_id),
            "values": session.values,
            "custom_requirements": session.custom_requirements
        }

    def find_matching_tasks(self, task: Task) -> List[Task]:
        all_tasks = self.storage.get_all_tasks()
        matching_tasks = []
        task_demand = (task.metadata or {}).get("structured_demand")

        for candidate in all_tasks:
            if candidate.id == task.id:
                continue
            if candidate.task_type != task.task_type:
                continue
            if candidate.status not in [TaskStatus.PENDING, TaskStatus.ACTIVE]:
                continue

            # When both tasks carry structured demand data, apply domain-aware filters.
            cand_demand = (candidate.metadata or {}).get("structured_demand")
            if task_demand and cand_demand:
                if not self._demands_compatible(task_demand, cand_demand):
                    continue

            matching_tasks.append(candidate)

        return matching_tasks

    # ── demand compatibility helpers ─────────────────────────────────────────

    def _demands_compatible(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> bool:
        """Return True if two structured demands can be considered a candidate match."""
        dtype1 = d1.get("demand_type") or d1.get("type")
        dtype2 = d2.get("demand_type") or d2.get("type")
        if dtype1 != dtype2:
            return False
        if dtype1 == "rental":
            return self._rental_compatible(d1, d2)
        if dtype1 == "gaming":
            return self._gaming_compatible(d1, d2)
        if dtype1 == "dating":
            return self._dating_compatible(d1, d2)
        # Unknown demand type – fall through and allow
        return True

    def _rental_compatible(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> bool:
        """Rental matching requires opposite roles, same city, compatible price, and matching bedrooms."""
        r1, r2 = d1.get("role"), d2.get("role")
        if r1 == r2:          # both tenant or both landlord
            return False
        tenant_d = d1 if r1 == "tenant" else d2
        landlord_d = d2 if r1 == "tenant" else d1
        vt = tenant_d.get("values", {})
        vl = landlord_d.get("values", {})
        # City must match when both are specified
        loc_t = self._extract_city(
            vt.get("location_city") or vt.get("location") or vt.get("address")
        )
        loc_l = self._extract_city(
            vl.get("address_city") or vl.get("location_city") or vl.get("address") or vl.get("location")
        )
        if loc_t and loc_l and loc_t != loc_l:
            return False
        # Tenant's budget must cover landlord's asking price
        max_price = self._normalize_price_to_weekly(vt.get("max_price"), vt.get("max_price_period"))
        price = self._normalize_price_to_weekly(vl.get("price"), vl.get("price_period"))
        if max_price is not None and price is not None and max_price < price:
            return False
        # Number of bedrooms must match when both are specified
        br_t = vt.get("bedrooms")
        br_l = vl.get("bedrooms")
        if br_t is not None and br_l is not None and br_t != br_l:
            return False
        return True

    def _gaming_compatible(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> bool:
        """Gaming: both parties must want the same game."""
        v1, v2 = d1.get("values", {}), d2.get("values", {})
        g1 = self._canonical_game_name(v1.get("game_name"))
        g2 = self._canonical_game_name(v2.get("game_name"))
        if g1 and g2 and g1 != g2:
            return False
        return True

    def _dating_compatible(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> bool:
        """Dating: mutual gender preferences, city, and age-range overlap."""
        v1, v2 = d1.get("values", {}), d2.get("values", {})
        g1, g2 = v1.get("gender"), v2.get("gender")
        gp1, gp2 = v1.get("gender_preference"), v2.get("gender_preference")
        # d1 must prefer d2's gender
        if gp1 and g2 and gp1 != g2:
            return False
        # d2 must prefer d1's gender
        if gp2 and g1 and gp2 != g1:
            return False
        loc1 = self._extract_city(v1.get("location_city") or v1.get("location"))
        loc2 = self._extract_city(v2.get("location_city") or v2.get("location"))
        if loc1 and loc2 and loc1 != loc2:
            return False
        if not self._age_ranges_overlap(v1.get("age_range"), v2.get("age_range")):
            return False
        return True

    def _format_price_period(self, period: Optional[str]) -> str:
        return "月" if period == "monthly" else "周"

    def _normalize_price_to_weekly(self, amount: Any, period: Optional[str]) -> Optional[float]:
        if amount is None:
            return None
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return None
        if period == "monthly":
            return value * 12 / 52
        return value

    def _extract_city(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        match = re.match(r"([\u4e00-\u9fff]{2,}(?:市)?)", text)
        if match:
            candidate = match.group(1)
            if candidate.endswith("市"):
                return candidate
            if len(candidate) >= 2:
                return candidate[:2] if len(candidate) > 3 else candidate
        if "," in text:
            return text.split(",", 1)[0].strip().lower()
        return text.strip().lower()

    def _canonical_game_name(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        aliases = {
            "lol": "league of legends",
            "英雄联盟": "league of legends",
            "league of legends": "league of legends",
            "王者荣耀": "honor of kings",
            "honor of kings": "honor of kings",
            "绝地求生": "pubg",
            "pubg": "pubg",
        }
        return aliases.get(text, text)

    def _age_ranges_overlap(self, r1: Any, r2: Any) -> bool:
        if not isinstance(r1, dict) or not isinstance(r2, dict):
            return True
        try:
            min1, max1 = int(r1.get("min")), int(r1.get("max"))
            min2, max2 = int(r2.get("min")), int(r2.get("max"))
        except (TypeError, ValueError):
            return True
        return max(min1, min2) <= min(max1, max2)

    def start_negotiation(self, task1_id: str, task2_id: str):
        task1 = self.storage.get_task(task1_id)
        task2 = self.storage.get_task(task2_id)

        user1 = self.storage.get_user(task1.user_id)
        user2 = self.storage.get_user(task2.user_id)

        initial_message = Message(
            id=str(uuid.uuid4()),
            sender_id=task1.agent_id,
            content=f"你好！我是代表 {user1.username} 的智能体。我们来聊聊需求匹配的事情。",
        )

        self.storage.add_message_to_task(task1_id, initial_message)
        self.storage.add_message_to_task(task2_id, initial_message)

        task1.status = TaskStatus.MATCHING
        task2.status = TaskStatus.MATCHING
        self.storage.update_task(task1)
        self.storage.update_task(task2)


agent_system = AgentSystem()
