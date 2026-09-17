"""
JARVIS-Windows - Run storage with SQLite.
Tracks all runs, their status, events, and usage.
"""
import sqlite3
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .data_paths import get_data_paths

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"

@dataclass
class Run:
    id: str
    project: str
    prompt: str
    status: RunStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    tokens_used: int = 0
    model: str = "sonnet"
    brief: Optional[str] = None
    plan: Optional[str] = None

@dataclass
class RunEvent:
    id: int
    run_id: str
    timestamp: datetime
    event_type: str
    payload: Dict[str, Any]

class RunStore:
    def __init__(self):
        self.db_path = get_data_paths().runs_db
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    exit_code INTEGER,
                    error TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    model TEXT DEFAULT 'sonnet',
                    brief TEXT,
                    plan TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id)
            """)
    
    def create_run(self, run: Run) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO runs (id, project, prompt, status, created_at, model, brief, plan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.id, run.project, run.prompt, run.status.value,
                run.created_at.isoformat(), run.model, run.brief, run.plan
            ))
    
    def update_run(self, run: Run) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE runs SET
                    status = ?, started_at = ?, finished_at = ?,
                    exit_code = ?, error = ?, tokens_used = ?,
                    brief = ?, plan = ?
                WHERE id = ?
            """, (
                run.status.value, 
                run.started_at.isoformat() if run.started_at else None,
                run.finished_at.isoformat() if run.finished_at else None,
                run.exit_code, run.error, run.tokens_used,
                run.brief, run.plan, run.id
            ))
    
    def get_run(self, run_id: str) -> Optional[Run]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            return self._row_to_run(row)
    
    def list_runs(self, project: Optional[str] = None, status: Optional[RunStatus] = None, limit: int = 100) -> List[Run]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM runs WHERE 1=1"
            params = []
            if project:
                query += " AND project = ?"
                params.append(project)
            if status:
                query += " AND status = ?"
                params.append(status.value)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_run(row) for row in rows]
    
    def add_event(self, run_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO run_events (run_id, timestamp, event_type, payload)
                VALUES (?, ?, ?, ?)
            """, (run_id, datetime.now().isoformat(), event_type, json.dumps(payload)))
    
    def get_events(self, run_id: str) -> List[RunEvent]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM run_events WHERE run_id = ? ORDER BY timestamp",
                (run_id,)
            ).fetchall()
            return [
                RunEvent(
                    id=row["id"],
                    run_id=row["run_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    event_type=row["event_type"],
                    payload=json.loads(row["payload"])
                )
                for row in rows
            ]
    
    def _row_to_run(self, row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"],
            project=row["project"],
            prompt=row["prompt"],
            status=RunStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            exit_code=row["exit_code"],
            error=row["error"],
            tokens_used=row["tokens_used"] or 0,
            model=row["model"] or "sonnet",
            brief=row["brief"],
            plan=row["plan"]
        )

# Global instance
_run_store = None

def get_run_store() -> RunStore:
    global _run_store
    if _run_store is None:
        _run_store = RunStore()
    return _run_store