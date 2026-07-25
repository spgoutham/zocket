# Zocket Intern Assessment — Consumer Research Data Pipeline

This README is a running **session log**. Each session appends an entry below;
by the time the pipeline is complete, this file *is* the submission README
(setup & run, design decisions, classifier + evaluation, time spent — per the
completion gate). The original assessment brief is preserved verbatim at
[`docs/ASSESSMENT_BRIEF.md`](docs/ASSESSMENT_BRIEF.md) and isn't edited again.

Built stage by stage on purpose, closely following the brief's own
Part 1 (Crawl) / Part 2 (Transform + Load) / Part 3 (Classify + Summarize)
structure — no extra modules or invented scope beyond that.

## Status

- [x] Stage 0 — Design decisions + repo scaffold
- [ ] Stage 1 — Crawl (Extract)
- [ ] Stage 2 — Transform + Load
- [ ] Stage 3 — Classify
- [ ] Stage 4 — Evaluate
- [ ] Stage 5 — Summarize + completion gate hardening
- [ ] Stage 6 — Stretch goals (optional)

## Quick start (current state)

```bash
pip install -r requirements.txt
make run          # or: python -m pipeline
```

Right now `make run` only loads `config.yaml`, sets up logging, and
initializes the SQLite schema — crawl/classify/summarize are stubs (see
`pipeline/crawler/`, `pipeline/classify/`, `pipeline/evaluate/`). This section
gets rewritten as each stage lands so it always reflects what actually runs.

## Design decisions (Session 0)

### Source: HN Algolia (`hn.algolia.com/api/v1/search`)

The brief's recommended default: no auth, real JSON pagination, generous rate
limits. Reddit's public `.json` endpoints were considered (closer to "real
consumer chatter") but ruled out — Reddit has tightened unauthenticated API
access hard since 2023, which is a bad bet for a single-source, ~1-day build.

### Topics (config-driven, see `config.yaml`)

Zocket's own case studies are framed around real consumer brands across a
handful of industries (a regional bank pre-testing campaign messaging is one
of their published examples). These 5 topics mirror that spread — one brand
per vertical, each with enough real online chatter to crawl:

| Topic | Vertical | Why |
|---|---|---|
| Chime | Financial Services | Neobank with heavy, polarized chatter (no-fee praise vs. account-freeze complaints) — a crawlable stand-in for "regional bank" style case studies. |
| Oatly | FMCG / CPG | Plant-based FMCG brand with a genuinely mixed public reaction to its own marketing (Super Bowl ad backlash, sustainability claims). |
| Allbirds | Retail / D2C | D2C retail brand frequently used as a marketing case study; post-IPO chatter gives real sentiment range. |
| Noom | Healthcare / Wellness | Wellness/subscription app with strong, split sentiment (weight-loss marketing vs. subscription/cancellation complaints). |
| Rivian | Automotive | EV brand with active product + business-news discussion. |

### Storage: SQLite (`data/processed/consumer_research.db`)

Single `mentions` table (schema in `pipeline/storage/db.py`), columns
matching the brief directly: id, topic, source, author, title, text, url,
created_at, fetched_at, plus sentiment/category. The source-provided id (HN
object id) is the `PRIMARY KEY` — a second crawl inserts nothing new for
records already seen (`INSERT OR IGNORE` / upsert, implemented in Stage 2),
which is what makes re-runs idempotent.

### Classification plan (locked now, implemented in Stage 3)

- **Sentiment** — VADER (off-the-shelf, allowed by the brief; training a
  custom model is explicitly out of scope). Standard compound-score
  thresholds: `>= 0.05` positive, `<= -0.05` negative, else neutral, run
  against `title + text`.
- **Category** — a small keyword-based taxonomy (`config.yaml`
  `classification.categories`): Product Experience, Pricing & Subscription,
  Customer Service & Trust, Marketing & Advertising, Company & Business News,
  General/Other. Picked to fit how people actually talk about consumer
  brands, not a generic dev-tool taxonomy.
- **Evaluation (Stage 4)** — hand-label ~25 items, report accuracy + a
  confusion matrix + a short written failure analysis.

### Reliability score (locked now, computed in Stage 2)

One field beyond the brief's literal ask: `reliability_score` (0.0–1.0),
a rule-based (no ML) proxy for signal quality using HN's own points and
comment count — so a 0-point drive-by comment doesn't get weighted the same
as a heavily upvoted, heavily discussed post. In a consumer-research context
this matters: an analyst reading "sentiment on Chime is negative" should be
able to tell that from one angry outlier vs. from a post the community
actually piled onto. Formula (`config.yaml` `reliability:`):

```
score = min(points / 100, 0.6) + min(num_comments / 50, 0.2) + (0.2 if has_text else 0.0)
```

Column + config are added now so the schema is ready; the actual math is
written in Stage 2, once `points`/`num_comments` are actually coming out of
the crawler.

### Logging

Structured JSON logs (`pipeline/logging_setup.py`) via the standard library's
own `extra=` mechanism — no custom wrapper classes.

## Repo structure

```
config.yaml                    topics, source, storage, classification taxonomy — all config-driven
docs/ASSESSMENT_BRIEF.md       original assessment brief, verbatim, untouched
pipeline/
  config.py                    loads + validates config.yaml
  logging_setup.py             structured JSON logging
  __main__.py                  `python -m pipeline` entry point
  crawler/                     Stage 1 — HN Algolia client (not yet implemented)
  storage/db.py                SQLite schema (`mentions` table) — implemented
  classify/                    Stage 3 — sentiment.py, category.py (not yet implemented)
  evaluate/                    Stage 4 — compares against hand-labeled sample (not yet implemented)
data/raw/                      persisted raw payloads (gitignored, regenerable via `make run`)
data/processed/                SQLite db (gitignored during dev, revisit at Stage 5)
eval/                          hand-labeled sample lands here in Stage 4
```

## Stage plan (what's next)

1. **Crawl** — HN Algolia client: pagination, throttle + jitter, exponential
   backoff on transient failures, raw payload persisted before any transform,
   skip-if-already-fetched caching.
2. **Transform + Load** — normalize into the `mentions` schema, dedupe on id,
   idempotent upsert into SQLite, prove a second run is a fast no-op.
3. **Classify** — implement VADER sentiment + keyword category tagger.
4. **Evaluate** — hand-label ~25 items, accuracy + confusion matrix + failure
   analysis.
5. **Summarize + completion gate hardening** — emit the analyst summary
   (totals, dedup counts, category counts, sentiment breakdown per topic, top
   items per topic), confirm the completion gate end to end (clean clone,
   single command, run-twice-no-dupes), finalize this README.
6. **Stretch** (time permitting, only if the gate is already solid).

## Session Log

### Session 0 — 2026-07-25 — Design decisions + repo scaffold

- Read the assessment brief in full; preserved it verbatim at
  `docs/ASSESSMENT_BRIEF.md` so this file can become the living log without
  losing the original spec.
- Locked design decisions: source = HN Algolia; topics = Chime, Oatly,
  Allbirds, Noom, Rivian (one per vertical Zocket's own case studies target);
  storage = SQLite; classification = VADER + a keyword taxonomy fit to
  consumer-brand chatter.
- Scaffolded the repo: `config.yaml`, the `pipeline/` package (config loader,
  logging, SQLite schema — all real code, not placeholders),
  `Makefile`/`requirements.txt`, and the `docs/ASSESSMENT_BRIEF.md` split.
- Revised mid-session: first draft leaned on personal-project brands
  (Cloudflare/Stripe) and over-built the scaffold (a custom logging adapter,
  extra schema columns not asked for by the brief). Swapped topics for real
  consumer brands modeled on Zocket's own case studies, and trimmed the
  scaffold back to just what each stage actually needs.
- Added `reliability_score` (points/comments-based, rule-based, no ML) to
  the schema + config as a v1 signal-quality proxy — column and formula
  locked now, actual computation deferred to Stage 2 once the crawler is
  producing real points/num_comments data.
- Verified `python -m pipeline` runs end to end against the current stubs
  (loads config, initializes the schema, logs status as JSON).
- Time spent: `TODO — log actual hours here`.
- Next session: Stage 1 — implement the HN Algolia crawler.
