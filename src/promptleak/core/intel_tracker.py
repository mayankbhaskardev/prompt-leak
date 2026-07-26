"""Competitor intelligence tracker — track prompt changes over time with SQLite DB."""
import difflib
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

logger = logging.getLogger("promptleak")

INTEL_DIR = os.path.expanduser("~/.promptleak/intel")
INTEL_DB = os.path.join(INTEL_DIR, "intel.db")


def _ensure_db(db_path=None):
    if db_path:
        d = os.path.dirname(os.path.abspath(db_path))
        if d:
            os.makedirs(d, exist_ok=True)
        conn = sqlite3.connect(db_path)
    else:
        os.makedirs(INTEL_DIR, exist_ok=True)
        conn = sqlite3.connect(INTEL_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_scanned TEXT,
            scan_count INTEGER DEFAULT 0,
            total_leaks INTEGER DEFAULT 0,
            model_fingerprint TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            prompt_hash TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            technique TEXT,
            captured_at TEXT NOT NULL,
            FOREIGN KEY (target_id) REFERENCES targets(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompt_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            old_snapshot_id INTEGER NOT NULL,
            new_snapshot_id INTEGER NOT NULL,
            detected_at TEXT NOT NULL,
            change_type TEXT NOT NULL,
            change_summary TEXT,
            diff_text TEXT,
            similarity_score REAL,
            FOREIGN KEY (target_id) REFERENCES targets(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS extra_data (
            target_id INTEGER PRIMARY KEY,
            scan_history TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (target_id) REFERENCES targets(id)
        )
    """)
    conn.commit()
    return conn


class IntelTracker:
    """Track how system prompts change over time across targets."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path

    def _conn(self):
        return _ensure_db(self._db_path)

    def record_scan(self, domain: str, url: str, prompt_text: str,
                    confidence: float = 0.0, technique: str = "",
                    model_fingerprint: Optional[str] = None) -> dict:
        """Record a scan result and detect changes."""
        conn = self._conn()
        now = datetime.now().isoformat()
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()

        cursor = conn.execute("SELECT id, domain, last_scanned, scan_count, total_leaks, model_fingerprint FROM targets WHERE domain = ?", (domain,))
        row = cursor.fetchone()

        if row:
            target_id = row[0]
            if model_fingerprint:
                conn.execute("UPDATE targets SET last_scanned = ?, scan_count = scan_count + 1, model_fingerprint = ? WHERE id = ?",
                             (now, model_fingerprint, target_id))
            else:
                conn.execute("UPDATE targets SET last_scanned = ?, scan_count = scan_count + 1 WHERE id = ?",
                             (now, target_id))
        else:
            cursor = conn.execute(
                "INSERT INTO targets (domain, url, first_seen, last_scanned, scan_count, model_fingerprint) VALUES (?, ?, ?, ?, 1, ?)",
                (domain, url, now, now, model_fingerprint or ""),
            )
            target_id = cursor.lastrowid

        cursor = conn.execute(
            "INSERT INTO snapshots (target_id, prompt_hash, prompt_text, confidence, technique, captured_at) VALUES (?, ?, ?, ?, ?, ?)",
            (target_id, prompt_hash, prompt_text, confidence, technique, now),
        )
        new_snapshot_id = cursor.lastrowid
        conn.commit()

        change_result = None
        cursor = conn.execute(
            "SELECT id, prompt_hash, prompt_text, captured_at FROM snapshots WHERE target_id = ? AND id < ? ORDER BY id DESC LIMIT 1",
            (target_id, new_snapshot_id),
        )
        prev = cursor.fetchone()

        if prev and prev[1] != prompt_hash:
            old_text = prev[2]
            similarity = difflib.SequenceMatcher(None, old_text, prompt_text).ratio()

            if similarity < 0.3:
                change_type = "REWRITTEN"
            elif similarity < 0.7:
                change_type = "MODIFIED"
            else:
                change_type = "MINOR_TWEAK"

            differ = difflib.unified_diff(
                old_text.splitlines(keepends=True),
                prompt_text.splitlines(keepends=True),
                fromfile="old", tofile="new",
            )
            diff_text = "".join(differ)
            added = sum(1 for line in diff_text.split("\n") if line.startswith("+") and not line.startswith("+++"))
            removed = sum(1 for line in diff_text.split("\n") if line.startswith("-") and not line.startswith("---"))
            summary = f"+{added} lines, -{removed} lines ({similarity:.0%} similarity)"

            c = conn.execute(
                "INSERT INTO prompt_changes (target_id, old_snapshot_id, new_snapshot_id, detected_at, change_type, change_summary, diff_text, similarity_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (target_id, prev[0], new_snapshot_id, now, change_type, summary, diff_text[:5000], similarity),
            )
            change_id = c.lastrowid
            conn.commit()

            change_result = {
                "change_id": change_id,
                "change_type": change_type,
                "summary": summary,
                "similarity": round(similarity, 3),
                "diff": diff_text[:2000],
                "old_timestamp": prev[3],
                "new_timestamp": now,
            }

        conn.close()
        return {"change": change_result, "target_id": target_id, "snapshot_id": new_snapshot_id}

    def get_timeline(self, domain: str) -> list[dict]:
        """Get full change timeline for a target."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT pc.id, pc.change_type, pc.change_summary, pc.similarity_score, pc.detected_at,
                   s1.prompt_text as old_text, s2.prompt_text as new_text
            FROM prompt_changes pc
            JOIN targets t ON pc.target_id = t.id
            JOIN snapshots s1 ON pc.old_snapshot_id = s1.id
            JOIN snapshots s2 ON pc.new_snapshot_id = s2.id
            WHERE t.domain = ?
            ORDER BY pc.detected_at DESC
        """, (domain,)).fetchall()
        conn.close()
        return [
            {"id": r[0], "type": r[1], "summary": r[2], "similarity": r[3], "detected_at": r[4],
             "old_preview": r[5][:200], "new_preview": r[6][:200]}
            for r in rows
        ]

    def get_leaderboard(self, metric: str = "most_changes") -> list[dict]:
        """Rank targets by various metrics."""
        conn = self._conn()
        metrics = {
            "most_changes": """
                SELECT t.domain, COUNT(pc.id) as val FROM prompt_changes pc
                JOIN targets t ON pc.target_id = t.id
                GROUP BY t.domain ORDER BY val DESC LIMIT 20
            """,
            "most_leaky": """
                SELECT domain, total_leaks as val FROM targets
                WHERE total_leaks > 0 ORDER BY val DESC LIMIT 20
            """,
            "most_scanned": """
                SELECT domain, scan_count as val FROM targets
                ORDER BY val DESC LIMIT 20
            """,
            "recently_changed": """
                SELECT t.domain, pc.detected_at as val FROM prompt_changes pc
                JOIN targets t ON pc.target_id = t.id
                ORDER BY pc.detected_at DESC LIMIT 20
            """,
        }
        sql = metrics.get(metric, metrics["most_changes"])
        rows = conn.execute(sql).fetchall()
        conn.close()
        return [{"domain": r[0], "value": r[1]} for r in rows]

    def get_all_targets(self) -> list[dict]:
        conn = self._conn()
        rows = conn.execute("""
            SELECT t.id, t.domain, t.url, t.first_seen, t.last_scanned, t.scan_count, t.total_leaks, t.model_fingerprint,
                   (SELECT COUNT(*) FROM prompt_changes WHERE target_id = t.id) as changes
            FROM targets t ORDER BY t.last_scanned DESC
        """).fetchall()
        conn.close()
        return [
            {"id": r[0], "domain": r[1], "url": r[2], "first_seen": r[3], "last_scanned": r[4],
             "scan_count": r[5], "total_leaks": r[6], "model_fingerprint": r[7], "changes": r[8]}
            for r in rows
        ]

    def export_intel_report(self, output_path: str):
        """Export full intelligence database as an HTML report."""
        targets = self.get_all_targets()
        leaderboard = self.get_leaderboard("most_changes")

        rows = ""
        for t in targets:
            changes = self.get_timeline(t["domain"])
            change_summary = f"{t['changes']} changes" if t["changes"] > 0 else "No changes"
            rows += f"""
            <tr>
                <td><a href="#target-{t['id']}">{t['domain']}</a></td>
                <td>{t['scan_count']}</td>
                <td>{change_summary}</td>
                <td>{t['last_scanned'][:19] if t['last_scanned'] else '-'}</td>
            </tr>"""

        detail_sections = ""
        for t in targets:
            changes = self.get_timeline(t["domain"])
            change_rows = ""
            for c in changes:
                change_rows += f"""
                <tr>
                    <td>{c['detected_at'][:19]}</td>
                    <td><span class="badge badge-{c['type'].lower()}">{c['type']}</span></td>
                    <td>{c['summary']}</td>
                    <td>{c['similarity']:.0%}</td>
                    <td><pre>{c['old_preview']}</pre></td>
                    <td><pre>{c['new_preview']}</pre></td>
                </tr>"""
            if not change_rows:
                change_rows = "<tr><td colspan='6'>No changes detected</td></tr>"
            detail_sections += f"""
            <div class="target-section" id="target-{t['id']}">
                <h2>{t['domain']}</h2>
                <p>URL: {t['url']} | Scans: {t['scan_count']} | Model: {t['model_fingerprint'] or 'unknown'}</p>
                <table><tr><th>Time</th><th>Type</th><th>Summary</th><th>Similarity</th><th>Old Preview</th><th>New Preview</th></tr>{change_rows}</table>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>PromptLeak Intel Report</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0d1117; color:#c9d1d9; font-family:-apple-system,sans-serif; padding:20px; }}
    h1 {{ color:#58a6ff; }} h2 {{ color:#58a6ff; font-size:16px; margin:16px 0 8px; }}
    table {{ width:100%; border-collapse:collapse; margin:12px 0; background:#161b22; border:1px solid #30363d; border-radius:8px; }}
    th {{ background:#21262d; color:#8b949e; padding:10px; text-align:left; font-size:11px; text-transform:uppercase; }}
    td {{ padding:10px; border-bottom:1px solid #21262d; font-size:13px; }}
    tr:hover {{ background:#1c2128; }}
    pre {{ font-size:11px; max-height:60px; overflow:auto; }}
    .badge {{ display:inline-block; padding:2px 6px; border-radius:8px; font-size:10px; font-weight:600; }}
    .badge-rewritten {{ background:rgba(248,81,73,0.15); color:#f85149; }}
    .badge-modified {{ background:rgba(210,153,34,0.15); color:#d29922; }}
    .badge-minor_tweak {{ background:rgba(63,185,80,0.15); color:#3fb950; }}
    .target-section {{ margin:20px 0; padding:16px; background:#161b22; border:1px solid #30363d; border-radius:8px; }}
    .footer {{ text-align:center; color:#8b949e; font-size:12px; margin-top:40px; }}
</style>
</head>
<body>
<h1>PromptLeak Intel Report</h1>
<p>Generated {datetime.now().isoformat()[:19]} | {len(targets)} targets tracked</p>
<table><tr><th>Target</th><th>Scans</th><th>Changes</th><th>Last Scanned</th></tr>{rows}</table>
{detail_sections}
<div class="footer">Generated by PromptLeak</div>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Intel report written to {output_path}")
