"""Single entry point for the whole pipeline: `python -m pipeline`.

Status: config, logging, storage schema, Stage 1 (crawl), Stage 2
(transform + load), and Stage 3 (classify) are real. Summarize is still a
stub -- see README.md for the stage-by-stage plan.
"""

from __future__ import annotations

import logging

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
from pipeline.transform import iter_raw_hits, normalize_hit

log = logging.getLogger("pipeline.main")


def main() -> None:
    config = load_config("config.yaml")
    setup_logging(level=config.logging["level"])

    log.info("config loaded", extra={"topics": [t.id for t in config.topics]})

    conn = get_connection(config.storage["db_path"])
    init_schema(conn)
    log.info("storage schema ready", extra={"db_path": config.storage["db_path"]})

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

    conn.close()

    log.info("summarize not implemented yet -- see README.md for the stage-by-stage plan")


if __name__ == "__main__":
    main()
