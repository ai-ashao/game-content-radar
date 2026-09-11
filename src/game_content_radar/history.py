from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


class HistoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_snapshots (
                appid INTEGER NOT NULL,
                game_name TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                players INTEGER NOT NULL,
                PRIMARY KEY (appid, captured_at)
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add_player_snapshot(self, appid: int, game_name: str, players: int, captured_at: str | None = None) -> str:
        ts = captured_at or datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO player_snapshots(appid, game_name, captured_at, players) VALUES (?, ?, ?, ?)",
            (appid, game_name, ts, players),
        )
        self.conn.commit()
        return ts

    def nearest_before(self, appid: int, hours: int, now: datetime | None = None) -> tuple[str, int] | None:
        now = now or datetime.now(timezone.utc)
        target = now - timedelta(hours=hours)
        # Prefer a snapshot near the target but not newer than 70% of the window.
        upper = now - timedelta(hours=max(1, int(hours * 0.7)))
        row = self.conn.execute(
            """
            SELECT captured_at, players
            FROM player_snapshots
            WHERE appid = ? AND captured_at <= ?
            ORDER BY ABS(strftime('%s', captured_at) - strftime('%s', ?)) ASC
            LIMIT 1
            """,
            (appid, upper.isoformat(), target.isoformat()),
        ).fetchone()
        return (str(row[0]), int(row[1])) if row else None
