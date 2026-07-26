"""SQLite cache for extraction results to avoid redundant runs."""
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

CACHE_DIR = os.path.expanduser("~/.promptleak")
CACHE_DB = os.path.join(CACHE_DIR, "cache.db")
CACHE_TTL_HOURS = 24


def _ensure_db():
    os.makedirs(CACHE_DIR, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            technique TEXT NOT NULL,
            result TEXT,
            confidence REAL DEFAULT 0.0,
            timestamp TEXT NOT NULL
        )
    """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_domain_technique ON extractions(domain, technique)"
    )
    conn.commit()
    return conn


def get_cached(domain: str, technique: str) -> Optional[str]:
    conn = _ensure_db()
    cutoff = (datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)).isoformat()
    row = conn.execute(
        "SELECT result FROM extractions WHERE domain = ? AND technique = ? AND timestamp > ? ORDER BY timestamp DESC LIMIT 1",
        (domain, technique, cutoff),
    ).fetchone()
    conn.close()
    if row:
        return row[0]
    return None


def set_cached(domain: str, technique: str, result: str, confidence: float) -> None:
    conn = _ensure_db()
    conn.execute(
        "INSERT INTO extractions (url, domain, technique, result, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        ("cached", domain, technique, result, confidence, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_all_gallery_entries() -> list[dict]:
    conn = _ensure_db()
    rows = conn.execute(
        "SELECT url, domain, technique, result, confidence, timestamp FROM extractions ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "url": r[0],
            "domain": r[1],
            "technique": r[2],
            "result": r[3],
            "confidence": r[4],
            "timestamp": r[5],
        }
        for r in rows
    ]
