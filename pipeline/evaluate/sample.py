"""Stage 4 (Evaluate), step 1: draw a stratified sample for hand-labeling.

Pulls `per_topic` random records per topic (5 topics x 5 = 25 by default)
and writes them to eval/labeled_sample.csv with id/topic/title/text/url --
deliberately NOT the classifier's own sentiment/category, so whoever
hand-labels the sample isn't anchored by what the classifier already said.
Won't overwrite an existing sample file (hand-edits would be lost).
"""

from __future__ import annotations

import csv
import pathlib
import random
import sqlite3

from pipeline.config import load_config
from pipeline.storage.db import get_connection

SAMPLE_PATH = pathlib.Path("eval/labeled_sample.csv")
FIELDNAMES = ["id", "topic", "title", "text", "url", "true_sentiment", "true_category", "notes"]


def stratified_sample(conn: sqlite3.Connection, per_topic: int, seed: int) -> list[dict]:
    """Return `per_topic` randomly-chosen records for every topic, seeded
    for reproducibility -- re-running this produces the same sample."""
    topics = [row[0] for row in conn.execute("SELECT DISTINCT topic FROM mentions ORDER BY topic")]
    rng = random.Random(seed)
    sample = []

    for topic in topics:
        rows = conn.execute(
            "SELECT id, topic, title, text, url FROM mentions WHERE topic = ?", (topic,)
        ).fetchall()
        chosen = rng.sample(rows, min(per_topic, len(rows)))
        for row in chosen:
            sample.append(dict(zip(["id", "topic", "title", "text", "url"], row)))

    return sample


def main() -> None:
    if SAMPLE_PATH.exists():
        print(f"{SAMPLE_PATH} already exists -- not overwriting (would lose hand-labels).")
        return

    config = load_config("config.yaml")
    conn = get_connection(config.storage["db_path"])
    sample = stratified_sample(conn, per_topic=5, seed=42)
    conn.close()

    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLE_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in sample:
            row["true_sentiment"] = ""
            row["true_category"] = ""
            row["notes"] = ""
            writer.writerow(row)

    print(f"wrote {len(sample)} rows to {SAMPLE_PATH}")


if __name__ == "__main__":
    main()
