Intern Assessment — Consumer Research Data Track
Task: Build a small end-to-end pipeline that crawls public text data, runs it through a
repeatable pipeline, and classifies it.
Role context: Consumer Research / Data + AI (backend-leaning IC).
Target effort: ~1 focused working day for the core task (6–8 hrs). Stretch goals are optional.
Language/stack: Python preferred (use what you're fastest in). No paid services required.
How you'll be judged: completion first, then quality. A working, re-runnable pipeline that does
less beats an ambitious one that doesn't run. See the Completion Gate below.
The scenario
You've joined the Consumer Research team. We continuously pull what people say online about
a set of topics/brands, land it in a clean store, and enrich it so analysts can answer "what's the
conversation, and is it positive or negative?"
Your task is a miniature of that: pick 3–5 topics (product names, brands S, or subjects — your
choice), crawl public mentions of them, land them in a tidy store, and classify each record
by sentiment and category/topic. Then produce a small summary an analyst could read in 30
seconds. This is deliberately small in scope — we care far more about how you build it than how
much you build.
What we're evaluating
1. Pipeline thinking — config-driven, idempotent, re-runnable, resilient to failure?
2. Crawling discipline — rate limits / robots / ToS respected, pagination correct, flaky
responses handled?
3. Data hygiene — clear schema, dedupe, sane handling of missing fields.
4. Classification judgment — a sensible, explainable method and a real (even tiny)
evaluation of it — not just a library call.
5. Communication — a README explaining what you did, why, and the tradeoffs you
made under time pressure.
The task
Part 1 — Crawl (Extract). Pull public mentions for your 3–5 topics from one ToS-friendly source.
 Topics are configured, not hard-coded (config.yaml/.json or CLI args).
 Handle pagination for a reasonable sample per topic (aim ~50–150 items/topic; total ≤
~500).
 Be a polite crawler: throttle (rate limit), set a sane User-Agent, honor robots/ToS, retry
transient failures with backoff.
 Persist the raw payload before transforming (so a re-run needn't re-crawl). Cache/skip
already-fetched items.
Source (pick one) Why Notes
Hacker News Algolia
No auth, JSON, real
Recommended default — least
API (hn.algolia.com/api/v1/search)
pagination + rate limits.
fiddly.
Purpose-built scraping
Use to show parsing over API
quotes.toscrape.com / books.toscrape.com
sandboxes; tests HTML
consumption.
parsing.
Reddit public
Closest to real consumer
Rate-limited & picky; set a
JSON (reddit.com/search.json?q=…)
chatter.
User-Agent, throttle hard.
You may propose your own public, no-auth, ToS-permitted source — just justify it in the
README. Do not scrape anything behind a login, paywall, or an explicit robots.txt disallow.
Part 2 — Pipeline (Transform + Load).
 Normalize into a defined schema, e.g. id (stable, source-
provided), topic, source, author, title/text, url, created_at, fetched_at, plus
your classification fields.
 Dedupe on the stable id.
 Idempotent & incremental: running twice must not create duplicate rows or re-do
finished work. A second run on the same config should be a fast no-op (or only fetch
what's new).
 Land it in a simple store: SQLite (recommended), or Parquet/CSV.
Structured logging and basic error handling throughout.
Part 3 — Classify + Summarize.
 Add two labels per record: Sentiment (positive/negative/neutral) and a Category/topic
label (a small taxonomy you define).
 Use a transparent, reproducible method (keyword rules, a small model like VADER, etc.).
Explain it in the README.
 Evaluate it, even minimally: hand-label ~20–30 items, compare against your classifier,
report rough accuracy + where it fails. This is the part most candidates skip — don't.
 Emit a summary (Markdown or JSON): total crawled vs. deduped, counts by category,
sentiment breakdown per topic, top few items per topic.
Completion Gate (what "done" means)
Your submission is complete only if all of these are true. We check these before scoring quality:
 ☐ Runs from a clean clone with documented setup (≤ a few commands).
 ☐ One command runs the whole pipeline end-to-end (e.g. make run or python -m
pipeline).
 ☐ Produces a stored dataset with records across ≥ 3 topics, plus the summary output.
 ☐ Every record has a sentiment and a category label.
 ☐ Re-running does not duplicate data (prove it: run it twice, show the counts).
 ☐ README covers setup & run, design decisions, your classifier + its evaluation, and how
long you spent.
Miss the gate and the task reads as incomplete regardless of how polished individual pieces are
— so wire the whole thing together early, then improve.
Out of scope (please do NOT build)
 No web UI / dashboard / frontend.
 No deployment, Docker, cloud infra, or CI setup.
 No user auth, no multi-source crawling, no distributed anything.
 No training your own ML model — a rules-based or off-the-shelf classifier is expected.
If you find yourself building any of the above, stop and spend that time on the Completion Gate
and README instead.
Deliverables & how to submit
 A Git repository (a GitHub link is easiest).
 README.md as described above, plus requirements.txt/pyproject.toml and a
single run command.
 The generated dataset + summary committed (or a one-command way to regenerate
them).
 A short screen recording (≤ 5 min) walking through: running it end-to-end, the output,
and a re-run showing no duplicates.
Process-fit bonus (optional, unscored but noticed): deliver on a sensibly named feature
branch (e.g. feat/crawl-pipeline) with a PR description explaining what and why.
Ground rules
 Keep the crawl small and polite (≤ ~500 items total, throttled). This is a skills test, not a
load test.
 Only public, no-auth, ToS-permitted data. When unsure, pick a gentler source and note it.
 Use libraries freely (requests/httpx, beautifulsoup4, pandas, vaderSentiment,
etc.). AI coding assistants are fine — but you must understand and be able to defend
every line; we'll ask.
 Timebox honestly. If you run out of time, ship what passes the gate and write down what
you'd do next. We reward good tradeoff calls under time pressure.