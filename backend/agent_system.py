import os
import uuid
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
        if any(keyword in user_message for keyword in ["找房", "租房", "房子", "合租"]):
            return "好的，我理解你在寻找住房！我来帮你：\n\n1. 先了解一下你的基本需求：预算多少？想在哪个区域？\n2. 有什么特殊要求吗（比如宠物、车位等）？\n\n请继续告诉我更多细节！"
        elif any(keyword in user_message for keyword in ["相亲", "交友", "对象", "恋爱", "认识"]):
            return "太好了，我来帮你寻找合适的人！请告诉我：\n\n1. 你想找什么样的朋友/对象？\n2. 有什么兴趣爱好或者特别要求吗？\n\n期待了解更多！"
        elif any(keyword in user_message for keyword in ["游戏", "打游戏", "组队", "开黑"]):
            return "好的！找游戏伙伴对吧！告诉我：\n\n1. 你玩什么游戏？\n2. 大概什么时间段在线？\n\n一起玩才开心！"
        else:
            return "收到！我正在理解你的需求。为了更好地帮你，请告诉我：\n\n1. 这是关于什么方面的需求？（比如：租房、相亲、游戏等）\n2. 有什么具体的要求吗？\n\n你说得越详细，我越能帮到你！"

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
                return f"租房需求：{bedrooms}卧，预算${max_price}/周，{location}"
            else:
                property_type = values.get("property_type", "房源")
                price = values.get("price", "?")
                return f"出租{property_type}：${price}/周"

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
            "pending_fields": [f.name for f in session.pending_fields],
            "is_complete": self.demand_engine.is_demand_complete(session_id),
            "values": session.values,
            "custom_requirements": session.custom_requirements
        }

    def find_matching_tasks(self, task: Task) -> List[Task]:
        all_tasks = self.storage.get_all_tasks()
        matching_tasks = []

        for candidate in all_tasks:
            if candidate.id == task.id:
                continue
            if candidate.task_type == task.task_type and candidate.status in [
                TaskStatus.PENDING,
                TaskStatus.ACTIVE,
            ]:
                matching_tasks.append(candidate)

        return matching_tasks

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
