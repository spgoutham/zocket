"""HN Algolia crawler -- Part 1 (Crawl / Extract).

Uses `search_by_date` (not the default relevance-sorted `search`) because
date order is stable between runs; relevance order can reshuffle, which
would make "page 3" mean a different set of items today vs. tomorrow and
break the on-disk page cache below.

Four pieces:
  - _throttle / _sleep_backoff -- politeness (always) vs. retry (on failure)
  - _request_with_backoff      -- one HTTP GET, retried on transient failure
  - _fetch_query_variant       -- paginates ONE query string to target_items,
                                   caching each page to disk
  - fetch_topic                -- runs every query variant for a topic
                                   (usually just one; see `chime` in
                                   config.yaml for why a topic can have more
                                   than one) and merges them by objectID
"""

from __future__ import annotations

import json
import logging
import pathlib
import random
import time

import requests

from pipeline.config import Topic

log = logging.getLogger("pipeline.crawler")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _throttle(source: dict) -> None:
    """Sleep before every real request -- the rate-limit floor, not a retry."""
    delay = source["min_delay_seconds"] + random.uniform(0, source["jitter_seconds"])
    time.sleep(delay)


def _sleep_backoff(attempt: int, source: dict, reason: str) -> None:
    """Sleep between retries of a failed request, backing off exponentially."""
    delay = min(source["backoff_base_seconds"] * (2**attempt), source["backoff_max_seconds"])
    log.warning(
        "retrying after transient failure",
        extra={"attempt": attempt + 1, "delay_seconds": round(delay, 2), "reason": reason},
    )
    time.sleep(delay)


def _request_with_backoff(params: dict, source: dict) -> dict:
    """One HTTP GET against `source['base_url']`, retried on transient failure.

    Timeouts and connection errors are transient (network hiccup) --
    retried. HTTP 429/5xx are transient (server-side, rate-limited or
    struggling) -- retried. Anything else (e.g. a 4xx from a malformed
    request) is not transient -- `raise_for_status()` fails fast instead of
    retrying a request that will never succeed.
    """
    headers = {"User-Agent": source["user_agent"]}
    timeout = source["request_timeout_seconds"]
    max_retries = source["max_retries"]

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(
                source["base_url"], params=params, headers=headers, timeout=timeout
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == max_retries:
                raise
            _sleep_backoff(attempt, source, reason=repr(exc))
            continue

        if response.status_code == 200:
            return response.json()
        if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
            _sleep_backoff(attempt, source, reason=f"HTTP {response.status_code}")
            continue

        response.raise_for_status()

    raise RuntimeError(f"exhausted {max_retries} retries for params={params}")


def _fetch_query_variant(
    query: str, topic_id: str, target_items: int, source: dict, variant_dir: pathlib.Path
) -> dict[str, dict]:
    """Paginate ONE query string up to target_items, caching each page to disk.

    Returns hits keyed by HN's own `objectID` (a dict, not a list) so
    `fetch_topic` can merge several variants without double-counting a
    story that happens to match more than one of them. A page already
    cached on disk is read from disk instead of re-fetched.
    """
    variant_dir.mkdir(parents=True, exist_ok=True)
    hits_per_page = source["hits_per_page"]
    hits_by_id: dict[str, dict] = {}
    page = 0

    while len(hits_by_id) < target_items:
        page_path = variant_dir / f"page_{page}.json"

        if page_path.exists():
            payload = json.loads(page_path.read_text())
            log.info(
                "raw page cached, skipping fetch",
                extra={"topic": topic_id, "query": query, "page": page},
            )
        else:
            _throttle(source)
            payload = _request_with_backoff(
                params={
                    # query is expected to already be quoted where needed
                    # (config.yaml owns that decision, see its own comments)
                    "query": query,
                    "typoTolerance": "true" if source["typo_tolerance"] else "false",
                    "tags": "story",
                    "page": page,
                    "hitsPerPage": hits_per_page,
                },
                source=source,
            )
            page_path.write_text(json.dumps(payload))
            log.info(
                "fetched page",
                extra={
                    "topic": topic_id,
                    "query": query,
                    "page": page,
                    "hits": len(payload.get("hits", [])),
                },
            )

        page_hits = payload.get("hits", [])
        for hit in page_hits:
            hits_by_id[hit["objectID"]] = hit

        if len(page_hits) < hits_per_page:
            break  # source has no more results for this query
        page += 1

    return hits_by_id


def fetch_topic(topic: Topic, source: dict, raw_dir: str | pathlib.Path) -> list[dict]:
    """Run every query variant for `topic`, merge by objectID, cap at target_items.

    Most topics have exactly one variant (their plain brand name). A topic
    with more than one (see `chime` in config.yaml) exists because a single
    query wasn't precise enough on its own -- merging variants trades a bit
    of extra crawling for better recall without giving up the precision each
    variant was chosen for. A story matching more than one variant is only
    kept once.
    """
    topic_dir = pathlib.Path(raw_dir) / topic.id
    merged: dict[str, dict] = {}

    for variant_index, query in enumerate(topic.queries):
        variant_dir = topic_dir / f"q{variant_index}"
        merged.update(
            _fetch_query_variant(query, topic.id, topic.target_items, source, variant_dir)
        )

    if not merged:
        log.warning("topic returned zero hits", extra={"topic": topic.id, "queries": topic.queries})

    return list(merged.values())[: topic.target_items]
