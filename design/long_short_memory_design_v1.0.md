# 短期与长期记忆模块详细设计

## 一、记忆模块概述

记忆模块是智能代理系统的核心组件，负责存储和管理用户的短期上下文信息与长期偏好数据，为需求定义加速、匹配准确度提升提供数据支持。

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **分层存储** | 区分短期对话记忆与长期用户画像，采用不同存储策略 |
| **隐私优先** | 数据脱敏存储，用户可控制分享粒度，支持遗忘机制 |
| **动态更新** | 实时更新短期记忆，异步聚合更新长期记忆 |
| **可解释性** | 记忆内容可追溯来源，支持人工干预和修正 |
| **高效检索** | 支持向量化检索和结构化查询，满足实时性要求 |

### 1.2 记忆模块在整体架构中的位置

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI 后端层                          │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                   主应用服务                             │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────────┐   ┌───────────────┐
│  智能体系统   │   │   记忆模块        │   │   工具组件    │
│  (Agent)      │   │  ┌─────────────┐ │   │  (Tools)      │
│               │   │  │短期记忆缓存 │ │   │               │
│               │   │  ├─────────────┤ │   │               │
│               │───┼─▶│长期记忆存储 │ │   │               │
│               │   │  ├─────────────┤ │   │               │
│               │   │  │向量检索引擎 │ │   │               │
│               │   │  └─────────────┘ │   │               │
└───────────────┘   └───────────────────┘   └───────────────┘
```

---

## 二、记忆数据结构设计

### 2.1 短期记忆 (Short-Term Memory)

短期记忆存储当前对话会话的上下文信息，生命周期为一次任务会话。

```python
# short_term_memory.py

from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class ExtractedEntity(BaseModel):
    """从对话中提取的实体"""
    entity_type: str  # person, location, price, date, etc.
    value: Any
    confidence: float
    source_message_id: str
    created_at: datetime

class ConversationTurn(BaseModel):
    """单轮对话记录"""
    turn_id: str
    role: str  # "user" or "assistant" or "agent"
    message: str
    timestamp: datetime
    intent: Optional[str]  # 识别的意图
    entities: List[ExtractedEntity] = []
    sentiment: Optional[float]  # 情感得分 -1到1

class ShortTermMemory:
    """
    短期记忆 - 会话级内存
    存储在Redis，TTL=24小时或会话结束
    """
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.user_id: Optional[str] = None
        self.current_task_id: Optional[str] = None
        self.current_demand_id: Optional[str] = None
        self.conversation_history: List[ConversationTurn] = []
        self.extracted_info: Dict[str, Any] = {}  # 当前会话已提取信息
        self.pending_fields: List[str] = []  # 待补充字段
        self.context_stack: List[Dict] = []  # 上下文栈，用于多轮嵌套
        self.mentioned_custom: List[str] = []  # 提到的自定义需求
        self.last_active: datetime = Field(default_factory=datetime.now)
        
        # 状态追踪
        self.current_state: str = "initial"  # 对话状态
        self.consecutive_unknowns: int = 0  # 连续未知回答
        self.negotiation_state: Optional[Dict] = None  # 协商状态
        
    def add_turn(self, turn: ConversationTurn):
        """添加一轮对话"""
        self.conversation_history.append(turn)
        self.last_active = datetime.now()
        
        # 提取实体更新到extracted_info
        for entity in turn.entities:
            self._update_extracted_info(entity)
    
    def _update_extracted_info(self, entity: ExtractedEntity):
        """更新提取信息，保留高置信度"""
        key = entity.entity_type
        if key not in self.extracted_info:
            self.extracted_info[key] = entity.value
        elif entity.confidence > 0.8:  # 高置信度覆盖
            self.extracted_info[key] = entity.value
    
    def get_recent_context(self, turns: int = 5) -> List[ConversationTurn]:
        """获取最近N轮对话"""
        return self.conversation_history[-turns:]
    
    def to_dict(self) -> Dict:
        """序列化用于Redis存储"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "current_task_id": self.current_task_id,
            "current_demand_id": self.current_demand_id,
            "conversation_history": [t.dict() for t in self.conversation_history],
            "extracted_info": self.extracted_info,
            "pending_fields": self.pending_fields,
            "mentioned_custom": self.mentioned_custom,
            "current_state": self.current_state,
            "last_active": self.last_active.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ShortTermMemory":
        """反序列化"""
        mem = cls(data["session_id"])
        mem.user_id = data.get("user_id")
        mem.current_task_id = data.get("current_task_id")
        mem.current_demand_id = data.get("current_demand_id")
        mem.conversation_history = [ConversationTurn(**t) for t in data.get("conversation_history", [])]
        mem.extracted_info = data.get("extracted_info", {})
        mem.pending_fields = data.get("pending_fields", [])
        mem.mentioned_custom = data.get("mentioned_custom", [])
        mem.current_state = data.get("current_state", "initial")
        mem.last_active = datetime.fromisoformat(data.get("last_active", datetime.now().isoformat()))
        return mem
```

### 2.2 长期记忆 (Long-Term Memory)

长期记忆存储用户的持久化画像，生命周期与用户账号绑定。

```python
# long_term_memory.py

from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum

class VerificationLevel(str, Enum):
    """验证级别"""
    UNVERIFIED = "unverified"
    SELF_CLAIMED = "self_claimed"
    BASIC = "basic"  # 基础验证
    ADVANCED = "advanced"  # 高级验证（如人脸、证件）

class PreferenceCategory(str, Enum):
    """偏好类别"""
    DATING = "dating"
    RENTAL = "rental"
    SECOND_HAND = "second_hand"
    CARPOOL = "carpool"
    SERVICE = "service"
    GENERAL = "general"

class UserBasicInfo(BaseModel):
    """用户基础信息"""
    user_id: str
    username: str
    gender: Optional[str]
    age: Optional[int]
    location: Optional[str]  # 常驻地区
    occupation: Optional[str]
    education: Optional[str]
    languages: List[str] = []
    
    # 验证状态
    verification_level: VerificationLevel = VerificationLevel.UNVERIFIED
    verified_fields: List[str] = []  # 已验证字段
    verified_at: Optional[datetime] = None

class PreferenceValue(BaseModel):
    """偏好值，带时间戳和置信度"""
    value: Any
    confidence: float  # 0-1
    source: str  # "explicit", "inferred", "default"
    first_seen: datetime
    last_updated: datetime
    update_count: int = 1
    
    def update(self, new_value: Any, confidence: float, source: str):
        """更新偏好值"""
        if self.value != new_value:
            self.value = new_value
            self.update_count += 1
        self.confidence = max(self.confidence, confidence)  # 取最高置信度
        self.source = source if source == "explicit" else self.source  # 显式输入优先
        self.last_updated = datetime.now()

class UserPreferences(BaseModel):
    """用户偏好聚合"""
    user_id: str
    categories: Dict[PreferenceCategory, Dict[str, PreferenceValue]] = {}
    
    def get_preference(self, category: PreferenceCategory, key: str, default=None):
        """获取偏好值"""
        if category in self.categories and key in self.categories[category]:
            return self.categories[category][key].value
        return default
    
    def set_preference(self, category: PreferenceCategory, key: str, 
                      value: Any, confidence: float = 1.0, 
                      source: str = "explicit"):
        """设置偏好"""
        if category not in self.categories:
            self.categories[category] = {}
        
        now = datetime.now()
        if key in self.categories[category]:
            self.categories[category][key].update(value, confidence, source)
        else:
            self.categories[category][key] = PreferenceValue(
                value=value,
                confidence=confidence,
                source=source,
                first_seen=now,
                last_updated=now
            )

class InteractionHistory(BaseModel):
    """交互历史摘要"""
    interaction_id: str
    timestamp: datetime
    task_type: str
    outcome: str  # "success", "failure", "abandoned"
    satisfaction: Optional[float]  # 满意度评分
    tags: List[str] = []
    embedding: Optional[List[float]]  # 交互向量表示

class LongTermMemory:
    """
    长期记忆 - 用户级持久化存储
    存储在PostgreSQL + 向量数据库
    """
    def __init__(self, user_id: str):
        self.user_id: str = user_id
        self.basic_info: Optional[UserBasicInfo] = None
        self.preferences: UserPreferences = UserPreferences(user_id=user_id)
        self.interaction_history: List[InteractionHistory] = []
        
        # 行为模式
        self.response_patterns: Dict[str, Any] = {
            "active_hours": [],  # 活跃时间段
            "avg_response_time": None,  # 平均响应时间
            "negotiation_style": "unknown",  # direct/indirect/flexible
            "common_phrases": [],  # 常用表达
            "price_sensitivity": None  # 价格敏感度
        }
        
        # 信用与验证
        self.credit_score: float = 0.0
        self.credit_history: List[Dict] = []
        
        # 统计信息
        self.total_tasks: int = 0
        self.success_rate: float = 0.0
        self.created_at: datetime = Field(default_factory=datetime.now)
        self.updated_at: datetime = Field(default_factory=datetime.now)
    
    def update_from_interaction(self, interaction_data: Dict):
        """从一次交互更新长期记忆"""
        # 更新统计
        self.total_tasks += 1
        
        # 更新行为模式
        self._update_response_patterns(interaction_data)
        
        # 提取偏好（通过LLM分析）
        extracted_prefs = self._extract_preferences(interaction_data)
        for category, key, value, confidence in extracted_prefs:
            self.preferences.set_preference(
                category, key, value, 
                confidence=confidence, 
                source="inferred"
            )
        
        self.updated_at = datetime.now()
    
    def _update_response_patterns(self, interaction_data: Dict):
        """更新响应模式"""
        # 更新时间分布
        hour = interaction_data.get("timestamp", datetime.now()).hour
        if hour not in self.response_patterns["active_hours"]:
            self.response_patterns["active_hours"].append(hour)
        
        # 更新常用表达
        if "user_messages" in interaction_data:
            # 使用TF-IDF或简单统计提取高频词
            pass
    
    def _extract_preferences(self, interaction_data: Dict) -> List[tuple]:
        """从交互中提取偏好（简化版，实际可用LLM）"""
        extracted = []
        # 这里由LLM分析对话，返回提取的偏好
        return extracted
    
    def to_db_document(self) -> Dict:
        """转换为数据库文档"""
        return {
            "user_id": self.user_id,
            "basic_info": self.basic_info.dict() if self.basic_info else None,
            "preferences": {
                cat.value: {
                    k: {
                        "value": v.value,
                        "confidence": v.confidence,
                        "source": v.source,
                        "last_updated": v.last_updated.isoformat()
                    }
                    for k, v in fields.items()
                }
                for cat, fields in self.preferences.categories.items()
            },
            "interaction_history": [
                {
                    "interaction_id": h.interaction_id,
                    "timestamp": h.timestamp.isoformat(),
                    "task_type": h.task_type,
                    "outcome": h.outcome,
                    "satisfaction": h.satisfaction,
                    "tags": h.tags
                }
                for h in self.interaction_history[-100:]  # 只保留最近100条
            ],
            "response_patterns": self.response_patterns,
            "credit_score": self.credit_score,
            "total_tasks": self.total_tasks,
            "success_rate": self.success_rate,
            "updated_at": self.updated_at.isoformat()
        }
```

---

## 三、存储层设计

### 3.1 存储架构

```
┌─────────────────────────────────────────────────────────────┐
│                      应用层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │短期记忆API  │  │长期记忆API  │  │向量检索API  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Redis       │   │  PostgreSQL   │   │  向量数据库   │
│  (短期缓存)   │   │ (长期结构化)  │   │  (Qdrant/PGVector)│
│               │   │               │   │               │
│ • 会话上下文  │   │ • 用户画像    │   │ • 偏好向量    │
│ • 临时状态    │   │ • 交互历史    │   │ • 需求向量    │
│ • 实时数据    │   │ • 信用记录    │   │ • 相似度检索  │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 3.2 短期记忆存储 (Redis)

```python
# memory_storage.py

import redis
import json
from typing import Optional
from datetime import timedelta

class ShortTermMemoryStore:
    """短期记忆存储 - Redis实现"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "stm:"
        self.ttl = timedelta(hours=24)  # 24小时过期
    
    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"
    
    def save(self, memory: ShortTermMemory):
        """保存短期记忆"""
        key = self._key(memory.session_id)
        data = json.dumps(memory.to_dict())
        self.redis.setex(key, self.ttl, data)
    
    def load(self, session_id: str) -> Optional[ShortTermMemory]:
        """加载短期记忆"""
        key = self._key(session_id)
        data = self.redis.get(key)
        if data:
            return ShortTermMemory.from_dict(json.loads(data))
        return None
    
    def delete(self, session_id: str):
        """删除短期记忆"""
        key = self._key(session_id)
        self.redis.delete(key)
    
    def update_last_active(self, session_id: str):
        """更新最后活跃时间"""
        key = self._key(session_id)
        self.redis.expire(key, self.ttl)  # 重置过期时间
```

### 3.3 长期记忆存储 (PostgreSQL)

```sql
-- long_term_memory_schema.sql

-- 用户基础信息表
CREATE TABLE user_profiles (
    user_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    basic_info JSONB,  -- 基础信息（脱敏）
    preferences JSONB,  -- 偏好数据
    response_patterns JSONB,  -- 响应模式
    credit_score DECIMAL(5,2) DEFAULT 0.0,
    total_tasks INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_username (username),
    INDEX idx_credit (credit_score)
);

-- 交互历史表
CREATE TABLE interaction_history (
    interaction_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    task_type VARCHAR(32) NOT NULL,
    task_id VARCHAR(64),
    outcome VARCHAR(20) NOT NULL,
    satisfaction DECIMAL(3,2),
    tags TEXT[],
    embedding VECTOR(384),  -- 交互向量（用于相似度检索）
    details JSONB,  -- 详细数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_task_type (user_id, task_type),
    INDEX idx_created (created_at)
);

-- 偏好变更历史（用于分析和回滚）
CREATE TABLE preference_history (
    history_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    key VARCHAR(64) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    source VARCHAR(20),  -- explicit/inferred
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id),
    INDEX idx_user_category (user_id, category)
);

-- 用户自定义记忆项（用户可以主动添加的记忆）
CREATE TABLE user_memories (
    memory_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id VARCHAR(64) NOT NULL,
    memory_type VARCHAR(32) NOT NULL,  -- fact, preference, rule
    content TEXT NOT NULL,
    embedding VECTOR(384),  -- 向量化内容
    importance INTEGER DEFAULT 5,  -- 1-10
    is_private BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- 可设置过期时间
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id),
    INDEX idx_user_memories (user_id),
    INDEX idx_importance (importance)
);

-- 创建向量索引（如果使用pgvector）
CREATE INDEX idx_interaction_embedding ON interaction_history 
    USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_user_memories_embedding ON user_memories 
    USING ivfflat (embedding vector_cosine_ops);
```

### 3.4 长期记忆存储实现

```python
# long_term_storage.py

import asyncpg
import json
from typing import Optional, List
from datetime import datetime

class LongTermMemoryStore:
    """长期记忆存储 - PostgreSQL实现"""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def load_profile(self, user_id: str) -> Optional[LongTermMemory]:
        """加载用户画像"""
        async with self.pool.acquire() as conn:
            # 查询用户基本信息
            row = await conn.fetchrow(
                "SELECT * FROM user_profiles WHERE user_id = $1",
                user_id
            )
            
            if not row:
                return None
            
            memory = LongTermMemory(user_id)
            
            # 填充基础信息
            if row['basic_info']:
                memory.basic_info = UserBasicInfo(**row['basic_info'])
            
            # 填充偏好
            if row['preferences']:
                prefs_data = json.loads(row['preferences'])
                for cat_str, fields in prefs_data.items():
                    category = PreferenceCategory(cat_str)
                    for key, value_data in fields.items():
                        memory.preferences.categories[category][key] = PreferenceValue(
                            value=value_data['value'],
                            confidence=value_data['confidence'],
                            source=value_data['source'],
                            first_seen=datetime.fromisoformat(value_data['first_seen']),
                            last_updated=datetime.fromisoformat(value_data['last_updated'])
                        )
            
            # 填充其他字段
            memory.response_patterns = row['response_patterns'] or {}
            memory.credit_score = row['credit_score'] or 0.0
            memory.total_tasks = row['total_tasks'] or 0
            memory.success_rate = row['success_rate'] or 0.0
            
            # 加载最近交互历史
            history_rows = await conn.fetch(
                "SELECT * FROM interaction_history WHERE user_id = $1 ORDER BY created_at DESC LIMIT 100",
                user_id
            )
            
            for hrow in history_rows:
                memory.interaction_history.append(InteractionHistory(
                    interaction_id=hrow['interaction_id'],
                    timestamp=hrow['created_at'],
                    task_type=hrow['task_type'],
                    outcome=hrow['outcome'],
                    satisfaction=hrow['satisfaction'],
                    tags=hrow['tags'] or []
                ))
            
            return memory
    
    async def save_profile(self, memory: LongTermMemory):
        """保存用户画像"""
        async with self.pool.acquire() as conn:
            # 转换为JSON
            basic_info = memory.basic_info.dict() if memory.basic_info else None
            
            preferences = {}
            for cat, fields in memory.preferences.categories.items():
                cat_str = cat.value
                preferences[cat_str] = {}
                for key, pv in fields.items():
                    preferences[cat_str][key] = {
                        "value": pv.value,
                        "confidence": pv.confidence,
                        "source": pv.source,
                        "first_seen": pv.first_seen.isoformat(),
                        "last_updated": pv.last_updated.isoformat()
                    }
            
            # UPSERT操作
            await conn.execute("""
                INSERT INTO user_profiles (
                    user_id, username, basic_info, preferences, 
                    response_patterns, credit_score, total_tasks, 
                    success_rate, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (user_id) DO UPDATE SET
                    basic_info = EXCLUDED.basic_info,
                    preferences = EXCLUDED.preferences,
                    response_patterns = EXCLUDED.response_patterns,
                    credit_score = EXCLUDED.credit_score,
                    total_tasks = EXCLUDED.total_tasks,
                    success_rate = EXCLUDED.success_rate,
                    updated_at = EXCLUDED.updated_at
            """,
                memory.user_id,
                memory.basic_info.username if memory.basic_info else "",
                json.dumps(basic_info) if basic_info else None,
                json.dumps(preferences),
                json.dumps(memory.response_patterns),
                memory.credit_score,
                memory.total_tasks,
                memory.success_rate,
                datetime.now()
            )
    
    async def add_interaction(self, interaction: InteractionHistory):
        """添加交互记录"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO interaction_history (
                    interaction_id, user_id, task_type, task_id,
                    outcome, satisfaction, tags, embedding, details, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                interaction.interaction_id,
                interaction.user_id,
                interaction.task_type,
                interaction.task_id if hasattr(interaction, 'task_id') else None,
                interaction.outcome,
                interaction.satisfaction,
                interaction.tags,
                interaction.embedding if hasattr(interaction, 'embedding') else None,
                json.dumps(interaction.details) if hasattr(interaction, 'details') else None,
                interaction.timestamp
            )
```

---

## 四、向量检索与相似度匹配

### 4.1 向量化设计

```python
# vector_service.py

import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer

class VectorizationService:
    """向量化服务 - 将文本转换为向量"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.dimension = 384  # 模型输出维度
    
    def encode_text(self, text: str) -> List[float]:
        """将文本编码为向量"""
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    def encode_demand(self, demand: Dict[str, Any]) -> List[float]:
        """将需求编码为向量"""
        # 构建需求文本表示
        text_parts = []
        
        # 需求类型
        text_parts.append(f"需求类型: {demand.get('type', 'unknown')}")
        
        # 必填字段
        if 'values' in demand:
            for key, value in demand['values'].items():
                if isinstance(value, (str, int, float)):
                    text_parts.append(f"{key}: {value}")
                elif isinstance(value, dict):
                    for sub_k, sub_v in value.items():
                        text_parts.append(f"{key}_{sub_k}: {sub_v}")
        
        # 自定义需求
        if 'custom' in demand:
            for custom in demand['custom']:
                text_parts.append(f"自定义: {custom}")
        
        full_text = " ".join(text_parts)
        return self.encode_text(full_text)
    
    def compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        cosine = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return float(cosine)
```

### 4.2 偏好向量检索

```python
# preference_retrieval.py

from typing import List, Tuple, Optional
import asyncpg

class PreferenceRetrieval:
    """偏好检索服务 - 基于向量相似度"""
    
    def __init__(self, pool: asyncpg.Pool, vector_service: VectorizationService):
        self.pool = pool
        self.vector_service = vector_service
    
    async def find_similar_preferences(
        self, 
        user_id: str, 
        query_text: str, 
        limit: int = 10
    ) -> List[Dict]:
        """查找相似的历史偏好"""
        query_vector = self.vector_service.encode_text(query_text)
        
        async with self.pool.acquire() as conn:
            # 从user_memories表检索相似记忆
            rows = await conn.fetch("""
                SELECT 
                    memory_id,
                    content,
                    memory_type,
                    importance,
                    1 - (embedding <=> $2) AS similarity
                FROM user_memories
                WHERE user_id = $1
                ORDER BY similarity DESC
                LIMIT $3
            """, user_id, query_vector, limit)
            
            return [dict(row) for row in rows]
    
    async def find_matching_demands(
        self,
        demand_vector: List[float],
        demand_type: str,
        limit: int = 20
    ) -> List[Tuple[str, float]]:
        """查找匹配的需求"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    d.demand_id,
                    d.user_id,
                    1 - (dc.embedding <=> $1) AS similarity
                FROM demand_custom dc
                JOIN demands d ON dc.demand_id = d.demand_id
                WHERE d.type = $2 
                  AND d.status = 'matching'
                  AND dc.importance = 'high'
                ORDER BY similarity DESC
                LIMIT $3
            """, demand_vector, demand_type, limit)
            
            return [(row['demand_id'], row['similarity']) for row in rows]
```

---

## 五、记忆更新与遗忘机制

### 5.1 记忆更新策略

```python
# memory_updater.py

from datetime import datetime, timedelta
import asyncio

class MemoryUpdater:
    """记忆更新服务"""
    
    def __init__(self, short_term_store, long_term_store, vector_service):
        self.short_term = short_term_store
        self.long_term = long_term_store
        self.vector_service = vector_service
    
    async def consolidate_memory(self, session_id: str):
        """
        会话结束后，将短期记忆整合到长期记忆
        """
        # 1. 加载短期记忆
        stm = self.short_term.load(session_id)
        if not stm or not stm.user_id:
            return
        
        # 2. 加载长期记忆
        ltm = await self.long_term.load_profile(stm.user_id)
        if not ltm:
            ltm = LongTermMemory(stm.user_id)
        
        # 3. 提取有价值的记忆
        await self._extract_preferences_from_session(stm, ltm)
        await self._extract_behavior_patterns(stm, ltm)
        await self._extract_custom_memories(stm, ltm)
        
        # 4. 更新统计信息
        if stm.current_task_id:
            ltm.total_tasks += 1
        
        # 5. 保存长期记忆
        await self.long_term.save_profile(ltm)
        
        # 6. 清理短期记忆（可选）
        # self.short_term.delete(session_id)
    
    async def _extract_preferences_from_session(self, stm: ShortTermMemory, ltm: LongTermMemory):
        """从会话中提取偏好"""
        
        # 从提取的信息中获取偏好
        for key, value in stm.extracted_info.items():
            # 映射到偏好类别
            category = self._map_to_category(key)
            if category:
                ltm.preferences.set_preference(
                    category,
                    key,
                    value,
                    confidence=0.8,
                    source="explicit"  # 用户明确表达的偏好
                )
        
        # 分析对话历史，推断隐含偏好
        conversation_text = " ".join([t.message for t in stm.conversation_history if t.role == "user"])
        if len(conversation_text) > 50:
            # 这里可以用LLM分析对话，提取隐含偏好
            pass
    
    def _map_to_category(self, key: str) -> Optional[PreferenceCategory]:
        """映射字段名到偏好类别"""
        mapping = {
            "gender_preference": PreferenceCategory.DATING,
            "age_range": PreferenceCategory.DATING,
            "property_type": PreferenceCategory.RENTAL,
            "max_price": PreferenceCategory.RENTAL,
            "bedrooms": PreferenceCategory.RENTAL,
        }
        return mapping.get(key)
    
    async def _extract_custom_memories(self, stm: ShortTermMemory, ltm: LongTermMemory):
        """提取自定义记忆"""
        for custom in stm.mentioned_custom:
            # 检查是否已存在相似记忆
            vector = self.vector_service.encode_text(custom)
            
            # 这里需要实现查重逻辑
            # 如果不存在，添加到user_memories
            pass
```

### 5.2 遗忘机制

```python
# forgetting_mechanism.py

class ForgettingMechanism:
    """记忆遗忘机制 - 符合隐私法规"""
    
    def __init__(self, long_term_store):
        self.store = long_term_store
    
    async def apply_forgetting_policy(self, user_id: str, policy: Dict):
        """
        应用遗忘策略
        policy示例:
        {
            "max_age_days": 365,  # 超过1年的记忆
            "low_confidence_threshold": 0.3,  # 低置信度
            "user_requested_fields": ["location", "income"]  # 用户请求删除的字段
        }
        """
        async with self.store.pool.acquire() as conn:
            # 1. 删除过期的交互历史
            if "max_age_days" in policy:
                cutoff = datetime.now() - timedelta(days=policy["max_age_days"])
                await conn.execute("""
                    DELETE FROM interaction_history
                    WHERE user_id = $1 AND created_at < $2
                """, user_id, cutoff)
            
            # 2. 删除低置信度偏好
            if "low_confidence_threshold" in policy:
                # 需要从JSON中过滤
                threshold = policy["low_confidence_threshold"]
                # 这需要更复杂的JSON操作
                pass
            
            # 3. 删除用户请求的字段
            if "user_requested_fields" in policy:
                profile = await self.store.load_profile(user_id)
                if profile:
                    for field in policy["user_requested_fields"]:
                        # 从preferences中删除
                        for cat in profile.preferences.categories:
                            if field in profile.preferences.categories[cat]:
                                del profile.preferences.categories[cat][field]
                    
                    # 保存更新后的profile
                    await self.store.save_profile(profile)
    
    async def schedule_forgetting(self, user_id: str):
        """定期执行遗忘"""
        # 默认策略
        policy = {
            "max_age_days": 730,  # 2年
            "low_confidence_threshold": 0.2
        }
        await self.apply_forgetting_policy(user_id, policy)
```

---

## 六、隐私保护设计

### 6.1 数据脱敏

```python
# privacy.py

import hashlib
import re

class PrivacyProtector:
    """隐私保护 - 数据脱敏"""
    
    @staticmethod
    def mask_email(email: str) -> str:
        """脱敏邮箱: abc***@example.com"""
        if '@' not in email:
            return email
        local, domain = email.split('@')
        if len(local) <= 3:
            masked = local[0] + '***'
        else:
            masked = local[:2] + '***' + local[-1]
        return f"{masked}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """脱敏电话: 0412***789"""
        if len(phone) >= 8:
            return phone[:4] + '***' + phone[-3:]
        return phone
    
    @staticmethod
    def mask_address(address: str) -> str:
        """脱敏地址: 只保留区域"""
        # 简单实现：提取区域名
        suburbs = re.findall(r'([A-Z][a-z]+ (?:East|West|North|South)?)', address)
        if suburbs:
            return suburbs[0]
        return "***"
    
    @staticmethod
    def hash_id(identifier: str, salt: str = "") -> str:
        """哈希ID，用于匿名化"""
        return hashlib.sha256(f"{identifier}{salt}".encode()).hexdigest()[:16]
```

### 6.2 分享控制

```python
# sharing_control.py

from enum import Enum

class SharingLevel(str, Enum):
    """分享级别"""
    NONE = "none"  # 不分享
    BASIC = "basic"  # 基础信息（年龄范围、兴趣等）
    VERIFIED = "verified"  # 已验证信息
    FULL = "full"  # 完整信息（需用户明确同意）

class PrivacyConfig(BaseModel):
    """隐私配置"""
    user_id: str
    default_level: SharingLevel = SharingLevel.BASIC
    
    # 字段级别的分享控制
    field_sharing: Dict[str, SharingLevel] = {
        "age": SharingLevel.BASIC,
        "location": SharingLevel.BASIC,
        "occupation": SharingLevel.VERIFIED,
        "income": SharingLevel.NONE,
        "identity": SharingLevel.NONE
    }
    
    # 场景级别的分享控制
    scenario_sharing: Dict[str, SharingLevel] = {
        "dating_initial": SharingLevel.BASIC,
        "dating_after_match": SharingLevel.VERIFIED,
        "rental_application": SharingLevel.VERIFIED,
        "payment": SharingLevel.FULL
    }

class SharingController:
    """分享控制器"""
    
    def __init__(self, privacy_config: PrivacyConfig):
        self.config = privacy_config
    
    def get_shareable_info(self, 
                          requested_fields: List[str], 
                          scenario: str,
                          user_profile: Dict) -> Dict:
        """获取可分享的信息"""
        
        # 确定场景级别
        scenario_level = self.config.scenario_sharing.get(
            scenario, self.config.default_level
        )
        
        result = {}
        for field in requested_fields:
            # 检查字段级别
            field_level = self.config.field_sharing.get(
                field, self.config.default_level
            )
            
            # 取两者中更严格的级别
            actual_level = self._stricter_level(scenario_level, field_level)
            
            if actual_level == SharingLevel.NONE:
                continue
            
            if field in user_profile:
                value = user_profile[field]
                
                # 根据级别处理
                if actual_level == SharingLevel.BASIC:
                    value = self._anonymize(field, value)
                elif actual_level == SharingLevel.VERIFIED:
                    value = self._add_verification_flag(field, value)
                
                result[field] = value
        
        return result
    
    def _stricter_level(self, level1: SharingLevel, level2: SharingLevel) -> SharingLevel:
        """返回更严格的级别"""
        levels = [SharingLevel.NONE, SharingLevel.BASIC, SharingLevel.VERIFIED, SharingLevel.FULL]
        idx1 = levels.index(level1)
        idx2 = levels.index(level2)
        return levels[min(idx1, idx2)]  # 索引越小越严格
    
    def _anonymize(self, field: str, value: Any) -> Any:
        """匿名化处理"""
        if field == "age":
            # 返回年龄段
            if isinstance(value, int):
                return f"{(value//10)*10}-{(value//10)*10+9}"
        elif field == "location":
            # 只返回城市
            return PrivacyProtector.mask_address(str(value))
        return value
    
    def _add_verification_flag(self, field: str, value: Any) -> Dict:
        """添加验证标志"""
        return {
            "value": value,
            "verified": True
        }
```

---

## 七、与需求定义模块的集成

### 7.1 集成接口

```python
# memory_integration.py

class MemoryIntegration:
    """记忆模块与需求定义模块的集成接口"""
    
    def __init__(self, short_term_store, long_term_store, sharing_controller):
        self.short_term = short_term_store
        self.long_term = long_term_store
        self.sharing = sharing_controller
    
    async def prepare_for_demand_definition(self, user_id: str, session_id: str):
        """
        准备需求定义：加载记忆，预填充
        """
        # 1. 加载或创建短期记忆
        stm = self.short_term.load(session_id)
        if not stm:
            stm = ShortTermMemory(session_id)
            stm.user_id = user_id
        
        # 2. 加载长期记忆
        ltm = await self.long_term.load_profile(user_id)
        
        # 3. 从长期记忆获取预填充数据
        prefilled = {}
        if ltm:
            # 获取常用偏好
            for category in [PreferenceCategory.RENTAL, PreferenceCategory.DATING]:
                if category in ltm.preferences.categories:
                    for key, pv in ltm.preferences.categories[category].items():
                        if pv.confidence > 0.7:  # 高置信度才预填充
                            prefilled[key] = pv.value
            
            # 获取基础信息
            if ltm.basic_info:
                prefilled['location'] = ltm.basic_info.location
                prefilled['age'] = ltm.basic_info.age
        
        # 4. 保存到短期记忆
        stm.extracted_info.update(prefilled)
        self.short_term.save(stm)
        
        return {
            "session_id": session_id,
            "prefilled": prefilled,
            "user_profile_summary": {
                "has_history": ltm is not None,
                "total_tasks": ltm.total_tasks if ltm else 0
            }
        }
    
    async def update_from_demand_definition(self, session_id: str, demand_data: Dict):
        """
        需求定义完成后更新记忆
        """
        stm = self.short_term.load(session_id)
        if not stm or not stm.user_id:
            return
        
        # 将需求数据合并到短期记忆
        if 'values' in demand_data:
            stm.extracted_info.update(demand_data['values'])
        
        if 'custom' in demand_data:
            stm.mentioned_custom.extend(demand_data['custom'])
        
        self.short_term.save(stm)
        
        # 异步整合到长期记忆
        asyncio.create_task(self._consolidate_after_demand(session_id))
    
    async def _consolidate_after_demand(self, session_id: str):
        """需求定义后整合记忆"""
        # 使用MemoryUpdater
        updater = MemoryUpdater(self.short_term, self.long_term, None)
        await updater.consolidate_memory(session_id)
```

### 7.2 需求定义中的记忆使用

```python
# 在需求定义对话中使用记忆

async def handle_demand_definition_message(user_id: str, session_id: str, message: str):
    """
    处理需求定义消息，集成记忆
    """
    # 1. 获取记忆集成服务
    memory_integration = get_memory_integration()
    
    # 2. 准备记忆（如果是新会话）
    if not short_term_store.load(session_id):
        await memory_integration.prepare_for_demand_definition(user_id, session_id)
    
    # 3. 加载短期记忆
    stm = short_term_store.load(session_id)
    
    # 4. 构建带有记忆的提示词
    prompt = build_demand_prompt(
        message=message,
        prefilled=stm.extracted_info,
        user_profile=await get_user_profile_summary(user_id),
        conversation_history=stm.get_recent_context(5)
    )
    
    # 5. 调用LLM处理
    response = await call_llm(prompt)
    
    # 6. 更新短期记忆
    # ... 处理响应，提取实体等
    
    # 7. 保存更新
    short_term_store.save(stm)
    
    return response
```

---

## 八、性能优化与扩展性

### 8.1 缓存策略

```python
# cache_strategy.py

class MemoryCacheStrategy:
    """记忆缓存策略"""
    
    # 短期记忆：Redis，TTL 24小时
    SHORT_TERM_TTL = 60 * 60 * 24
    
    # 长期记忆：本地缓存 + Redis二级缓存
    LONG_TERM_LOCAL_TTL = 60 * 5  # 5分钟本地缓存
    LONG_TERM_REDIS_TTL = 60 * 30  # 30分钟Redis缓存
    
    # 热门用户画像预加载
    HOT_USER_THRESHOLD = 100  # 日活超过100次的用户
    
    @staticmethod
    async def get_user_profile_with_cache(user_id: str, redis_client, db_store):
        """带缓存的用户画像获取"""
        # 尝试Redis缓存
        cache_key = f"profile:{user_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return LongTermMemory.from_dict(json.loads(cached))
        
        # 从数据库加载
        profile = await db_store.load_profile(user_id)
        
        # 存入Redis缓存
        if profile:
            await redis_client.setex(
                cache_key, 
                MemoryCacheStrategy.LONG_TERM_REDIS_TTL,
                json.dumps(profile.to_db_document())
            )
        
        return profile
```

### 8.2 批量更新

```python
# batch_updater.py

class BatchMemoryUpdater:
    """批量记忆更新器"""
    
    def __init__(self, long_term_store, batch_size=100):
        self.store = long_term_store
        self.batch_size = batch_size
        self.pending_updates = []
    
    async def add_update(self, user_id: str, update_data: Dict):
        """添加待更新"""
        self.pending_updates.append((user_id, update_data))
        
        if len(self.pending_updates) >= self.batch_size:
            await self.flush()
    
    async def flush(self):
        """批量刷新到数据库"""
        if not self.pending_updates:
            return
        
        # 按用户分组
        updates_by_user = {}
        for user_id, data in self.pending_updates:
            if user_id not in updates_by_user:
                updates_by_user[user_id] = []
            updates_by_user[user_id].append(data)
        
        # 批量处理
        async with self.store.pool.acquire() as conn:
            async with conn.transaction():
                for user_id, updates in updates_by_user.items():
                    # 加载当前profile
                    profile = await self.store.load_profile(user_id)
                    if not profile:
                        profile = LongTermMemory(user_id)
                    
                    # 应用所有更新
                    for update in updates:
                        self._apply_update(profile, update)
                    
                    # 保存
                    await self.store.save_profile(profile)
        
        self.pending_updates.clear()
    
    def _apply_update(self, profile: LongTermMemory, update: Dict):
        """应用单个更新"""
        if 'preference' in update:
            pref = update['preference']
            profile.preferences.set_preference(
                pref['category'],
                pref['key'],
                pref['value'],
                confidence=pref.get('confidence', 0.8),
                source=pref.get('source', 'inferred')
            )
        elif 'interaction' in update:
            # 更新统计
            profile.total_tasks += 1
```

---

## 九、监控与评估

### 9.1 记忆质量指标

```python
# memory_metrics.py

class MemoryMetrics:
    """记忆模块监控指标"""
    
    def __init__(self):
        self.metrics = {
            # 短期记忆
            "short_term_hit_rate": 0.0,  # 短期记忆命中率
            "short_term_avg_size": 0,    # 平均会话大小
            
            # 长期记忆
            "long_term_hit_rate": 0.0,   # 长期记忆命中率
            "preference_confidence_avg": 0.0,  # 平均偏好置信度
            
            # 预填充
            "prefill_success_rate": 0.0,  # 预填充成功率
            "prefill_acceptance_rate": 0.0,  # 用户接受率
            
            # 性能
            "memory_load_latency_ms": 0,
            "memory_save_latency_ms": 0
        }
    
    def record_hit(self, memory_type: str, hit: bool):
        """记录命中率"""
        # 更新滑动窗口
        pass
    
    def record_prefill(self, field: str, accepted: bool):
        """记录预填充"""
        pass
    
    def get_report(self) -> Dict:
        """获取报告"""
        return self.metrics
```

---

## 十、总结

### 10.1 设计亮点

1. **分层记忆结构**：短期记忆（Redis） + 长期记忆（PostgreSQL） + 向量检索（pgvector）
2. **隐私优先**：差分隐私、分享控制、遗忘机制
3. **智能更新**：会话后自动整合，批量更新优化
4. **向量检索**：支持语义匹配的个性化需求
5. **与需求定义无缝集成**：预填充加速，个性化提升

### 10.2 与商业策划书的对应

| 商业策划书要求 | 记忆模块实现 |
|---------------|------------|
| 加速需求定义 | 预填充机制、偏好记忆 |
| 提高匹配准确度 | 向量检索、历史行为分析 |
| 个性化代理 | 用户画像、行为模式 |
| 隐私保护 | 分享控制、脱敏处理 |
| 持续运行 | 短期记忆持久化、长期记忆聚合 |

### 10.3 后续扩展

1. **跨设备同步**：记忆在Web、微信、Telegram间同步
2. **社交图谱记忆**：记录用户间的互动历史
3. **情感记忆**：记录用户情绪反应，优化交互温度
4. **联邦学习**：在保护隐私的前提下，从群体行为中学习