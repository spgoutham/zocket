"""Summarize -- Part 3's "summarize" half.

Emits a Markdown summary an analyst could read in about 30 seconds: totals
(crawled vs. deduped), category counts, sentiment breakdown per topic, and
the top few items per topic by reliability_score.
"""

from __future__ import annotations

import datetime
import sqlite3


def generate_summary(conn: sqlite3.Connection, total_crawled: int) -> str:
    total_deduped = conn.execute("SELECT COUNT(*) FROM mentions").fetchone()[0]
    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Consumer Research Summary",
        "",
        f"_Generated {generated_at}_",
        "",
        f"- **Records crawled this run (pre-dedup):** {total_crawled}",
        f"- **Records stored (deduped, all-time):** {total_deduped}",
        f"- **Duplicates skipped this run:** {total_crawled - total_deduped}",
        "",
        "(\"Crawled this run\" recomputes from the raw cache every time -- on a "
        "second run it's identical to the first, while \"stored\" stays fixed "
        "at the same total. That's the idempotency proof: re-running adds "
        "nothing new.)",
        "",
        "## Category breakdown",
        "",
        "| Category | Count |",
        "|---|---|",
    ]

    for category, count in conn.execute(
        "SELECT category, COUNT(*) FROM mentions GROUP BY category ORDER BY COUNT(*) DESC"
    ):
        lines.append(f"| {category} | {count} |")

    lines += [
        "",
        "## Sentiment breakdown per topic",
        "",
        "| Topic | Positive | Neutral | Negative |",
        "|---|---|---|---|",
    ]

    topics = [row[0] for row in conn.execute("SELECT DISTINCT topic FROM mentions ORDER BY topic")]
    for topic in topics:
        counts = dict(
            conn.execute(
                "SELECT sentiment, COUNT(*) FROM mentions WHERE topic = ? GROUP BY sentiment",
                (topic,),
            ).fetchall()
        )
        lines.append(
            f"| {topic} | {counts.get('positive', 0)} | {counts.get('neutral', 0)} "
            f"| {counts.get('negative', 0)} |"
        )

    lines += ["", "## Top 3 items per topic (by reliability_score)", ""]

    for topic in topics:
        lines.append(f"### {topic}")
        lines.append("")
        top_rows = conn.execute(
            "SELECT title, sentiment, category, reliability_score, url FROM mentions "
            "WHERE topic = ? ORDER BY reliability_score DESC LIMIT 3",
            (topic,),
        ).fetchall()
        for title, sentiment, category, score, url in top_rows:
            link = f" — {url}" if url else ""
            lines.append(f"- **{title}** ({sentiment}, {category}, reliability {score:.2f}){link}")
        lines.append("")

    return "\n".join(lines)
