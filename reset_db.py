#!/usr/bin/env python3
import os
import sqlite3

DB_FILE = "agentic_matching.db"

def reset_database():
    if os.path.exists(DB_FILE):
        print(f"🗑️  删除旧数据库: {DB_FILE}")
        os.remove(DB_FILE)
    else:
        print("📝 数据库文件不存在，将创建新数据库")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("📋 创建表: users")
    cursor.execute("""
        CREATE TABLE users (
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

    print("📋 创建表: agents")
    cursor.execute("""
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    print("📋 创建表: tasks")
    cursor.execute("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            requirements TEXT,
            matched_task_ids TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)

    print("📋 创建表: messages")
    cursor.execute("""
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            receiver_id TEXT,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_public INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)

    print("📋 创建表: tokens")
    cursor.execute("""
        CREATE TABLE tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    print("📇 创建索引...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_user_id ON agents(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens(token)")

    conn.commit()
    conn.close()

    print("✅ 数据库初始化完成!")

if __name__ == "__main__":
    reset_database()
