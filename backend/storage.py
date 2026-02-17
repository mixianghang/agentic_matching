from typing import Dict, List, Optional
from backend.models import User, Agent, Task, Message
import uuid


class InMemoryStorage:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}

    def create_user(self, username: str, email: Optional[str] = None) -> User:
        user_id = str(uuid.uuid4())
        user = User(id=user_id, username=username, email=email)
        self.users[user_id] = user
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    def create_agent(self, user_id: str, role: str) -> Agent:
        agent_id = str(uuid.uuid4())
        agent = Agent(id=agent_id, user_id=user_id, role=role)
        self.agents[agent_id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def create_task(self, user_id: str, agent_id: str, task_type: str, description: str, requirements: Dict = None) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            user_id=user_id,
            agent_id=agent_id,
            task_type=task_type,
            description=description,
            requirements=requirements or {}
        )
        self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())

    def update_task(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def add_message_to_task(self, task_id: str, message: Message):
        task = self.get_task(task_id)
        if task:
            task.messages.append(message)
            self.update_task(task)


storage = InMemoryStorage()
