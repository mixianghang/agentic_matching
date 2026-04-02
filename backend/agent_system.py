import os
import uuid
import re
import logging
from typing import List, Optional, Dict, Any, Tuple
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
from backend.privacy import (
    DisclosureConfig,
    DisclosureEvent,
    DisclosureLevel,
    SessionDisclosureBudget,
    PrivacyFilterLayer,
    audit_log,
)

logger = logging.getLogger(__name__)

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
        response_content = self._apply_privacy_filter(
            task, session_id, response_content
        )

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
        demand_type = demand_data.get("demand_type") or demand_data.get("type", "")
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

    # ------------------------------------------------------------------
    # Privacy filter integration (Milestone 1)
    # ------------------------------------------------------------------

    def _get_disclosure_config(self, task: Task) -> DisclosureConfig:
        """Return the DisclosureConfig for a task, loading from metadata or creating a default."""
        metadata = task.metadata or {}
        raw = metadata.get("disclosure_config")
        if raw and isinstance(raw, dict):
            config = DisclosureConfig(demand_id=task.id)
            level_map = {lvl.value: lvl for lvl in DisclosureLevel}
            config.age_disclosure = level_map.get(raw.get("age_disclosure", ""), DisclosureLevel.COARSE)
            config.income_disclosure = level_map.get(raw.get("income_disclosure", ""), DisclosureLevel.NONE)
            config.occupation_disclosure = level_map.get(raw.get("occupation_disclosure", ""), DisclosureLevel.CATEGORY)
            config.location_disclosure = level_map.get(raw.get("location_disclosure", ""), DisclosureLevel.CITY)
            config.budget_disclosure = level_map.get(raw.get("budget_disclosure", ""), DisclosureLevel.RANGE)
            config.custom_overrides = {
                k: level_map.get(v, DisclosureLevel.NONE)
                for k, v in raw.get("custom_overrides", {}).items()
            }
            return config
        return DisclosureConfig(demand_id=task.id)

    def _apply_privacy_filter(
        self, task: Task, session_id: str, draft_message: str
    ) -> str:
        """Run the PrivacyFilterLayer on *draft_message* and return the safe text.

        Persists any DisclosureEvents to storage when the SQLite backend is in use.
        Falls back to the original message on any unexpected error so as not to
        break the response path.
        """
        try:
            demand_data = self.demand_engine.get_demand_data(session_id) or {}
            private_values: Dict[str, Any] = {}
            values = demand_data.get("values", {}) or {}
            if "age" in values:
                private_values["age"] = values["age"]
            if "income" in values or "annual_income" in values:
                private_values["income"] = values.get("income") or values.get("annual_income")
            if "budget" in values or "max_price" in values:
                private_values["budget"] = values.get("budget") or values.get("max_price")
            if "occupation" in values or "job" in values:
                private_values["occupation"] = values.get("occupation") or values.get("job")

            config = self._get_disclosure_config(task)
            budget = SessionDisclosureBudget(session_id=session_id)
            pfl = PrivacyFilterLayer(
                config=config,
                budget=budget,
                demand_id=task.id,
                session_id=session_id,
                peer_agent_id=task.agent_id,
            )
            filter_result = pfl.filter(draft_message, private_values=private_values)

            if filter_result.blocked:
                logger.info(
                    "Privacy filter blocked agent message for task %s: %s",
                    task.id,
                    filter_result.reasons,
                )
                return filter_result.fallback

            # Persist DisclosureEvents if storage supports it
            if filter_result.disclosed_attributes:
                from backend.storage_sqlite import SQLiteStorage
                if isinstance(self.storage, SQLiteStorage):
                    for attr_name in filter_result.disclosed_attributes:
                        coarse_val = private_values.get(attr_name, "")
                        event = DisclosureEvent(
                            demand_id=task.id,
                            session_id=session_id,
                            peer_agent_id=task.agent_id,
                            attribute_name=attr_name,
                            coarse_value=str(coarse_val),
                        )
                        self.storage.add_disclosure_event(event)
                        audit_log.append(task.user_id, event)

            return filter_result.message
        except Exception:
            logger.exception(
                "Privacy filter raised an unexpected exception for task %s; "
                "blocking message to prevent potential data leak",
                task.id,
            )
            return "抱歉，消息处理时出现错误，请稍后重试。"

    def get_disclosure_config_dict(self, task_id: str) -> Dict[str, Any]:
        """Return the DisclosureConfig for a task as a serialisable dict."""
        task = self.storage.get_task(task_id)
        if not task:
            return {}
        config = self._get_disclosure_config(task)
        return {
            "demand_id": config.demand_id,
            "age_disclosure": config.age_disclosure.value,
            "income_disclosure": config.income_disclosure.value,
            "occupation_disclosure": config.occupation_disclosure.value,
            "location_disclosure": config.location_disclosure.value,
            "budget_disclosure": config.budget_disclosure.value,
            "custom_overrides": {k: v.value for k, v in config.custom_overrides.items()},
        }

    def update_disclosure_config(self, task_id: str, updates: Dict[str, str]) -> Dict[str, Any]:
        """Update and persist DisclosureConfig for a task. Returns the new config dict."""
        task = self.storage.get_task(task_id)
        if not task:
            return {}

        config = self._get_disclosure_config(task)
        level_map = {lvl.value: lvl for lvl in DisclosureLevel}
        valid_fields = {
            "age_disclosure", "income_disclosure", "occupation_disclosure",
            "location_disclosure", "budget_disclosure",
        }
        for field, val in updates.items():
            if field in valid_fields and val in level_map:
                setattr(config, field, level_map[val])
            elif field == "custom_overrides" and isinstance(val, dict):
                config.custom_overrides = {
                    k: level_map.get(v, DisclosureLevel.NONE) for k, v in val.items()
                }

        # Persist back into task metadata
        if not task.metadata:
            task.metadata = {}
        task.metadata["disclosure_config"] = {
            "age_disclosure": config.age_disclosure.value,
            "income_disclosure": config.income_disclosure.value,
            "occupation_disclosure": config.occupation_disclosure.value,
            "location_disclosure": config.location_disclosure.value,
            "budget_disclosure": config.budget_disclosure.value,
            "custom_overrides": {k: v.value for k, v in config.custom_overrides.items()},
        }
        self.storage.update_task(task)

        return self.get_disclosure_config_dict(task_id)

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
        matching_tasks: List[Task] = []
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
            score, reason = self._compute_match_score_and_reason(task_demand, cand_demand, task, candidate)
            matching_tasks.append(self._with_match_metadata(candidate, score, reason))

        # Best-first ordering (score desc, deterministic tie-break)
        matching_tasks.sort(key=lambda t: (-(t.score if t.score is not None else -1.0), t.id))
        return matching_tasks

    def _with_match_metadata(self, task: Task, score: float, reason: str) -> Task:
        # Avoid mutating persisted Task objects returned by storage.
        if hasattr(task, "model_copy"):
            return task.model_copy(update={"score": score, "match_reason": reason})
        # Pydantic v1 fallback
        return task.copy(update={"score": score, "match_reason": reason})

    def _compute_match_score_and_reason(
        self,
        task_demand: Optional[Dict[str, Any]],
        cand_demand: Optional[Dict[str, Any]],
        target_task: Task,
        candidate_task: Task,
    ) -> Tuple[float, str]:
        if not task_demand or not cand_demand:
            return 0.5, "缺少结构化需求，采用基础匹配"

        dtype = task_demand.get("demand_type") or task_demand.get("type")
        if dtype == "rental":
            score = self._score_rental(task_demand, cand_demand)
            return score[0], score[1]
        if dtype == "dating":
            score = self._score_dating(task_demand, cand_demand)
            return score[0], score[1]
        if dtype == "gaming":
            score = self._score_gaming(task_demand, cand_demand)
            return score[0], score[1]

        return 0.5, "未知需求类型，采用基础匹配"

    def _score_rental(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> Tuple[float, str]:
        r1, r2 = d1.get("role"), d2.get("role")
        tenant_d = d1 if r1 == "tenant" else d2
        landlord_d = d2 if r1 == "tenant" else d1
        vt = tenant_d.get("values", {}) or {}
        vl = landlord_d.get("values", {}) or {}

        loc_t = self._extract_city(vt.get("location_city") or vt.get("location") or vt.get("address"))
        loc_l = self._extract_city(vl.get("address_city") or vl.get("location_city") or vl.get("address") or vl.get("location"))
        city_score = 1.0 if (loc_t and loc_l and loc_t == loc_l) else (0.8 if (loc_t or loc_l) else 0.5)

        br_t = vt.get("bedrooms")
        br_l = vl.get("bedrooms")
        bedrooms_score = (
            1.0 if (br_t is not None and br_l is not None and br_t == br_l)
            else (0.75 if (br_t is not None or br_l is not None) else 0.6)
        )

        max_price = self._normalize_price_to_weekly(vt.get("max_price"), vt.get("max_price_period"))
        price = self._normalize_price_to_weekly(vl.get("price"), vl.get("price_period"))
        if max_price is None and price is None:
            price_score = 0.4
        elif max_price is None or price is None:
            price_score = 0.6
        else:
            # Compatibility guarantees max_price >= price (when both exist). Score closer to the asking price higher.
            if max_price <= 0:
                price_score = 0.5
            else:
                ratio = float(price) / float(max_price)  # in (0,1]
                price_score = max(0.0, min(1.0, 0.3 + 0.7 * ratio))

        overall = 0.4 * city_score + 0.3 * bedrooms_score + 0.3 * price_score
        reason = f"租房匹配：{('同城' if loc_t and loc_l and loc_t == loc_l else '区域可匹配')}，卧室匹配，预算覆盖"
        return max(0.0, min(1.0, overall)), reason

    def _score_dating(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> Tuple[float, str]:
        v1, v2 = d1.get("values", {}) or {}, d2.get("values", {}) or {}

        # Mutual gender preference: d1 wants v2.gender, and d2 wants v1.gender.
        gp1, g1 = v1.get("gender_preference"), v1.get("gender")
        gp2, g2 = v2.get("gender_preference"), v2.get("gender")
        mutual_gender = bool(gp1 and g2 and gp1 == g2 and gp2 and g1 and gp2 == g1)
        gender_score = 1.0 if mutual_gender else (0.7 if (gp1 or gp2 or g1 or g2) else 0.5)

        # Age range overlap ratio (0..1), fallback conservative when missing.
        r1, r2 = v1.get("age_range"), v2.get("age_range")
        if isinstance(r1, dict) and isinstance(r2, dict):
            try:
                min1, max1 = int(r1.get("min")), int(r1.get("max"))
                min2, max2 = int(r2.get("min")), int(r2.get("max"))
                overlap = max(0, min(max1, max2) - max(min1, min2))
                span = max(1, max(max1, max2) - min(min1, min2))
                overlap_ratio = float(overlap) / float(span)
                age_score = max(0.0, min(1.0, 0.2 + 0.8 * overlap_ratio))
            except (TypeError, ValueError):
                age_score = 0.6
        else:
            age_score = 0.6

        loc1 = self._extract_city(v1.get("location_city") or v1.get("location"))
        loc2 = self._extract_city(v2.get("location_city") or v2.get("location"))
        city_score = 1.0 if (loc1 and loc2 and loc1 == loc2) else (0.8 if (loc1 or loc2) else 0.5)

        overall = 0.45 * gender_score + 0.35 * age_score + 0.2 * city_score
        reason = "相亲匹配：性别偏好互补 + 年龄窗口有重叠"
        return max(0.0, min(1.0, overall)), reason

    def _score_gaming(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> Tuple[float, str]:
        v1, v2 = d1.get("values", {}) or {}, d2.get("values", {}) or {}
        g1 = self._canonical_game_name(v1.get("game_name"))
        g2 = self._canonical_game_name(v2.get("game_name"))

        if g1 and g2 and g1 == g2:
            game_score = 1.0
        elif g1 or g2:
            game_score = 0.65
        else:
            game_score = 0.5

        rank1, rank2 = v1.get("rank"), v2.get("rank")
        rank_score = 1.0 if (rank1 and rank2 and str(rank1).strip().lower() == str(rank2).strip().lower()) else 0.0

        overall = 0.85 * game_score + 0.15 * rank_score
        reason = f"游戏匹配：{('同游戏' if g1 and g2 and g1 == g2 else '游戏可匹配')}，可选段位参考"
        return max(0.0, min(1.0, overall)), reason

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
