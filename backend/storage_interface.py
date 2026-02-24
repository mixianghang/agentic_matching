from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from backend.models import User, Agent, Task, Message, Token


class StorageBackend(ABC):
    """
    存储后端抽象接口
    所有存储实现都必须实现这个接口
    """
    
    @abstractmethod
    def create_user(self, username: str, email: Optional[str] = None,
                   password_hash: Optional[str] = None,
                   auth_provider: Optional[str] = None,
                   third_party_id: Optional[str] = None,
                   is_active: bool = True) -> User:
        """创建用户"""
        pass
    
    @abstractmethod
    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        pass
    
    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        pass
    
    @abstractmethod
    def update_user(self, user: User) -> User:
        """更新用户"""
        pass
    
    @abstractmethod
    def get_all_users(self) -> List[User]:
        """获取所有用户"""
        pass
    
    @abstractmethod
    def create_agent(self, user_id: str, role: str) -> Agent:
        """创建智能体"""
        pass
    
    @abstractmethod
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取智能体"""
        pass
    
    @abstractmethod
    def get_agents_by_user(self, user_id: str) -> List[Agent]:
        """获取用户的所有智能体"""
        pass
    
    @abstractmethod
    def create_task(self, user_id: str, agent_id: str, task_type: str, 
                   description: str, requirements: Dict = None) -> Task:
        """创建任务"""
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        pass
    
    @abstractmethod
    def get_tasks_by_user(self, user_id: str) -> List[Task]:
        """获取用户的所有任务"""
        pass
    
    @abstractmethod
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        pass
    
    @abstractmethod
    def update_task(self, task: Task) -> Task:
        """更新任务"""
        pass
    
    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        pass
    
    @abstractmethod
    def add_message_to_task(self, task_id: str, message: Message) -> None:
        """向任务添加消息"""
        pass
    
    @abstractmethod
    def get_messages_by_task(self, task_id: str) -> List[Message]:
        """获取任务的所有消息"""
        pass
    
    @abstractmethod
    def create_token(self, user_id: str, token: str, expires_in_hours: int = 24) -> Token:
        """创建 Token"""
        pass
    
    @abstractmethod
    def get_token(self, token: str) -> Optional[Token]:
        """获取 Token"""
        pass
    
    @abstractmethod
    def verify_token(self, token: str) -> Optional[User]:
        """验证 Token 并返回用户"""
        pass
    
    @abstractmethod
    def revoke_token(self, token: str) -> bool:
        """撤销 Token"""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """初始化存储后端（创建表、连接等）"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭存储后端（关闭连接等）"""
        pass
