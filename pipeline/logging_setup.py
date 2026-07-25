"""Structured (JSON) logging setup, shared by every stage of the pipeline.

Every log line carries stage + topic context where relevant, so a run's log
can be grepped/aggregated after the fact -- same instinct as wiring
observability into a production decision system: you want to be able to
answer "what happened on this run" without re-running it.
"""

from __future__ import annotations

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in getattr(record, "context", {}).items():
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


class _ContextAdapter(logging.LoggerAdapter):
    """Lets callers attach structured context without fighting stdlib's `extra`.

    `get_logger("pipeline.crawler", topic="cloudflare")` binds context once;
    `log.info("fetched page", context={"page": 3})` merges in per-call
    context on top of it. Both end up under the `context` key the
    JsonFormatter reads.
    """

    def process(self, msg, kwargs):
        context = {**self.extra, **kwargs.pop("context", {})}
        if context:
            kwargs["extra"] = {"context": context}
        return msg, kwargs


def get_logger(name: str, **context) -> logging.LoggerAdapter:
    return _ContextAdapter(logging.getLogger(name), context)
