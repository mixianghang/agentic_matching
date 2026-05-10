import os
import uuid
import re
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
from backend.demand_engine import DemandEngine, ExtractionState
from backend.matching.generic_engine import GenericMatchingEngine
from backend.demand_models import StructuredDemand

if "SSLKEYLOGFILE" in os.environ:
    del os.environ["SSLKEYLOGFILE"]

load_dotenv()


class AgentSystem:

    def __init__(self):
        self.storage = storage
        self._init_openai()
        llm = self if self.client else None
        self.demand_engine = DemandEngine(llm_client=llm)
        self.matching_engine = GenericMatchingEngine()

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
        task = self.storage.get_task(task_id)
        user = self.storage.get_user(task.user_id)

        user_entry = Message(
            id=str(uuid.uuid4()),
            sender_id=user.id,
            receiver_id=task.agent_id,
            content=user_message,
            message_type="user",
        )
        self.storage.add_message_to_task(task_id, user_entry)

        session_id = task.metadata.get("demand_session_id") if task.metadata else None
        if not session_id:
            session = self.demand_engine.create_session(user.id, task.id)
            session_id = session.session_id
            if not task.metadata:
                task.metadata = {}
            task.metadata["demand_session_id"] = session_id
            self.storage.update_task(task)

        result = self.demand_engine.process_message(session_id, user_message)
        response_content = result.get("message", "抱歉，我没有理解您的意思。")

        demand_data = self.demand_engine.get_demand_data(session_id)
        if demand_data and demand_data.get("demand_type"):
            detected_type = demand_data["demand_type"]
            if task.task_type in ("new", "pending") or task.task_type != detected_type:
                task.task_type = detected_type if detected_type in ("rental", "dating", "gaming") else "rental"
                self.storage.update_task(task)

        if result.get("rejected"):
            task.metadata["rejected"] = True
            task.metadata["reject_reason"] = "content_safety"
            self.storage.update_task(task)
            response_content = result.get("message", "")

        if result.get("completed"):
            sd = result.get("structured_demand", {})
            task.metadata["structured_demand"] = sd
            task.metadata["demand_completed"] = True
            if sd:
                task.task_type = sd.get("demand_type", task.task_type)
                task.description = f"{sd.get('demand_type','')}需求: {sd.get('role','')}"
            task.status = TaskStatus.ACTIVE
            self.storage.update_task(task)
            response_content += "\n\n需求已创建，正在寻找匹配..."

        message = Message(
            id=str(uuid.uuid4()),
            sender_id=task.agent_id,
            receiver_id=user.id,
            content=response_content,
            message_type="agent",
        )
        self.storage.add_message_to_task(task_id, message)
        return message

    def get_demand_progress(self, task_id: str) -> Dict[str, Any]:
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
            "schema_id": session.schema.schema_id if session.schema else None,
            "filled_fields": session.filled_fields,
            "pending_fields": [f.display_name or f.key for f in session.pending_fields],
            "is_complete": self.demand_engine.is_demand_complete(session_id),
            "values": session.values,
            "custom_requirements": session.custom_requirements,
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

            cand_demand = (candidate.metadata or {}).get("structured_demand")
            if task_demand and cand_demand:
                try:
                    sd1 = StructuredDemand.from_dict(task_demand)
                    sd2 = StructuredDemand.from_dict(cand_demand)
                    score, reason, _ = self.matching_engine.compute_match(sd1, sd2)
                except Exception:
                    score, reason = 0.5, "matching_error"
            else:
                score, reason = 0.5, "缺少结构化需求"

            matching_tasks.append(self._with_match_metadata(candidate, score, reason))

        matching_tasks.sort(key=lambda t: (-(t.score if t.score is not None else -1.0), t.id))
        return matching_tasks

    def _with_match_metadata(self, task: Task, score: float, reason: str) -> Task:
        if hasattr(task, "model_copy"):
            return task.model_copy(update={"score": score, "match_reason": reason})
        return task.copy(update={"score": score, "match_reason": reason})


agent_system = AgentSystem()
