from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    MATCHING = "matching"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    password_hash: Optional[str] = None
    auth_provider: Optional[str] = None
    third_party_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    private_info: Dict[str, Any] = Field(default_factory=dict)


class Token(BaseModel):
    id: str
    user_id: str
    token: str
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime
    revoked: bool = False


class Agent(BaseModel):
    id: str
    user_id: str
    role: str  # "user_agent", "task_agent", "matching_agent"
    created_at: datetime = Field(default_factory=datetime.now)
    active: bool = True


class Message(BaseModel):
    id: str
    sender_id: str
    receiver_id: Optional[str] = None
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    is_public: bool = False
    message_type: str = "agent"


class Task(BaseModel):
    id: str
    user_id: str
    agent_id: str
    task_type: str  # "dating", "rental", "gaming", etc.
    description: str
    requirements: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    matched_task_ids: List[str] = Field(default_factory=list)
    messages: List[Message] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Match scoring metadata (only populated by /matches endpoint; not persisted in storage)
    score: Optional[float] = None
    match_reason: Optional[str] = None
