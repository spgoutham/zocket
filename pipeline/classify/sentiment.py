"""VADER sentiment classification -- off-the-shelf, per the brief's constraints.

VADER is lexicon-based (tuned on social media / short informal text, which
is a reasonable match for HN titles+comments) and returns a `compound`
score from -1 to +1. `config.yaml`'s thresholds (VADER's own documented
defaults: +/-0.05) turn that score into a label.
"""

from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def classify_sentiment(text: str, thresholds: dict) -> tuple[str, float]:
    """Return (label, compound_score) for `text`."""
    score = _analyzer.polarity_scores(text)["compound"]

    if score >= thresholds["positive_threshold"]:
        label = "positive"
    elif score <= thresholds["negative_threshold"]:
        label = "negative"
    else:
        label = "neutral"

    return label, score
