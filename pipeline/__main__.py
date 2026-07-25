"""Single entry point for the whole pipeline: `python -m pipeline`.

Status: config, logging, storage schema, and Stage 1 (crawl) are real.
Transform+Load / classify / summarize are still stubs -- see README.md for
the stage-by-stage plan.
"""

from __future__ import annotations

import logging

from pipeline.config import load_config
from pipeline.crawler.hn_algolia import fetch_topic
from pipeline.logging_setup import setup_logging
from pipeline.storage.db import get_connection, init_schema

log = logging.getLogger("pipeline.main")


def main() -> None:
    config = load_config("config.yaml")
    setup_logging(level=config.logging["level"])

    log.info("config loaded", extra={"topics": [t.id for t in config.topics]})

    conn = get_connection(config.storage["db_path"])
    init_schema(conn)
    log.info("storage schema ready", extra={"db_path": config.storage["db_path"]})
    conn.close()

    for topic in config.topics:
        hits = fetch_topic(topic, config.source, config.storage["raw_dir"])
        log.info("topic crawled", extra={"topic": topic.id, "raw_items": len(hits)})

    log.info(
        "transform/load, classify, summarize not implemented yet -- "
        "see README.md for the stage-by-stage plan"
    )


if __name__ == "__main__":
    main()
