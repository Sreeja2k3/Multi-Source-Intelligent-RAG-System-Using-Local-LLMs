# src/database/db_manager.py
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger
from src.config import settings

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or getattr(settings, "DB_PATH", "./data/rag_system.db")
        # Fallback if DB_PATH not loaded yet from config
        if not self.db_path or self.db_path == "./data/chroma_db":
            self.db_path = "./data/rag_system.db"
            
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def _get_connection(self):
        """Returns a sqlite3 connection with dict-like row factory."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes tables if they do not exist."""
        logger.info(f"Initializing SQLite database at: {self.db_path}")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    feedback TEXT, -- 'up', 'down', or NULL
                    response_time REAL DEFAULT 0.0,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)
            
            # Sources table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    file_name TEXT,
                    url TEXT,
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
                )
            """)
            
            # Ingestion logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL, -- 'success', 'failed'
                    error_message TEXT,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logger.success("SQLite database initialized successfully.")

    # ── Conversation CRUD ───────────────────────────────────────────────────────

    def create_conversation(self, conv_id: str, title: str = "New Chat") -> bool:
        """Create a new conversation log."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO conversations (id, title) VALUES (?, ?)",
                    (conv_id, title)
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_conversation_title(self, conv_id: str, title: str) -> bool:
        """Update conversation title."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (title, conv_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations sorted by creation date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, created_at FROM conversations ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and all cascading dependencies."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # SQLite does cascade deletes if pragmas are configured, but manual cascade is safer
            cursor.execute("DELETE FROM sources WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = ?)", (conv_id,))
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ── Messages & Sources CRUD ─────────────────────────────────────────────────

    def add_message(self, conv_id: str, role: str, content: str, response_time: float = 0.0) -> int:
        """Add a message to a conversation. Returns the new message ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content, response_time) VALUES (?, ?, ?, ?)",
                (conv_id, role, content, response_time)
            )
            message_id = cursor.lastrowid
            
            # Auto-update conversation title if it's the first human message
            cursor.execute("SELECT COUNT(*) as count FROM messages WHERE conversation_id = ? AND role = 'user'", (conv_id,))
            if cursor.fetchone()["count"] == 1 and role == "user":
                title = content.strip()
                if len(title) > 40:
                    title = title[:37] + "..."
                cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
                
            conn.commit()
            return message_id

    def add_source(self, message_id: int, source_type: str, file_name: Optional[str] = None, url: Optional[str] = None):
        """Link a document source chunk reference to an assistant message."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sources (message_id, source_type, file_name, url) VALUES (?, ?, ?, ?)",
                (message_id, source_type, file_name, url)
            )
            conn.commit()

    def get_conversation_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        """Fetch all messages for a conversation, attaching sources to assistant replies."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, role, content, created_at, feedback, response_time FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conv_id,)
            )
            messages = [dict(r) for r in cursor.fetchall()]
            
            # Attach sources to assistant messages
            for msg in messages:
                if msg["role"] == "assistant":
                    cursor.execute(
                        "SELECT source_type, file_name, url FROM sources WHERE message_id = ?",
                        (msg["id"],)
                    )
                    msg["sources"] = [dict(s) for s in cursor.fetchall()]
                else:
                    msg["sources"] = []
            return messages

    def set_message_feedback(self, message_id: int, feedback: Optional[str]) -> bool:
        """Rate an assistant response ('up', 'down', or None)."""
        if feedback not in (None, "up", "down"):
            raise ValueError("Feedback must be 'up', 'down', or None")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE messages SET feedback = ? WHERE id = ?",
                (feedback, message_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    # ── Ingestion Logs ──────────────────────────────────────────────────────────

    def log_ingestion(self, file_name: str, source_type: str, file_size: int = 0, chunk_count: int = 0, status: str = "success", error_message: Optional[str] = None) -> int:
        """Create a history record for document ingestion."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO ingestion_logs (file_name, source_type, file_size, chunk_count, status, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (file_name, source_type, file_size, chunk_count, status, error_message)
            )
            conn.commit()
            return cursor.lastrowid

    def get_ingestion_logs(self) -> List[Dict[str, Any]]:
        """Retrieve all ingestion history log rows."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, file_name, source_type, file_size, chunk_count, status, error_message, ingested_at FROM ingestion_logs ORDER BY ingested_at DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_system_stats(self) -> Dict[str, Any]:
        """Retrieve telemetry metrics for the dashboard status card."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM conversations")
            convs = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM messages")
            msgs = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM messages WHERE feedback = 'up'")
            upvotes = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM messages WHERE feedback = 'down'")
            downvotes = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM ingestion_logs WHERE status = 'success'")
            success_files = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(*) as count FROM ingestion_logs WHERE status = 'failed'")
            failed_files = cursor.fetchone()["count"]
            
            return {
                "conversations_count": convs,
                "messages_count": msgs,
                "upvotes": upvotes,
                "downvotes": downvotes,
                "success_files": success_files,
                "failed_files": failed_files
            }
