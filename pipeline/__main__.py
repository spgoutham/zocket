"""Single entry point for the whole pipeline: `python -m pipeline`.

Session 0 status: config loading, logging, and the storage schema are wired
up and real. The crawl / classify / summarize stages themselves are stubs
until their sessions land -- see README.md for the stage-by-stage plan.
"""

from __future__ import annotations

import logging

from pipeline.config import load_config
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

    log.info(
        "crawl/classify/summarize stages not implemented yet -- "
        "see README.md for the stage-by-stage plan"
    )


if __name__ == "__main__":
    main()
