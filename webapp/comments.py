"""
SQLite tabanli yorum sistemi.
Veritabani: /opt/wood-sculpture-slicer/data/comments.db (production)
            ./data/comments.db (lokal)
"""
import sqlite3
import os
from datetime import datetime
from pathlib import Path


def _db_path() -> str:
    """Veritabani dosya yolu."""
    base = Path(__file__).resolve().parent.parent
    data_dir = base / 'data'
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / 'comments.db')


def get_connection():
    """SQLite baglantisi ac."""
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row  # dict-like erisim
    return conn


def init_db():
    """Tabloyu olustur (yoksa)."""
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT,
            comment   TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def save_comment(name: str, comment: str) -> dict:
    """
    Yeni yorum kaydet.
    Returns: kaydedilen yorum dict olarak
    """
    name = (name or '').strip()[:100]       # max 100 karakter
    comment = (comment or '').strip()[:2000] # max 2000 karakter

    if not comment:
        raise ValueError("Comment cannot be empty")

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    cur = conn.execute(
        'INSERT INTO comments (name, comment, created_at) VALUES (?, ?, ?)',
        (name or None, comment, now)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()

    return {
        'id': row_id,
        'name': name or 'Anonymous',
        'comment': comment,
        'created_at': now,
    }


def get_comments(limit: int = 50, offset: int = 0) -> list:
    """
    Yorumlari listele (en yeniden eskiye).
    """
    conn = get_connection()
    rows = conn.execute(
        'SELECT id, name, comment, created_at FROM comments '
        'ORDER BY id DESC LIMIT ? OFFSET ?',
        (limit, offset)
    ).fetchall()
    conn.close()

    return [
        {
            'id': r['id'],
            'name': r['name'] or 'Anonymous',
            'comment': r['comment'],
            'created_at': r['created_at'],
        }
        for r in rows
    ]


def get_comment_count() -> int:
    """Toplam yorum sayisi."""
    conn = get_connection()
    count = conn.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
    conn.close()
    return count