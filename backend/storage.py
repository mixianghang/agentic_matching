from typing import Dict, List, Optional
from datetime import datetime, timedelta
from backend.models import User, Agent, Task, Message, Token
from backend.storage_interface import StorageBackend
from backend.config import settings
import uuid


class InMemoryStorage(StorageBackend):
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.messages: Dict[str, List[Message]] = {}
        self.tokens: Dict[str, Token] = {}
    
    def initialize(self) -> None:
        pass
    
    def close(self) -> None:
        pass
    
    def create_user(self, username: str, email: Optional[str] = None,
                   password_hash: Optional[str] = None,
                   auth_provider: Optional[str] = None,
                   third_party_id: Optional[str] = None,
                   is_active: bool = True) -> User:
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id, 
            username=username, 
            email=email,
            password_hash=password_hash,
            auth_provider=auth_provider,
            third_party_id=third_party_id,
            is_active=is_active
        )
        self.users[user_id] = user
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def get_user_by_third_party_id(self, auth_provider: str, third_party_id: str) -> Optional[User]:
        for user in self.users.values():
            if user.auth_provider == auth_provider and user.third_party_id == third_party_id:
                return user
        return None
    
    def update_user(self, user: User) -> User:
        self.users[user.id] = user
        return user
    
    def get_all_users(self) -> List[User]:
        return list(self.users.values())
    
    def create_agent(self, user_id: str, role: str) -> Agent:
        agent_id = str(uuid.uuid4())
        agent = Agent(id=agent_id, user_id=user_id, role=role)
        self.agents[agent_id] = agent
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)
    
    def get_agents_by_user(self, user_id: str) -> List[Agent]:
        return [agent for agent in self.agents.values() if agent.user_id == user_id]
    
    def create_task(self, user_id: str, agent_id: str, task_type: str, 
                   description: str, requirements: Dict = None) -> Task:
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
        self.messages[task_id] = []
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)
    
    def get_tasks_by_user(self, user_id: str) -> List[Task]:
        return [task for task in self.tasks.values() if task.user_id == user_id]
    
    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())
    
    def update_task(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task
    
    def delete_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            if task_id in self.messages:
                del self.messages[task_id]
            return True
        return False
    
    def add_message_to_task(self, task_id: str, message: Message) -> None:
        task = self.get_task(task_id)
        if task:
            if task_id not in self.messages:
                self.messages[task_id] = []
            self.messages[task_id].append(message)
            task.messages = self.messages[task_id]
            self.update_task(task)
    
    def get_messages_by_task(self, task_id: str) -> List[Message]:
        return self.messages.get(task_id, [])
    
    def create_token(self, user_id: str, token: str, expires_in_hours: int = 24) -> Token:
        token_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        token_obj = Token(
            id=token_id,
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        self.tokens[token] = token_obj
        return token_obj
    
    def get_token(self, token: str) -> Optional[Token]:
        return self.tokens.get(token)
    
    def verify_token(self, token: str) -> Optional[User]:
        token_obj = self.tokens.get(token)
        if not token_obj:
            return None
        if token_obj.revoked:
            return None
        if datetime.now() > token_obj.expires_at:
            return None
        return self.users.get(token_obj.user_id)
    
    def revoke_token(self, token: str) -> bool:
        token_obj = self.tokens.get(token)
        if token_obj:
            token_obj.revoked = True
            return True
        return False


def get_storage_backend() -> StorageBackend:
    storage_type = settings.STORAGE_TYPE
    
    if storage_type == "in_memory":
        return InMemoryStorage()
    elif storage_type == "sqlite":
        from backend.storage_sqlite import SQLiteStorage
        storage = SQLiteStorage(settings.DATABASE_URL)
        storage.initialize()
        return storage
    elif storage_type == "postgresql":
        from backend.storage_postgres import PostgreSQLStorage
        db_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        storage = PostgreSQLStorage(db_url)
        storage.initialize()
        return storage
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


storage = get_storage_backend()
