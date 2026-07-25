"""SQLite schema + load for the `mentions` table.

Columns match the assessment brief directly (id, topic, source, author,
title/text, url, created_at, fetched_at, plus sentiment + category), with
`id` as the source-provided stable id (HN object id) and PRIMARY KEY -- that's
what makes re-runs idempotent: re-inserting a known id is a no-op via
`INSERT OR IGNORE`, not a new row. Raw payloads live on disk under
data/raw/<topic>/q<N>/page_<M>.json (see pipeline/crawler/) rather than a
DB column -- pipeline/transform.py reads them back by topic.

`reliability_score` is one addition beyond the brief's literal field list: a
rule-based (no ML) proxy for signal quality from HN's own points/comments,
so a 0-point drive-by comment doesn't count the same as a heavily upvoted,
heavily discussed post. Computed in pipeline/transform.py, formula is config
in `config.yaml` (`reliability:`).
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


def upsert_mentions(conn: sqlite3.Connection, records: list[dict]) -> int:
    """Insert `records`, ignoring any whose id already exists.

    `INSERT OR IGNORE` against the `id` PRIMARY KEY is the whole idempotency
    mechanism -- re-running with the same (or overlapping) records creates
    no duplicate rows, no application-level dedup logic required. Returns
    how many rows were actually newly inserted (via the `total_changes`
    delta), which is what makes "run it twice, show the counts" provable.
    """
    if not records:
        return 0

    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO mentions
            (id, topic, source, author, title, text, url,
             created_at, fetched_at, reliability_score)
        VALUES
            (:id, :topic, :source, :author, :title, :text, :url,
             :created_at, :fetched_at, :reliability_score)
        """,
        records,
    )
    conn.commit()
    return conn.total_changes - before


def fetch_for_classification(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    """Return (id, title, text) for every row -- the input classify needs."""
    return conn.execute("SELECT id, title, text FROM mentions").fetchall()


def update_classifications(conn: sqlite3.Connection, updates: list[dict]) -> None:
    """Write sentiment/sentiment_score/category back onto existing rows.

    An UPDATE, not an INSERT -- classification never creates rows, so it
    can't violate the load step's dedup guarantee. Always recomputed and
    overwritten on every run (classifying ~240 short records is
    milliseconds of work) rather than skipped for already-classified rows,
    so an improved classifier or retuned thresholds take effect on the next
    run without needing a reset.
    """
    if not updates:
        return
    conn.executemany(
        "UPDATE mentions SET sentiment=:sentiment, sentiment_score=:sentiment_score, "
        "category=:category WHERE id=:id",
        updates,
    )
    conn.commit()
