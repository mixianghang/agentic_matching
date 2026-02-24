# 持久化存储设计

## 1. 设计目标

### 1.1 核心目标
- **可扩展性**：支持多种数据库后端
- **可切换性**：可以轻松在不同数据库之间切换
- **向后兼容**：保持当前 API 不变
- **高性能**：支持高并发访问
- **类型安全**：使用类型提示

### 1.2 设计原则
- **接口优先**：先定义抽象接口，再实现具体存储
- **依赖注入**：通过配置选择具体实现
- **最小改动**：最小化对现有代码的修改
- **单一职责**：每个存储实现只负责自己的功能

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      应用层 (main.py, agent_system.py)       │
│                        使用统一的 Storage 接口                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 抽象层 (storage_interface.py)                │
│           StorageBackend 接口 - 定义统一的方法签名            │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ InMemory      │  │ SQLite        │  │ PostgreSQL    │
│ Storage       │  │ Storage       │  │ Storage       │
│ (开发/测试)   │  │ (开发环境)    │  │ (生产环境)    │
└───────────────┘  └───────────────┘  └───────────────┘
```

### 2.2 目录结构

```
backend/
├── __init__.py
├── models.py
├── storage_interface.py     # 新增：抽象接口定义
├── storage.py               # 修改：统一的存储访问点
├── storage_sqlite.py        # 新增：SQLite 实现
├── storage_postgres.py      # 新增：PostgreSQL 实现
├── agent_system.py
├── config.py
└── main.py
```

## 3. 抽象接口设计

### 3.1 StorageBackend 接口

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from backend.models import User, Agent, Task, Message

class StorageBackend(ABC):
    """
    存储后端抽象接口
    所有存储实现都必须实现这个接口
    """
    
    @abstractmethod
    def create_user(self, username: str, email: Optional[str] = None) -> User:
        """创建用户"""
        pass
    
    @abstractmethod
    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
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
    def initialize(self) -> None:
        """初始化存储后端（创建表、连接等）"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭存储后端（关闭连接等）"""
        pass
```

### 3.2 存储工厂

```python
from typing import Type
from backend.config import settings

def get_storage_backend() -> StorageBackend:
    """
    根据配置获取存储后端实例
    
    配置说明：
    - STORAGE_TYPE: "in_memory", "sqlite", "postgresql"
    """
    storage_type = settings.STORAGE_TYPE
    
    if storage_type == "in_memory":
        from backend.storage import InMemoryStorage
        return InMemoryStorage()
    elif storage_type == "sqlite":
        from backend.storage_sqlite import SQLiteStorage
        return SQLiteStorage(settings.DATABASE_URL)
    elif storage_type == "postgresql":
        from backend.storage_postgres import PostgreSQLStorage
        return PostgreSQLStorage(settings.DATABASE_URL)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
```

## 4. 数据库设计

### 4.1 数据库选择

| 数据库 | 使用场景 | 优势 | 劣势 |
|--------|---------|------|------|
| **InMemory** | 开发/快速原型 | 零配置，超快 | 数据不持久化 |
| **SQLite** | 开发/小型部署 | 零配置，文件存储 | 并发性能有限 |
| **PostgreSQL** | 生产环境 | 高性能，功能丰富 | 需要配置和维护 |

### 4.2 SQLite 数据库模式

```sql
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    preferences TEXT,  -- JSON
    private_info TEXT  -- JSON
);

-- 智能体表
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 任务表
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT,  -- JSON
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    matched_task_ids TEXT,  -- JSON array
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 消息表
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    receiver_id TEXT,
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id);
CREATE INDEX IF NOT EXISTS idx_agents_user_id ON agents(user_id);
```

### 4.3 PostgreSQL 数据库模式

```sql
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    preferences JSONB,
    private_info JSONB
);

-- 智能体表
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 任务表
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    requirements JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    matched_task_ids UUID[],
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 消息表
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL,
    sender_id TEXT NOT NULL,
    receiver_id TEXT,
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id);
CREATE INDEX IF NOT EXISTS idx_agents_user_id ON agents(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
```

## 5. 配置管理

### 5.1 配置项

在 `backend/config.py` 中添加：

```python
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # 存储配置
    STORAGE_TYPE: str = "in_memory"  # "in_memory", "sqlite", "postgresql"
    DATABASE_URL: str = "sqlite:///./agentic_matching.db"
    
    # PostgreSQL 配置（可选）
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "agentic_matching"
```

### 5.2 .env 示例

```env
# 存储配置
STORAGE_TYPE=sqlite
DATABASE_URL=sqlite:///./agentic_matching.db

# PostgreSQL 配置（如果使用 PostgreSQL）
# STORAGE_TYPE=postgresql
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_USER=postgres
# POSTGRES_PASSWORD=your_password
# POSTGRES_DB=agentic_matching
```

## 6. 实现计划

### 6.1 阶段 1：接口定义和重构（1天）
- [ ] 创建 `storage_interface.py` 定义抽象接口
- [ ] 重构 `storage.py` 中的 `InMemoryStorage` 实现接口
- [ ] 创建存储工厂函数
- [ ] 更新 `main.py` 和 `agent_system.py` 使用新的存储接口

### 6.2 阶段 2：SQLite 实现（2天）
- [ ] 创建 `storage_sqlite.py`
- [ ] 实现 SQLite 存储后端
- [ ] 实现数据库初始化和迁移
- [ ] 编写单元测试

### 6.3 阶段 3：PostgreSQL 实现（2天）
- [ ] 创建 `storage_postgres.py`
- [ ] 实现 PostgreSQL 存储后端
- [ ] 添加 SQLAlchemy 或 asyncpg 依赖
- [ ] 编写单元测试

### 6.4 阶段 4：测试和优化（1天）
- [ ] 集成测试
- [ ] 性能测试
- [ ] 文档完善
- [ ] 代码审查

## 7. 依赖管理

### 7.1 requirements.txt 更新

```txt
# 现有依赖
fastapi>=0.100.0
uvicorn>=0.20.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
openai>=1.0.0
python-dotenv>=1.0.0

# 新增：数据库依赖
# SQLite（内置，无需额外依赖）

# PostgreSQL（可选）
# psycopg2-binary>=2.9.0
# 或者
# asyncpg>=0.27.0
# sqlalchemy>=2.0.0
```

## 8. 迁移策略

### 8.1 从 InMemory 迁移到 SQLite
- 自动：首次运行 SQLite 存储时，自动创建数据库
- 手动：提供数据导出/导入脚本

### 8.2 从 SQLite 迁移到 PostgreSQL
- 使用 `pgloader` 或 `pg_dump`/`pg_restore`
- 提供迁移脚本

## 9. 测试策略

### 9.1 单元测试
- 测试每个存储方法
- 使用 pytest 和内存数据库
- 测试数据完整性

### 9.2 集成测试
- 测试完整的 CRUD 操作
- 测试并发访问
- 测试数据一致性

## 10. 监控和运维

### 10.1 健康检查
- 数据库连接状态
- 查询性能监控
- 连接池状态

### 10.2 备份策略
- SQLite：定期备份数据库文件
- PostgreSQL：使用 pg_dump 或 WAL 归档

## 11. 扩展性设计

### 11.1 未来可能的存储后端
- MongoDB（文档数据库）
- Redis（缓存 + 持久化）
- CockroachDB（分布式 SQL）
- Firebase（云存储）

### 11.2 添加新存储后端的步骤
1. 创建新的存储类实现 `StorageBackend` 接口
2. 在 `get_storage_backend()` 工厂函数中添加新类型
3. 更新配置文档
4. 编写测试

## 12. 风险评估

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| 性能问题 | 高 | 中 | 使用索引、缓存、连接池 |
| 数据丢失 | 高 | 低 | 定期备份、事务、WAL |
| 迁移复杂 | 中 | 低 | 提供迁移工具和文档 |
| 依赖冲突 | 中 | 中 | 使用虚拟环境、版本锁定 |

---

**文档版本**：1.0  
**创建日期**：2026-02-24  
**作者**：系统设计团队
