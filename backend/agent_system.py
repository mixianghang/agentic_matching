import os
import uuid
import re
from typing import List, Optional
from dotenv import load_dotenv
from backend.models import User, Task, Message, TaskStatus
from backend.storage import storage

load_dotenv()


class AgentSystem:
    def __init__(self):
        self.storage = storage
        self._init_openai()

    def _init_openai(self):
        self.client = None
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key != "dummy_key_for_testing" and api_key != "dummy_key":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            except ImportError:
                pass

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
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

    def _detect_task_type(self, message: str) -> str:
        if any(keyword in message for keyword in ["房", "租", "住", "合租"]):
            return "rental"
        elif any(keyword in message for keyword in ["相亲", "交友", "对象", "恋爱", "结婚"]):
            return "dating"
        elif any(keyword in message for keyword in ["游戏", "打", "开黑", "组队"]):
            return "gaming"
        return "dating"

    def create_user_agent_interaction(self, task_id: str, user_message: str) -> Message:
        task = self.storage.get_task(task_id)
        user = self.storage.get_user(task.user_id)
        
        is_new_task = task.description == "新建需求对话中..."
        
        if is_new_task:
            task_type = self._detect_task_type(user_message)
            task.task_type = task_type
            task.description = user_message
            task.status = TaskStatus.ACTIVE
            self.storage.update_task(task)
        
        system_prompt = f"""
        你是一个友好、专业的智能助手，正在帮助用户 {user.username} 完成需求匹配。
        
        用户当前任务信息：
        - 任务类型：{task.task_type}
        - 任务描述：{task.description}
        - 任务状态：{task.status}
        
        你的目标：
        1. 通过对话帮助用户澄清和完善需求
        2. 用自然、友好的中文回复
        3. 适时提供一些建议
        4. 不要太正式，像朋友一样聊天
        
        回复要简洁、有帮助，每次回复2-4句话。
        """
        
        response_content = self.generate_response(system_prompt, user_message)
        
        message = Message(
            id=str(uuid.uuid4()),
            sender_id=task.agent_id,
            content=response_content
        )
        
        self.storage.add_message_to_task(task_id, message)
        
        return message

    def find_matching_tasks(self, task: Task) -> List[Task]:
        all_tasks = self.storage.get_all_tasks()
        matching_tasks = []
        
        for candidate in all_tasks:
            if candidate.id == task.id:
                continue
            if candidate.task_type == task.task_type and candidate.status in [TaskStatus.PENDING, TaskStatus.ACTIVE]:
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
            content=f"你好！我是代表 {user1.username} 的智能体。我们来聊聊需求匹配的事情。"
        )
        
        self.storage.add_message_to_task(task1_id, initial_message)
        self.storage.add_message_to_task(task2_id, initial_message)
        
        task1.status = TaskStatus.MATCHING
        task2.status = TaskStatus.MATCHING
        self.storage.update_task(task1)
        self.storage.update_task(task2)


agent_system = AgentSystem()
