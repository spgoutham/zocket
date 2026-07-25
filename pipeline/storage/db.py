"""SQLite schema for the `mentions` table.

Schema only at this stage (Session 0) -- insert/upsert/query logic belongs to
Stage 2 (Transform + Load) and Stage 3 (Classify), once there's real data to
push through it. Defining the contract now so those stages build against a
fixed shape instead of improvising it mid-flight.

Columns match the assessment brief directly (id, topic, source, author,
title/text, url, created_at, fetched_at, plus sentiment + category), with
`id` as the source-provided stable id (HN object id) and PRIMARY KEY -- that's
what makes re-runs idempotent: re-inserting a known id is a no-op via
INSERT OR IGNORE / UPSERT, not a new row. Raw payloads live on disk under
data/raw/<topic>/<id>.json rather than a DB column -- the id already tells
you where to find them.

`reliability_score` is one addition beyond the brief's literal field list: a
rule-based (no ML) proxy for signal quality from HN's own points/comments,
so a 0-point drive-by comment doesn't count the same as a heavily upvoted,
heavily discussed post. Column + index only for now -- the formula is
config in `config.yaml` (`reliability:`), the actual math gets written in
Stage 2 once points/num_comments are actually being crawled.
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
    sentiment           TEXT,
    sentiment_score     REAL,
    category            TEXT,
    reliability_score   REAL,
    inserted_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_mentions_topic ON mentions(topic);
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment ON mentions(sentiment);
CREATE INDEX IF NOT EXISTS idx_mentions_category ON mentions(category);
CREATE INDEX IF NOT EXISTS idx_mentions_reliability ON mentions(reliability_score);
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
