"""Stage 4 (Evaluate), step 2: compare hand-labels against the classifier.

Reads eval/labeled_sample.csv (hand-labeled independently, blind to the
classifier's output -- see sample.py) and the classifier's actual stored
labels for those same ids, then reports accuracy and a confusion matrix for
both sentiment and category.
"""

from __future__ import annotations

import csv
import pathlib
from collections import Counter

from pipeline.config import load_config
from pipeline.storage.db import get_connection

SAMPLE_PATH = pathlib.Path("eval/labeled_sample.csv")


def _confusion_matrix(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """pairs is a list of (true_label, predicted_label). Returns counts keyed
    by (true, predicted)."""
    matrix: dict[tuple[str, str], int] = Counter()
    for true_label, predicted_label in pairs:
        matrix[(true_label, predicted_label)] += 1
    return matrix


def _print_matrix(title: str, pairs: list[tuple[str, str]]) -> None:
    labels = sorted({label for pair in pairs for label in pair})
    matrix = _confusion_matrix(pairs)

    correct = sum(count for (t, p), count in matrix.items() if t == p)
    total = len(pairs)

    print(f"\n{title}: {correct}/{total} correct ({correct / total:.0%})")
    header = "true\\pred".ljust(24) + "".join(label[:10].rjust(12) for label in labels)
    print(header)
    for true_label in labels:
        row = true_label.ljust(24)
        for predicted_label in labels:
            row += str(matrix.get((true_label, predicted_label), 0)).rjust(12)
        print(row)


def main() -> None:
    rows = list(csv.DictReader(SAMPLE_PATH.open(newline="", encoding="utf-8")))
    ids = [row["id"] for row in rows]

    config = load_config("config.yaml")
    conn = get_connection(config.storage["db_path"])
    placeholders = ",".join("?" * len(ids))
    rows_from_db = conn.execute(
        f"SELECT id, sentiment, category FROM mentions WHERE id IN ({placeholders})", ids
    ).fetchall()
    predicted = {mention_id: (sentiment, category) for mention_id, sentiment, category in rows_from_db}
    conn.close()

    sentiment_pairs = [(row["true_sentiment"], predicted[row["id"]][0]) for row in rows]
    category_pairs = [(row["true_category"], predicted[row["id"]][1]) for row in rows]

    _print_matrix("Sentiment", sentiment_pairs)
    _print_matrix("Category", category_pairs)

    mismatches = [
        row
        for row in rows
        if row["true_sentiment"] != predicted[row["id"]][0]
        or row["true_category"] != predicted[row["id"]][1]
    ]
    print(f"\n{len(mismatches)}/{len(rows)} rows had at least one mismatch:")
    for row in mismatches:
        pred_sentiment, pred_category = predicted[row["id"]]
        print(
            f"  [{row['id']}] true=({row['true_sentiment']}, {row['true_category']}) "
            f"pred=({pred_sentiment}, {pred_category}) -- {row['title'][:70]}"
        )


if __name__ == "__main__":
    main()
