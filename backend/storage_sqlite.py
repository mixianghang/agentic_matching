import sqlite3
import json
import uuid
import threading
from functools import wraps
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from backend.models import User, Agent, Task, Message, TaskStatus, Token
from backend.storage_interface import StorageBackend


def with_lock(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        acquired = self._lock.acquire(timeout=5)
        if not acquired:
            print(f"WARNING: Lock timeout for {func.__name__}")
            raise Exception(f"Lock timeout for {func.__name__}")
        try:
            return func(self, *args, **kwargs)
        finally:
            self._lock.release()
    return wrapper


class SQLiteStorage(StorageBackend):
    def __init__(self, db_path: str = "agentic_matching.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
    
    def _get_connection(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    @with_lock
    def initialize(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
                password_hash TEXT,
                auth_provider TEXT,
                third_party_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                preferences TEXT,
                private_info TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                description TEXT NOT NULL,
                requirements TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                matched_task_ids TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                receiver_id TEXT,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                is_public INTEGER NOT NULL DEFAULT 0,
                message_type TEXT NOT NULL DEFAULT 'agent',
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)

        cursor.execute("PRAGMA table_info(messages)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'message_type' not in columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'agent'")

        # Add metadata column to tasks if missing (migration)
        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = [row['name'] for row in cursor.fetchall()]
        if 'metadata' not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN metadata TEXT")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_user_id ON agents(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_third_party_unique ON users(auth_provider, third_party_id) WHERE auth_provider IS NOT NULL AND third_party_id IS NOT NULL")
        
        conn.commit()
    
    @with_lock
    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _row_to_user(self, row) -> User:
        return User(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            password_hash=row['password_hash'],
            auth_provider=row['auth_provider'],
            third_party_id=row['third_party_id'],
            is_active=bool(row['is_active']) if 'is_active' in row and row['is_active'] is not None else True,
            created_at=datetime.fromisoformat(row['created_at']),
            preferences=json.loads(row['preferences']) if row['preferences'] else {},
            private_info=json.loads(row['private_info']) if row['private_info'] else {}
        )
    
    def _row_to_agent(self, row) -> Agent:
        return Agent(
            id=row['id'],
            user_id=row['user_id'],
            role=row['role'],
            created_at=datetime.fromisoformat(row['created_at']),
            active=bool(row['active'])
        )
    
    def _row_to_message(self, row) -> Message:
        message_type = row['message_type'] if 'message_type' in row.keys() else 'agent'
        return Message(
            id=row['id'],
            sender_id=row['sender_id'],
            receiver_id=row['receiver_id'],
            content=row['content'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            is_public=bool(row['is_public']),
            message_type=message_type
        )
    
    @with_lock
    def create_user(self, username: str, email: Optional[str] = None, 
                   password_hash: Optional[str] = None,
                   auth_provider: Optional[str] = None,
                   third_party_id: Optional[str] = None,
                   is_active: bool = True) -> User:
        user_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO users (id, username, email, password_hash, auth_provider, third_party_id, is_active, created_at, preferences, private_info) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, email, password_hash, auth_provider, third_party_id, 1 if is_active else 0, created_at, '{}', '{}')
        )
        conn.commit()
        
        return User(
            id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            auth_provider=auth_provider,
            third_party_id=third_party_id,
            is_active=is_active,
            created_at=datetime.fromisoformat(created_at),
            preferences={},
            private_info={}
        )
    
    def get_user(self, user_id: str) -> Optional[User]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_user(row)
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_user(row)
        return None
    
    def get_user_by_third_party_id(self, auth_provider: str, third_party_id: str) -> Optional[User]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE auth_provider = ? AND third_party_id = ?",
            (auth_provider, third_party_id)
        )
        row = cursor.fetchone()
        
        if row:
            return self._row_to_user(row)
        return None
    
    @with_lock
    def update_user(self, user: User) -> User:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET username = ?, email = ?, password_hash = ?, auth_provider = ?, third_party_id = ?, preferences = ?, private_info = ? WHERE id = ?",
            (user.username, user.email, user.password_hash, user.auth_provider, user.third_party_id,
             json.dumps(user.preferences), json.dumps(user.private_info), user.id)
        )
        conn.commit()
        return user
    
    def get_all_users(self) -> List[User]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        return [self._row_to_user(row) for row in rows]
    
    @with_lock
    def create_agent(self, user_id: str, role: str) -> Agent:
        agent_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO agents (id, user_id, role, created_at, active) VALUES (?, ?, ?, ?, ?)",
            (agent_id, user_id, role, created_at, 1)
        )
        conn.commit()
        
        return Agent(
            id=agent_id,
            user_id=user_id,
            role=role,
            created_at=datetime.fromisoformat(created_at),
            active=True
        )
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_agent(row)
        return None
    
    def get_agents_by_user(self, user_id: str) -> List[Agent]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return [self._row_to_agent(row) for row in rows]
    
    def _row_to_task(self, row, include_messages: bool = True) -> Task:
        row_keys = row.keys()
        task = Task(
            id=row['id'],
            user_id=row['user_id'],
            agent_id=row['agent_id'],
            task_type=row['task_type'],
            description=row['description'],
            requirements=json.loads(row['requirements']) if row['requirements'] else {},
            status=TaskStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']),
            matched_task_ids=json.loads(row['matched_task_ids']) if row['matched_task_ids'] else [],
            metadata=json.loads(row['metadata']) if 'metadata' in row_keys and row['metadata'] else {},
            messages=[]
        )

        if include_messages:
            # 延迟加载消息，避免在锁内调用另一个需要锁的方法
            pass

        return task
    
    @with_lock
    def create_task(self, user_id: str, agent_id: str, task_type: str, 
                   description: str, requirements: Dict = None) -> Task:
        task_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO tasks (id, user_id, agent_id, task_type, description, requirements, status, matched_task_ids, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, user_id, agent_id, task_type, description, 
             json.dumps(requirements or {}), 'pending', '[]', created_at, created_at)
        )
        conn.commit()
        
        return Task(
            id=task_id,
            user_id=user_id,
            agent_id=agent_id,
            task_type=task_type,
            description=description,
            requirements=requirements or {},
            status=TaskStatus.PENDING,
            created_at=datetime.fromisoformat(created_at),
            matched_task_ids=[],
            messages=[]
        )
    
    @with_lock
    def get_task(self, task_id: str) -> Optional[Task]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        if row:
            task = self._row_to_task(row, include_messages=False)
            # 在锁内加载消息（使用内部方法避免死锁）
            task.messages = self._get_messages_by_task_internal(task.id)
            return task
        return None
    
    def get_tasks_by_user(self, user_id: str) -> List[Task]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return [self._row_to_task(row, include_messages=False) for row in rows]
    
    def get_all_tasks(self) -> List[Task]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks")
        rows = cursor.fetchall()
        return [self._row_to_task(row, include_messages=False) for row in rows]
    
    @with_lock
    def update_task(self, task: Task) -> Task:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE tasks SET user_id = ?, agent_id = ?, task_type = ?, description = ?, 
               requirements = ?, status = ?, matched_task_ids = ?, metadata = ? WHERE id = ?""",
            (task.user_id, task.agent_id, task.task_type, task.description,
             json.dumps(task.requirements), task.status.value,
             json.dumps(task.matched_task_ids),
             json.dumps(task.metadata) if task.metadata else None,
             task.id)
        )
        conn.commit()
        return task
    
    @with_lock
    def delete_task(self, task_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return True
    
    @with_lock
    def add_message_to_task(self, task_id: str, message: Message) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages (id, task_id, sender_id, receiver_id, content, timestamp, is_public, message_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (message.id, task_id, message.sender_id, message.receiver_id,
             message.content, message.timestamp.isoformat(), int(message.is_public), message.message_type)
        )
        conn.commit()
    
    def _get_messages_by_task_internal(self, task_id: str) -> List[Message]:
        """内部方法：获取任务消息（不获取锁，假设调用者已持有锁）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE task_id = ? ORDER BY timestamp", (task_id,))
        rows = cursor.fetchall()
        return [self._row_to_message(row) for row in rows]

    @with_lock
    def get_messages_by_task(self, task_id: str) -> List[Message]:
        """公共方法：获取任务消息（带锁）"""
        return self._get_messages_by_task_internal(task_id)
    
    def _row_to_token(self, row) -> Token:
        return Token(
            id=row['id'],
            user_id=row['user_id'],
            token=row['token'],
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']),
            revoked=bool(row['revoked'])
        )
    
    @with_lock
    def create_token(self, user_id: str, token: str, expires_in_hours: int = 24) -> Token:
        token_id = str(uuid.uuid4())
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=expires_in_hours)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tokens (id, user_id, token, created_at, expires_at, revoked) VALUES (?, ?, ?, ?, ?, ?)",
            (token_id, user_id, token, created_at.isoformat(), expires_at.isoformat(), 0)
        )
        conn.commit()
        
        return Token(
            id=token_id,
            user_id=user_id,
            token=token,
            created_at=created_at,
            expires_at=expires_at,
            revoked=False
        )
    
    def get_token(self, token: str) -> Optional[Token]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tokens WHERE token = ?", (token,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_token(row)
        return None
    
    @with_lock
    def verify_token(self, token: str) -> Optional[User]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tokens WHERE token = ?", (token,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        if row['revoked']:
            return None
        
        expires_at = datetime.fromisoformat(row['expires_at'])
        if datetime.now() > expires_at:
            return None
        
        return self.get_user(row['user_id'])
    
    @with_lock
    def revoke_token(self, token: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tokens SET revoked = 1 WHERE token = ?", (token,))
        conn.commit()
        return cursor.rowcount > 0
