import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BufferedReport:
    report_id: str
    payload: dict[str, Any]
    attempts: int


class ReportBuffer:
    def __init__(self, path: Path, max_reports: int) -> None:
        self.path = path
        self.max_reports = max_reports
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def enqueue(self, report_id: str, payload: dict[str, Any]) -> int:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO reports (report_id, payload) VALUES (?, ?)",
                (report_id, encoded),
            )
            count = self.count()
            overflow = max(0, count - self.max_reports)
            if overflow:
                self._connection.execute(
                    """
                    DELETE FROM reports
                    WHERE report_id IN (
                        SELECT report_id FROM reports
                        ORDER BY created_at ASC, rowid ASC
                        LIMIT ?
                    )
                    """,
                    (overflow,),
                )
            return overflow

    def pending(self, limit: int = 100) -> list[BufferedReport]:
        rows = self._connection.execute(
            """
            SELECT report_id, payload, attempts
            FROM reports
            ORDER BY created_at ASC, rowid ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            BufferedReport(
                report_id=row["report_id"],
                payload=json.loads(row["payload"]),
                attempts=row["attempts"],
            )
            for row in rows
        ]

    def mark_delivered(self, report_id: str) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM reports WHERE report_id = ?", (report_id,))

    def mark_failed(self, report_id: str, error: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE reports
                SET attempts = attempts + 1, last_error = ?
                WHERE report_id = ?
                """,
                (error[:500], report_id),
            )

    def count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM reports").fetchone()
        return int(row["count"]) if row else 0

    def set_metadata(self, key: str, value: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        row = self._connection.execute(
            "SELECT value FROM metadata WHERE key = ?",
            (key,),
        ).fetchone()
        return str(row["value"]) if row else default

    def close(self) -> None:
        self._connection.close()
