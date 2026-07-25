"""Transform -- Part 2 (Transform + Load), the "transform" half.

Reads raw HN hits back from the disk cache Stage 1 wrote (not Stage 1's
in-memory return value) -- this stage can be re-run, or run on its own,
without a crawl having just happened in the same process. That's the
practical payoff of "persist the raw payload before transforming."
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import pathlib
import re
from typing import Iterator

log = logging.getLogger("pipeline.transform")

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str | None) -> str | None:
    """HN's story_text is HTML: `<p>` breaks, `&#x27;`-style escaped entities.

    Unescape + strip tags so what lands in the DB (and later goes into
    VADER for sentiment) is plain, readable text, not markup soup.
    """
    if not raw:
        return raw
    return _HTML_TAG_RE.sub("", html.unescape(raw)).strip()


def iter_raw_hits(raw_dir: str | pathlib.Path, topic_id: str) -> Iterator[tuple[dict, str]]:
    """Yield (hit, fetched_at) for every hit crawled for `topic_id`.

    fetched_at is the raw page file's own mtime -- the moment Stage 1
    actually wrote it. That stays correct across re-runs even when a page
    was served from cache rather than fetched fresh just now.
    """
    topic_dir = pathlib.Path(raw_dir) / topic_id
    for page_path in sorted(topic_dir.glob("**/page_*.json")):
        fetched_at = datetime.datetime.fromtimestamp(
            page_path.stat().st_mtime, tz=datetime.timezone.utc
        ).isoformat()
        payload = json.loads(page_path.read_text())
        for hit in payload.get("hits", []):
            yield hit, fetched_at


def compute_reliability(points: int, num_comments: int, has_text: bool, reliability: dict) -> float:
    """Rule-based (no ML) signal-quality proxy -- see config.yaml `reliability:`."""
    points_component = min(
        points / reliability["points_divisor"], reliability["points_weight_cap"]
    )
    comments_component = min(
        num_comments / reliability["comments_divisor"], reliability["comments_weight_cap"]
    )
    text_component = reliability["text_presence_weight"] if has_text else 0.0
    return round(points_component + comments_component + text_component, 4)


def normalize_hit(
    hit: dict, topic_id: str, source_name: str, fetched_at: str, reliability: dict
) -> dict | None:
    """Turn one raw HN hit into a `mentions` row.

    Returns None (and logs a warning) for a hit missing a field with no
    sane default -- id or created_at -- rather than inserting a broken row
    or crashing the whole run over one bad record.
    """
    object_id = hit.get("objectID")
    created_at = hit.get("created_at")
    if not object_id or not created_at:
        log.warning(
            "skipping hit with missing id/created_at",
            extra={"topic": topic_id, "hit_keys": sorted(hit.keys())},
        )
        return None

    text = _clean_text(hit.get("story_text"))
    points = hit.get("points") or 0
    num_comments = hit.get("num_comments") or 0

    return {
        "id": str(object_id),
        "topic": topic_id,
        "source": source_name,
        "author": hit.get("author") or None,
        "title": _clean_text(hit.get("title")) or None,
        "text": text,
        # HN's API is inconsistent about "no url": sometimes the key is
        # absent (-> None via .get()), sometimes it's a literal "" --
        # found by inspecting real rows, not assumed. Collapse both to a
        # single NULL rather than storing "no url" two different ways.
        "url": hit.get("url") or None,
        "created_at": created_at,
        "fetched_at": fetched_at,
        "reliability_score": compute_reliability(points, num_comments, bool(text), reliability),
    }
