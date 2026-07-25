"""SQLite schema for the `mentions` table.

Schema only at this stage (Session 0) -- insert/upsert/query logic belongs to
Stage 2 (Transform + Load) and Stage 3 (Classify), once there's real data to
push through it. Defining the contract now so those stages build against a
fixed shape instead of improvising it mid-flight.

Design notes:
  - `id` is the source-provided stable id (HN object id) and is the PRIMARY
    KEY, which is what makes re-runs idempotent: re-inserting the same id is
    a no-op via INSERT OR IGNORE / UPSERT, not a new row.
  - `category_reasoning` is deliberately not optional decoration: it's the
    same "explain every decision" instinct as KaizoCore's detection
    dashboard, applied to a sentiment/category label instead of a bot score.
  - `raw_ref` points back at the persisted raw payload file so any record
    can be traced back to exactly what the crawler saw.
"""

from __future__ import annotations

import pathlib
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS mentions (
    id                  TEXT PRIMARY KEY,
    topic               TEXT NOT NULL,
    source              TEXT NOT NULL,
    author              TEXT,
    title               TEXT,
    text                TEXT,
    url                 TEXT,
    created_at          TEXT NOT NULL,
    fetched_at          TEXT NOT NULL,
    raw_ref             TEXT,
    sentiment           TEXT,
    sentiment_score     REAL,
    category            TEXT,
    category_reasoning  TEXT,
    inserted_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_mentions_topic ON mentions(topic);
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment ON mentions(sentiment);
CREATE INDEX IF NOT EXISTS idx_mentions_category ON mentions(category);
"""


def get_connection(db_path: str | pathlib.Path) -> sqlite3.Connection:
    db_path = pathlib.Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
