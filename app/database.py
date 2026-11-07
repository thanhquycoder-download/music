import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings

_db_initialized = False

def init_db():
    """Khởi tạo database và bảng songs nếu chưa có."""
    global _db_initialized
    db_file = Path(settings.DATABASE_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS songs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        artist TEXT DEFAULT 'Unknown Artist',
        duration INTEGER NOT NULL DEFAULT 0,
        audio_url TEXT NOT NULL,
        cover_url TEXT,
        source_type TEXT NOT NULL,
        original_url TEXT NOT NULL,
        search_keywords TEXT,
        lyrics TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    try:
        cursor.execute("ALTER TABLE songs ADD COLUMN lyrics TEXT;")
    except sqlite3.OperationalError:
        pass  # Column already exists
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_songs_search_keywords ON songs(search_keywords);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_songs_created_at ON songs(created_at DESC);")
    conn.commit()
    conn.close()
    _db_initialized = True

def get_connection() -> sqlite3.Connection:
    global _db_initialized
    if not _db_initialized:
        init_db()
    conn = sqlite3.connect(settings.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
