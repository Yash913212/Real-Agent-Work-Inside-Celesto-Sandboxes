"""Database access layer for Ledger runs."""
import os
import sqlite3
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import DATABASE_URL, BASE_DIR

# Seed path
SEED_PATH = BASE_DIR / "seeds" / "01_runs.sql"


class Database:
    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
        self._is_postgres = db_url.startswith("postgres://") or db_url.startswith("postgresql://")
        self._sqlite_conn: Optional[sqlite3.Connection] = None

    def _get_pg_conn(self):
        return psycopg2.connect(self.db_url)

    def init_db(self):
        """Ensure schema exists and apply seed if needed."""
        if self._is_postgres:
            try:
                with self._get_pg_conn() as conn:
                    with conn.cursor() as cur:
                        if SEED_PATH.exists():
                            cur.execute(SEED_PATH.read_text())
                        else:
                            cur.execute("""
                                CREATE TABLE IF NOT EXISTS runs (
                                    run_id VARCHAR(64) PRIMARY KEY,
                                    sandbox_name VARCHAR(64) NOT NULL,
                                    problem_id VARCHAR(64) NOT NULL,
                                    state VARCHAR(32) NOT NULL,
                                    execution_target VARCHAR(64) NOT NULL,
                                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                                );
                                INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
                                VALUES ('run-seed-001', 'sbx-seeddemo1', 'detonator-prob-01', 'deleted', 'celesto_sandbox')
                                ON CONFLICT (run_id) DO NOTHING;
                            """)
                        conn.commit()
                return
            except Exception as e:
                # If Postgres connection fails during local standalone testing, fallback to SQLite
                print(f"[DB] Postgres init failed ({e}), falling back to SQLite for local standalone mode.")
                self._is_postgres = False

        # SQLite fallback
        self._sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
        cur = self._sqlite_conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                sandbox_name TEXT NOT NULL,
                problem_id TEXT NOT NULL,
                state TEXT NOT NULL,
                execution_target TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            INSERT OR IGNORE INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
            VALUES ('run-seed-001', 'sbx-seeddemo1', 'detonator-prob-01', 'deleted', 'celesto_sandbox');
        """)
        self._sqlite_conn.commit()

    def list_runs(self) -> List[Dict[str, Any]]:
        """Return all runs sorted by created_at."""
        if self._is_postgres:
            try:
                with self._get_pg_conn() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("SELECT run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at FROM runs ORDER BY created_at ASC")
                        rows = cur.fetchall()
                        results = []
                        for row in rows:
                            d = dict(row)
                            if d.get("created_at"):
                                d["created_at"] = str(d["created_at"])
                            if d.get("updated_at"):
                                d["updated_at"] = str(d["updated_at"])
                            results.append(d)
                        return results
            except Exception as e:
                print(f"[DB] Postgres list_runs failed: {e}")

        # SQLite fallback
        if not self._sqlite_conn:
            self.init_db()
        cur = self._sqlite_conn.cursor()
        cur.execute("SELECT run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at FROM runs ORDER BY created_at ASC")
        rows = cur.fetchall()
        return [
            {
                "run_id": r[0],
                "sandbox_name": r[1],
                "problem_id": r[2],
                "state": r[3],
                "execution_target": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

    def insert_run(self, run_id: str, sandbox_name: str, problem_id: str, state: str, execution_target: str) -> Dict[str, Any]:
        """Insert or update a run row."""
        if self._is_postgres:
            try:
                with self._get_pg_conn() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT (run_id) DO UPDATE SET
                                state = EXCLUDED.state,
                                sandbox_name = EXCLUDED.sandbox_name,
                                problem_id = EXCLUDED.problem_id,
                                execution_target = EXCLUDED.execution_target,
                                updated_at = CURRENT_TIMESTAMP
                            RETURNING run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at
                        """, (run_id, sandbox_name, problem_id, state, execution_target))
                        row = cur.fetchone()
                        conn.commit()
                        d = dict(row)
                        d["created_at"] = str(d["created_at"])
                        d["updated_at"] = str(d["updated_at"])
                        return d
            except Exception as e:
                print(f"[DB] Postgres insert_run failed ({e}), falling back to SQLite.")

        if not self._sqlite_conn:
            self.init_db()
        cur = self._sqlite_conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO runs (run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (run_id, sandbox_name, problem_id, state, execution_target))
        self._sqlite_conn.commit()
        return {
            "run_id": run_id,
            "sandbox_name": sandbox_name,
            "problem_id": problem_id,
            "state": state,
            "execution_target": execution_target,
            "created_at": "CURRENT_TIMESTAMP",
            "updated_at": "CURRENT_TIMESTAMP",
        }


db = Database()
