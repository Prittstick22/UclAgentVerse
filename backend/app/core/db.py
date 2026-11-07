"""Tiny SQLite helper. One file holds events, runs, proposals, ledger snapshots, memory and the LLM cache."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, run_id TEXT, seq INTEGER, ts_wall TEXT, as_of TEXT, mode TEXT, type TEXT, json TEXT
);
CREATE INDEX IF NOT EXISTS events_run ON events(run_id, seq);
CREATE TABLE IF NOT EXISTS kv (ns TEXT, key TEXT, json TEXT, PRIMARY KEY (ns, key));
CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, response TEXT, tokens INTEGER, created TEXT);
"""


class DB:
    def __init__(self, path: Path | str = ":memory:"):
        self.path = str(path)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.executescript(SCHEMA)

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            cur = self.conn.execute(sql, params)
            rows = cur.fetchall()
            self.conn.commit()
            return rows

    # simple key-value store for runs, proposals, mandate, memory, etc.
    def put(self, ns: str, key: str, json_text: str) -> None:
        self.execute("INSERT OR REPLACE INTO kv(ns, key, json) VALUES (?,?,?)", (ns, key, json_text))

    def get(self, ns: str, key: str) -> str | None:
        rows = self.execute("SELECT json FROM kv WHERE ns=? AND key=?", (ns, key))
        return rows[0][0] if rows else None

    def list(self, ns: str) -> list[tuple[str, str]]:
        return self.execute("SELECT key, json FROM kv WHERE ns=? ORDER BY key", (ns,))
