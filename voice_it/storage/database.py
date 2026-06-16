"""
Voice IT - Database Manager
SQLite database for storing transcription history.
"""

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

from voice_it.storage.config import get_config


class Database:
    """
    SQLite database manager for Voice IT.
    Stores transcription history.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the database.

        Args:
            db_path: Path to the database file (uses config default if not provided)
        """
        if db_path is None:
            db_path = get_config().database_path

        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        # The connection is shared across threads (check_same_thread=False),
        # so every access must be serialized through this lock.
        self._lock = threading.Lock()

        # Initialize database
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _init_db(self):
        """Initialize database tables."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # History table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    raw_text TEXT,
                    mode TEXT DEFAULT 'dictation',
                    app_name TEXT,
                    provider TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    # ========== History Methods ==========

    def add_history(
        self,
        text: str,
        raw_text: Optional[str] = None,
        mode: str = "dictation",
        app_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> int:
        """
        Add a new history entry.

        Returns:
            The ID of the new entry
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO history (text, raw_text, mode, app_name, provider)
                VALUES (?, ?, ?, ?, ?)
                """,
                (text, raw_text, mode, app_name, provider),
            )
            conn.commit()

            return cursor.lastrowid

    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get history entries.

        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip
            search: Optional search term

        Returns:
            List of history entries
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            if search:
                cursor.execute(
                    """
                    SELECT * FROM history
                    WHERE text LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (f"%{search}%", limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM history
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            return [dict(row) for row in cursor.fetchall()]

    def delete_history(self, entry_id: int) -> bool:
        """Delete a history entry."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()

            return cursor.rowcount > 0

    def clear_history(self) -> int:
        """Clear all history entries. Returns number of deleted entries."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM history")
            conn.commit()

            return cursor.rowcount

    def get_dictionary_for_prompt(self) -> Optional[str]:
        """
        Get custom dictionary entries formatted for transcription prompt.

        Returns:
            Formatted dictionary string or None if no entries exist.

        Note: Dictionary feature not yet implemented. Returns None.
        """
        # TODO: Implement dictionary table and retrieval
        # For now, return None to indicate no custom dictionary
        return None

    def close(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global database instance
_database: Optional[Database] = None


def get_database() -> Database:
    """Get the global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database
