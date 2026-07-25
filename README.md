# Zocket Intern Assessment — Consumer Research Data Pipeline

This README is a running **session log**. Each session appends an entry below;
by the time the pipeline is complete, this file *is* the submission README
(setup & run, design decisions, classifier + evaluation, time spent — per the
completion gate). The original assessment brief is preserved verbatim at
[`docs/ASSESSMENT_BRIEF.md`](docs/ASSESSMENT_BRIEF.md) and isn't edited again.

Built stage by stage, on purpose: the goal isn't just a passing submission,
it's using this assessment as a real entry point into AI/ML for marketing
research — so decisions get made deliberately and explained, not defaulted to.

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

Right now `make run` only loads `config.yaml`, sets up structured logging, and
initializes the SQLite schema — crawl/classify/summarize are stubs (see
`pipeline/crawler/`, `pipeline/classify/`, `pipeline/evaluate/`). This section
gets rewritten as each stage lands so it always reflects what actually runs.

## Why this task is framed this way

Zocket's own product is an "AI Marketing OS" with a **Consumer Research**
module — a "Brand Moderator" that monitors brand mentions and tracks
sentiment, sentiment velocity, and trend forecasting, explicitly aiming for
nuance beyond keyword-matching (sarcasm, brand-vs-category sentiment
divergence). This assessment is a miniature of exactly that. Rather than
build a generic crawl-and-classify exercise, the design decisions below try
to be a small, honest version of that same module — using their vocabulary
where it fits, not overclaiming what a toy pipeline can actually do.

## Design decisions (Session 0)

### Source: HN Algolia (`hn.algolia.com/api/v1/search`)

The brief's recommended default: no auth, real JSON pagination, generous rate
limits. **Reddit's public `.json` endpoints were considered** (closer to
"real consumer chatter") but ruled out — Reddit has tightened unauthenticated
API access hard since 2023, and a picky, rate-limited source is a bad bet for
a single-source, ~1-day-timeboxed build. Documenting it here as a
considered-and-rejected alternative rather than pretending it wasn't an
option.

### Topics (config-driven, see `config.yaml`)

| Topic | Query | Why this one |
|---|---|---|
| Cloudflare | `Cloudflare` | Trust/security infra brand — overlaps directly with my own bot-detection/fraud-prevention work (KaizoCore: XGBoost + Isolation Forest behavioral scoring). |
| Stripe | `Stripe` | Payments/fraud-adjacent infra — same domain overlap as above. |
| Shopify | `Shopify` | Martech/commerce brand — squarely the kind of customer Zocket itself serves. |
| Meta Ads | `Meta ads` | Marketing/ad platform — closest 1:1 match to what Zocket's Consumer Research module actually monitors for clients. |
| OpenAI | `OpenAI` | The AI thread tying the whole exercise together. |

Deliberately a blend: two topics lean into my own security/trust specialty,
two lean into Zocket's own marketing/ad-tech domain, one ties both to the
"AI/ML" framing of the internship itself.

### Storage: SQLite (`data/processed/consumer_research.db`)

Single `mentions` table (schema in `pipeline/storage/db.py`). The
source-provided id (HN object id) is the `PRIMARY KEY` — that's what makes
re-runs idempotent: a second crawl inserts nothing new for records already
seen (`INSERT OR IGNORE` / upsert, implemented in Stage 2), rather than
needing separate dedupe logic bolted on after the fact.

### Classification plan (locked now, implemented in Stage 3)

- **Sentiment** — VADER (off-the-shelf, explicitly allowed by the brief;
  training a custom model is explicitly out of scope). Standard compound-score
  thresholds: `>= 0.05` positive, `<= -0.05` negative, else neutral, run
  against `title + text`.
- **Category** — a small keyword-based taxonomy (`config.yaml`
  `classification.categories`): Product & Features, Pricing & Billing,
  Reliability & Incidents, Security & Trust, Business & Funding, Developer
  Experience, General/Other. Chosen because this is genuinely how HN chatter
  about these five brands splits, not a generic off-the-shelf taxonomy.
- **Explainability trace** — every classified record carries *why* it got its
  label (`category_reasoning` column: which keywords fired; the sentiment
  score itself), not just the label. This isn't required by the brief — it's
  carried over from the "explain every decision" instinct behind KaizoCore's
  real-time detection dashboard, applied here to a sentiment/category call
  instead of a bot-or-human call. A label an analyst can't audit isn't
  actually usable.
- **Evaluation (Stage 4)** — hand-label ~25 items, report accuracy + a
  confusion matrix + written failure analysis. Error review will be
  precision-weighted toward *not* mislabeling neutral/positive mentions as
  negative — the same false-positive-first instinct as fraud detection
  (wrongly flagging a real user costs more trust than missing a bot), applied
  here to "wrongly flagging a mention as negative costs an analyst's trust
  more than missing a subtle neutral one."

### Logging

Structured JSON logging everywhere (`pipeline/logging_setup.py`), with
per-call context (topic, page, counts) rather than free-text messages — so a
run's behavior is auditable from its logs alone, without re-running it.

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
3. **Classify** — implement VADER sentiment + keyword category tagger with
   the explainability trace described above.
4. **Evaluate** — hand-label ~25 items, accuracy + confusion matrix + failure
   analysis.
5. **Summarize + completion gate hardening** — emit the analyst summary
   (totals, dedup counts, category counts, sentiment breakdown per topic, top
   items per topic), confirm the completion gate end to end (clean clone,
   single command, run-twice-no-dupes), finalize this README.
6. **Stretch** (time permitting) — e.g. sentiment-velocity-over-time (a nod to
   Zocket's own "sentiment velocity" framing), PR description on a
   `feat/crawl-pipeline` branch.

## Session Log

### Session 0 — 2026-07-25 — Design decisions + repo scaffold

- Read the assessment brief in full; preserved it verbatim at
  `docs/ASSESSMENT_BRIEF.md` so this file can become the living log without
  losing the original spec.
- Researched Zocket's actual product (AI Marketing OS; Consumer Research
  module with a Brand Moderator, sentiment velocity, trend forecasting,
  synthetic focus groups) to frame this pipeline as a small, honest analog of
  that module rather than a generic take-home.
- Locked design decisions: source = HN Algolia; topics = Cloudflare, Stripe,
  Shopify, Meta Ads, OpenAI; storage = SQLite; classification = VADER +
  keyword taxonomy, both carrying an explainability trace.
- Scaffolded the repo: `config.yaml`, the `pipeline/` package (config loader,
  structured logging, SQLite schema — all real code, not placeholders),
  `Makefile`/`requirements.txt`, and the `docs/ASSESSMENT_BRIEF.md` split.
- Verified `python -m pipeline` runs end to end against the current stubs
  (loads config, initializes the schema, logs status as JSON).
- Time spent: `TODO — log actual hours here`.
- Next session: Stage 1 — implement the HN Algolia crawler.
