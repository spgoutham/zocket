"""Single entry point for the whole pipeline: `python -m pipeline`.

Status: config, logging, storage schema, Stage 1 (crawl), and Stage 2
(transform + load) are real. Classify/summarize are still stubs -- see
README.md for the stage-by-stage plan.
"""

from __future__ import annotations

import logging

from pipeline.config import load_config
from pipeline.crawler.hn_algolia import fetch_topic
from pipeline.logging_setup import setup_logging
from pipeline.storage.db import get_connection, init_schema, upsert_mentions
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
    conn.close()

    log.info(
        "classify/summarize not implemented yet -- see README.md for the stage-by-stage plan"
    )


if __name__ == "__main__":
    main()
