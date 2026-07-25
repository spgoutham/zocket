"""Keyword-based category tagger -- transparent, reproducible, no ML.

Each category (config.yaml `classification.categories`) has a fixed keyword
list below, built by reading the actual 240 crawled titles (not guessed).
A record is scored against every category by counting keyword hits in its
lowercased title+text; the category with the most hits wins, ties broken by
list order, and zero hits anywhere falls through to `general`.

Left-anchored word-boundary matching (`\\bkeyword`, not `\\bkeyword\\b`) --
not plain substring matching. Stage 4's hand-labeled evaluation caught a
real substring collision ("valuation" matching inside "Evaluation"), which
a left boundary alone fixes (nothing precedes "valuation" mid-word in
"Evaluation" the way "E" does). A *right* boundary too was tried first and
reverted: it broke intentional stem matches this keyword list relies on
("rebrand" matching "rebrands", "advertis" matching "advertising", "unveil"
matching "unveils") -- verified both ways before settling on left-only.
"""

from __future__ import annotations

import re

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "business_news": [
        "ipo", "s-1", "s1", "valuation", "valued at", "stock", "share",
        "surge", "jump", "raise", "raised", "raises", "funding", "series a",
        "series b", "series c", "series f", "acquisition", "acquire",
        "acquires", "acquired", "sold", "merger", "joint venture", "invest",
        "investment", "bankrupt", "delisting", "loan", "reverse stock split",
        "earnings", "revenue", "profit", "layoff", "lays off", "laying off",
        "spin-off", "spinoff", "quarter", "grant", "unlocked",
    ],
    "marketing_advertising": [
        "marketing", "advertis", "campaign", "rebrand", "growth marketing",
        "landing page", "a/b test", "ab test", "influencer", "commercial",
        "promo", "branding", "acquires and converts", "sponsorship",
    ],
    "customer_service_trust": [
        "fraud", "scam", "sue", "sued", "sues", "complaint",
        "privacy", "security", "hacked", "flagged", "2fa", "data collection",
        "goes dark", "without access", "trust", "criticism", "backlash",
        "false accusation", "police", "outbreak", "locked out",
        "breach", "stuck", "illegal",
    ],
    "pricing_subscription": [
        "price", "pricing", "lease", "cost", "fee", "subscription", "cancel",
        "discount", "afford", "expensive", "cheap", "starting at",
    ],
    "product_experience": [
        "review", "quality", "comfortable", "feature", "design", "app",
        "experience", "interface", "taste", "release", "unveil", "specs",
        "autonomy", "self-driving", "lidar", "chip", "software", "update",
        "version", "deliver", "launch",
    ],
    "regulatory": [
        "lawsuit", "court", "fcc", "banned",
    ],
}

_FALLBACK_CATEGORY = "general"

_CATEGORY_PATTERNS: dict[str, list[re.Pattern]] = {
    category: [re.compile(rf"\b{re.escape(kw)}") for kw in keywords]
    for category, keywords in _CATEGORY_KEYWORDS.items()
}


def classify_category(text: str) -> str:
    """Return the winning category id for `text` (or "general" if none match)."""
    lowered = text.lower()

    best_category = _FALLBACK_CATEGORY
    best_score = 0

    for category, patterns in _CATEGORY_PATTERNS.items():
        score = sum(1 for pattern in patterns if pattern.search(lowered))
        if score > best_score:
            best_category = category
            best_score = score

    return best_category
