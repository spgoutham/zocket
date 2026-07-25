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
- [x] Stage 1 — Crawl (Extract)
- [x] Stage 2 — Transform + Load
- [ ] Stage 3 — Classify
- [ ] Stage 4 — Evaluate
- [ ] Stage 5 — Summarize + completion gate hardening
- [ ] Stage 6 — Stretch goals (optional)

## Quick start (current state)

```bash
pip install -r requirements.txt
make run          # or: python -m pipeline
```

Right now `make run` loads `config.yaml`, sets up logging, initializes the
SQLite schema, crawls all 5 topics from HN Algolia into
`data/raw/<topic>/q<N>/page_M.json` (real network calls the first time; a
second run makes zero network calls because every page is already cached),
then normalizes + loads every crawled hit into
`data/processed/consumer_research.db`'s `mentions` table (idempotent —
re-running inserts nothing new, see the Stage 2 section below). Classify/
summarize are still stubs (see `pipeline/classify/`, `pipeline/evaluate/`).
This section gets rewritten as each stage lands.

## Design decisions (Session 0 + Session 1)

### Source: HN Algolia (`hn.algolia.com/api/v1/search_by_date`)

The brief's recommended default: no auth, real JSON pagination, generous rate
limits. Reddit's public `.json` endpoints were considered (closer to "real
consumer chatter") but ruled out — Reddit has tightened unauthenticated API
access hard since 2023, which is a bad bet for a single-source, ~1-day build.
No `robots.txt` on this host (checked directly, 404) — it's a dedicated
public JSON API, not scraped HTML. Uses `search_by_date`, not the default
relevance-sorted `search`, because relevance order can reshuffle between
calls, which would break the "page N is already cached, skip it" assumption
the crawler's caching relies on.

### Topics (config-driven, see `config.yaml`)

Zocket's own case studies are framed around real consumer brands across a
handful of industries (a regional bank pre-testing campaign messaging is one
of their published examples). These 5 topics mirror that spread — one brand
per vertical, each with enough real online chatter to crawl:

| Topic | Vertical | Why |
|---|---|---|
| Chime | Financial Services | Neobank with heavy, polarized chatter (no-fee praise vs. account-freeze complaints) — a crawlable stand-in for "regional bank" style case studies. Also, unintentionally, this session's hardest data-hygiene problem — see below. |
| Oatly | FMCG / CPG | Plant-based FMCG brand with a genuinely mixed public reaction to its own marketing (Super Bowl ad backlash, sustainability claims). |
| Allbirds | Retail / D2C | D2C retail brand frequently used as a marketing case study; post-IPO chatter gives real sentiment range. |
| Noom | Healthcare / Wellness | Wellness/subscription app with strong, split sentiment (weight-loss marketing vs. subscription/cancellation complaints). |
| Rivian | Automotive | EV brand with active product + business-news discussion. |

### Query-precision finding: "Chime" (Stage 1)

The first real crawl of `Chime` came back **80/80 items about Chinese AI
policy**, not the neobank. Root-caused by inspecting the actual crawled
titles (not assumed):

1. Algolia's typo tolerance treats `Chime` and `Chine[se]` as a 1-edit
   match (`m`↔`n`), and HN currently has a flood of "Chinese AI" stories —
   completely swamping the real signal.
2. Unquoted, Algolia also treats the last word of a query as a *prefix*
   match, so `Chime` was separately matching `Chimera` (as in Chimera Linux).

**Fix, applied to every topic's query, not just this one:** quote the query
(`"Chime"` — whole-word match, no prefix-stemming) and pass
`typoTolerance: false` (now `source.typo_tolerance` in `config.yaml`). That
alone got Oatly/Allbirds/Noom/Rivian to clean results. Chime needed one more
round: even quoted and typo-strict, it still collided with a **defunct
Amazon product** (`"Amazon shuts down Chime, its Zoom alternative"`), a
**macOS app** of the same name, and the literal **notification-chime sound**
— genuine word collisions, not a query bug.

Tried excluding the obvious collisions (`-Amazon -AirPods -Wind`) — barely
moved the needle (383→347 hits), because most of the noise wasn't those
specific collisions, it was "chime" the common word appearing incidentally
in unrelated posts' body text. What actually worked: **requiring a second,
disambiguating word** (Algolia treats extra bare words as required, not just
a ranking boost — confirmed empirically: adding `bank` cut 383 hits down to
18, and every one of those 18 was genuinely about Chime-the-company).

That led to a small, reusable pattern rather than a one-off hack: a topic
can now have **multiple query variants** (`config.yaml` `topics[].queries`,
a list instead of a single string). `fetch_topic()` runs each variant,
caches its pages separately (`data/raw/<topic>/q<N>/`), and merges the
results by HN's own `objectID` so a story matching more than one variant
only counts once. Chime ended up with two variants — `"Chime" bank` and
`"Chime" fintech` — chosen for coverage (18 + 7 hits, 3 overlap → 22 unique,
all but a handful directly about the company; the rest are legitimate
comparison mentions, e.g. "how did companies like Stripe and Brex start,"
not noise). 22 is below the 80-item ceiling for this topic — same
"ceiling, not quota" tradeoff already accepted for Oatly (27) and Noom (37):
fewer clean records beats more polluted ones. This is a v1 — two variants,
not an exhaustive search for every disambiguating word; more could be added
later if more recall is needed.

### Crawler mechanics (Stage 1, `pipeline/crawler/hn_algolia.py`)

- **Politeness** — every real request sleeps `min_delay_seconds` + random
  jitter first (`_throttle`); cache hits don't sleep, since they make no
  network call at all. A dedicated `User-Agent` identifies the crawler and
  a contact address.
- **Resilience** — timeouts/connection errors and HTTP 429/5xx are treated
  as transient and retried with exponential backoff (`base * 2^attempt`,
  capped); anything else (a 4xx from a malformed request) fails fast instead
  of retrying something that will never succeed. Verified for real, not just
  read: pointed the client at an unresolvable host and confirmed the log
  shows two backoff attempts (1.0s, then 2.0s) before it raises.
- **Persist-before-transform + caching** — each page's *entire, untouched*
  API response is written to `data/raw/<topic>/q<N>/page_<M>.json` before
  anything is parsed. If that file already exists on a later run, it's read
  from disk instead of re-fetched — confirmed: a full 5-topic re-run after
  the first crawl took 0.25s and made zero HTTP requests, vs. ~30s for the
  first real crawl.

### Transform (Stage 2, `pipeline/transform.py`)

Reads raw hits back from the `data/raw/` files Stage 1 wrote — not Stage 1's
in-memory return value — so this stage can be re-run, or run standalone,
without a crawl having just happened in the same process.

- **`fetched_at` is the raw page file's own mtime**, not "now." If
  `fetched_at` were stamped at transform time, it would be wrong for any
  record served from Stage 1's cache (i.e. most records on any re-run) —
  the mtime is the moment that data was actually fetched, and it stays
  correct no matter how many times the pipeline reruns afterward.
- **Text cleaning was a real finding, not a guess.** HN's `story_text` is
  HTML (`<p>` breaks, `&#x27;`-style escaped entities) — confirmed by
  inspecting real crawled records, several of which had literal `<p>` tags
  and `&#x27;`/`&amp;` sequences in the body. Both `title` and `text` are
  HTML-unescaped and tag-stripped before storage, since leftover markup
  would otherwise pollute Stage 3's sentiment scoring.
- **`reliability_score` is now real math**, not just a locked column: `score
  = min(points/100, 0.6) + min(num_comments/50, 0.2) + (0.2 if body text
  present else 0.0)`, per `config.yaml` `reliability:`.
- **Sane handling of missing fields, caught by actually looking at the
  data**: HN's own API is inconsistent about "no url" — sometimes the key
  is simply absent, sometimes it's a literal `""`. Found by querying the
  loaded DB (`WHERE url = ''` returned 3 rows even though the crawler never
  writes empty strings on purpose) and fixed by collapsing both cases to a
  single `NULL` rather than storing "no url" two different ways. Separately,
  a hit missing `objectID` or `created_at` (fields with no sane default) is
  logged and skipped rather than inserted broken or crashing the run —
  verified with a synthetic malformed hit, not just written and trusted.

### Storage + Load: SQLite (`data/processed/consumer_research.db`)

Single `mentions` table (schema in `pipeline/storage/db.py`), columns
matching the brief directly: id, topic, source, author, title, text, url,
created_at, fetched_at, plus sentiment/category. The source-provided id (HN
object id) is the `PRIMARY KEY` — `upsert_mentions()` does a plain
`INSERT OR IGNORE`, so the primary key itself is the entire dedup mechanism,
no application-level "have I seen this id before" logic needed. Proven, not
assumed: running the full pipeline twice against the same cached raw data
recomputed the same normalized record counts both times (e.g. 25 for Chime,
across its two query variants) but inserted 0 new rows on the second run —
`total_mentions` stayed at 240 both times.

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

Implemented in Stage 2 (`pipeline/transform.py`'s `compute_reliability()`) —
see the Transform section above for the real numbers.

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
  crawler/hn_algolia.py        Stage 1 — HN Algolia client — implemented
  transform.py                 Stage 2 — normalize + reliability_score — implemented
  storage/db.py                SQLite schema + upsert_mentions() — implemented
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

### Session 2 — 2026-07-25 — Transform + Load

- Built `pipeline/transform.py`: reads raw hits back from `data/raw/` (not
  Stage 1's in-memory return value, so this stage is independently
  re-runnable), cleans HTML out of `title`/`text` (a real finding —
  `story_text` came back with literal `<p>` tags and `&#x27;`-style
  entities in several crawled records), and computes the real
  `reliability_score` from each hit's `points`/`num_comments`.
- `fetched_at` is the raw page file's mtime, not "now" — so it stays correct
  even for records served from Stage 1's cache on a later run, instead of
  getting re-stamped with today's date every time the pipeline reruns.
- Added `upsert_mentions()` to `pipeline/storage/db.py`: a plain
  `INSERT OR IGNORE` against the `id` primary key. No app-level dedup logic
  — the schema itself is the entire idempotency mechanism.
- Caught a second data-hygiene issue by querying the loaded DB rather than
  assuming it was clean: HN's API sometimes omits `url` entirely and
  sometimes sends back a literal `""` — both mean "no url," but were being
  stored as two different values. Fixed by collapsing both to `NULL`.
- Verified a malformed hit (missing `objectID`) is logged and skipped
  rather than crashing the run or inserting a broken row.
- Proved idempotency, not just claimed it: ran the full pipeline twice —
  same normalized record counts both times (e.g. 25 for Chime, across its
  two query variants), 0 new inserts the second time, `total_mentions`
  stayed at 240.
- Corrected a small inaccuracy from the Session 1 log: Chime's two query
  variants were said to overlap by 1 record; the real number, visible once
  Stage 2 actually merged them, is 3 (18 + 7 − 22 unique).
- Time spent: `TODO — log actual hours here`.
- Next session: Stage 3 — Classify (VADER sentiment + keyword category
  tagger).

### Session 1 — 2026-07-25 — Crawl (Extract)

- Verified the API before writing any parsing code: no `robots.txt` on
  `hn.algolia.com` (404), and pulled real responses to confirm field shapes
  (`objectID`, `story_text` only present on self-posts, etc.) rather than
  guessing them.
- Built `pipeline/crawler/hn_algolia.py`: throttle+jitter before every real
  request, exponential backoff on transient failures (timeouts/connection
  errors/429/5xx), persist-raw-payload-before-transform with per-page disk
  caching. Verified the retry path fires for real (pointed it at an
  unresolvable host, watched the two backoff attempts in the logs) and that
  a full re-crawl after caching takes 0.25s and zero network calls, vs. ~30s
  cold.
- Ran the crawl for real against all 5 topics — then caught a serious data
  hygiene problem: `Chime` came back 80/80 items about Chinese AI policy,
  not the neobank (see the design-decisions writeup above for the full
  root-cause chain: typo-tolerance + prefix-matching, then a genuine
  3-way word collision with Amazon Chime / a macOS app / the literal sound).
  Fixed generally (quoted queries + `typoTolerance: false` for every topic)
  and specifically for Chime (multi-query-variant crawling: `topics[].queries`
  is now a list, merged by `objectID`) rather than swapping the topic away
  from the problem.
- Re-crawled clean: Chime 22 items (from 0 relevant), Oatly 27, Allbirds 74,
  Noom 37, Rivian 80 — 240 total, well under the ~500 ground rule.
- Time spent: `TODO — log actual hours here`.
- Next session: Stage 2 — Transform + Load (normalize into `mentions`,
  compute `reliability_score`, dedupe on id, idempotent upsert into SQLite).

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
