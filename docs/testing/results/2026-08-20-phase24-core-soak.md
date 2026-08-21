# PaperFlow Phase 24 Core Soak Report

- Date: 2026-08-20 (America/New_York)
- Baseline commit: `4ed9472`
- Figures configuration: `enabled=false`, placeholder contract retained
- External billing: no OpenRouter calls; deterministic injectable clients only
- Checked-in recurring schedule: disabled
- Isolated soak schedule: enabled and synchronized only inside the temporary test project

## Result

PASS — five consecutive due local-date runs completed without manual repair. The
repository validator passed after the fifth run. No duplicate canonical IDs, missed
eligible retries, partial publication, count mismatch, state loss, or unexplained
usage/cost variance was observed.

The paid recurring-production activation observation remains intentionally deferred
by the owner's instruction not to enable the daily schedule. This report validates
the same due gate, DST-generated cron candidate, pipeline, persistence, rendering,
and validation path with deterministic network/LLM fixtures.

## Run evidence

| Local date | Source | Fetched / deduplicated | KEEP / DROP / FAILED | Summaries generated / failed | Expected fixture cost | Result |
|---|---|---:|---:|---:|---:|---|
| 2026-08-20 | complete | 12 / 10 | 3 / 6 / 1 | 2 / 1 | $0.002080 | success |
| 2026-08-21 | failed paper absent; metadata refetched from backlog | 11 / 9 | 1 / 0 / 0 | 2 / 0 | $0.001080 | success |
| 2026-08-22 | complete after same-date source-failure drill | 11 / 9 | 0 / 0 / 0 | 0 / 0 | $0.000000 | success |
| 2026-08-23 | complete | 11 / 9 | 0 / 0 / 0 | 0 / 0 | $0.000000 | success |
| 2026-08-24 | complete | 11 / 9 | 0 / 0 / 0 | 0 / 0 | $0.000000 | success |

The first run's deliberately invalid filter result remained FAILED after semantic
retry. On the next date that paper was absent from the source, selected from the
eligible FAILED backlog, refetched through the injectable metadata boundary, and
received a later KEEP event. Both ledger events remained present. A summary failed
both semantic attempts on the first date, remained selected with abstract fallback,
and generated successfully on the second date.

Before the 2026-08-22 success, a complete source failure was injected at the due
time. Canonical papers, run state, feed index, website root, and README remained
byte-identical. The same local date then succeeded through the configured catch-up
path. The five persisted run-stat dates were 2026-08-20 through 2026-08-24.

## Validation evidence

- Focused soak: `pytest -q tests/integration/test_full_pipeline.py` — 2 passed.
- Python regression: 287 passed, 4 explicit paid live tests skipped.
- Ruff: passed.
- Taxonomy validation: version 1, 7 topics, 20 subtopics; passed.
- Full repository validation: passed; canonical and generated memberships matched.
- Rebuild dry-run: zero changes and zero stale removals.
- iOS unit suite: 75 passed.
- iOS UI suite: 11 passed, including cached offline Saved/personal actions.
- Simulator scheme build: passed on iPhone 16 Pro / iOS 18.3.1.
- GitHub Pages: site, feed index, and topics returned HTTP 200; private state returned 404.
- Physical owner device: signed build installed and launched on the connected iPhone 13.

No UI source changed in Phase 24. Existing Phase 20/21 UI-test captures cover the
Saved offline, accessibility, Today, Topics, Swipe, and restoration paths exercised
by the regression. A physical-device two-output offline Save drill was not fabricated;
the automated simulator equivalent passed and the owner confirmed the installed app
was open.

Signed-off-by: Codex
