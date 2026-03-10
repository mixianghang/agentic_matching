#!/usr/bin/env python3
import argparse
import sqlite3

def cleanup_tasks(db_path: str, include_messages: bool, vacuum: bool) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]

        message_count = 0
        if include_messages:
            cursor.execute("SELECT COUNT(*) FROM messages")
            message_count = cursor.fetchone()[0]

        if include_messages:
            cursor.execute("DELETE FROM messages")
        cursor.execute("DELETE FROM tasks")
        conn.commit()

        if vacuum:
            cursor.execute("VACUUM")

        print(f"Deleted {task_count} tasks")
        if include_messages:
            print(f"Deleted {message_count} messages")
        if vacuum:
            print("Database vacuumed")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean tasks in the SQLite database.")
    parser.add_argument("--db-path", default="./agentic_matching.db", help="Path to the SQLite database file")
    parser.add_argument("--keep-messages", action="store_true", help="Keep messages when deleting tasks")
    parser.add_argument("--vacuum", action="store_true", help="Run VACUUM after deleting tasks")
    args = parser.parse_args()

    cleanup_tasks(args.db_path, include_messages=not args.keep_messages, vacuum=args.vacuum)


if __name__ == "__main__":
    main()
