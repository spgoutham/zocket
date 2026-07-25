"""Single entry point for the whole pipeline: `python -m pipeline`.

Status: config, logging, storage schema, Stage 1 (crawl), Stage 2
(transform + load), Stage 3 (classify), and Stage 4's summarize step are
all real -- this is the full pipeline end to end.
"""

from __future__ import annotations

import logging
import pathlib

from pipeline.classify.category import classify_category
from pipeline.classify.sentiment import classify_sentiment
from pipeline.config import load_config
from pipeline.crawler.hn_algolia import fetch_topic
from pipeline.logging_setup import setup_logging
from pipeline.storage.db import (
    fetch_for_classification,
    get_connection,
    init_schema,
    update_classifications,
    upsert_mentions,
)
from pipeline.summarize import generate_summary
from pipeline.transform import iter_raw_hits, normalize_hit

log = logging.getLogger("pipeline.main")


def main() -> None:
    config = load_config("config.yaml")
    setup_logging(level=config.logging["level"])

    log.info("config loaded", extra={"topics": [t.id for t in config.topics]})

    conn = get_connection(config.storage["db_path"])
    init_schema(conn)
    log.info("storage schema ready", extra={"db_path": config.storage["db_path"]})

    total_records_this_run = 0
    for topic in config.topics:
        hits = fetch_topic(topic, config.source, config.storage["raw_dir"])
        log.info("topic crawled", extra={"topic": topic.id, "raw_items": len(hits)})

        records = []
        for hit, fetched_at in iter_raw_hits(config.storage["raw_dir"], topic.id):
            record = normalize_hit(
                hit, topic.id, config.source["name"], fetched_at, config.reliability
            )
            if record is not None:
                records.append(record)

        inserted = upsert_mentions(conn, records)
        total_records_this_run += len(records)
        log.info(
            "topic loaded",
            extra={"topic": topic.id, "records": len(records), "inserted": inserted},
        )

    total = conn.execute("SELECT COUNT(*) FROM mentions").fetchone()[0]
    log.info("load complete", extra={"total_mentions": total})

    sentiment_thresholds = config.classification["sentiment"]
    updates = []
    for mention_id, title, text in fetch_for_classification(conn):
        combined = f"{title or ''} {text or ''}".strip()
        sentiment, sentiment_score = classify_sentiment(combined, sentiment_thresholds)
        category = classify_category(combined)
        updates.append(
            {
                "id": mention_id,
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "category": category,
            }
        )
    update_classifications(conn, updates)
    log.info("classification complete", extra={"classified": len(updates)})

    summary = generate_summary(conn, total_crawled=total_records_this_run)
    summary_path = pathlib.Path(config.storage["summary_path"])
    summary_path.write_text(summary)
    log.info("summary written", extra={"summary_path": str(summary_path)})

    conn.close()


if __name__ == "__main__":
    main()
