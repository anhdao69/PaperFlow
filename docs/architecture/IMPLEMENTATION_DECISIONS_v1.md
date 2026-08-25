# PaperFlow V1 Implementation Decisions

- Status: accepted, as built
- Updated: 2026-08-25
- Technical contract: `../specification/PaperFlow_Technical_Plan_v1.md`

This file records decisions that materially shape the production system. It is
normative when an older phase plan or status note describes a superseded state.

## D-001 — Static public architecture

**Decision:** Build and validate content in GitHub Actions, commit generated
artifacts to the repository, and publish an allowlisted static site/feed with
GitHub Pages.

**Reason:** The public feed is read-only, inexpensive to operate, cacheable, and
requires no always-on backend or credential-bearing mobile client.

**Consequence:** GitHub is the public source of truth. iPhone personal state is
not written back to GitHub.

## D-002 — Public and personal state remain separate

**Decision:** Public paper metadata is downloaded and cached as files. Seen,
saved, notes, rating, reading status, and saved snapshots live only in SwiftData
on the iPhone.

**Reason:** Personal reading behavior must remain private and usable offline.

**Consequence:** Removing/rebuilding public feeds does not reset reviewed or
saved state. Deleting app data does. V1 has no CloudKit or account sync.

## D-003 — Canonical identity is versionless arXiv ID

**Decision:** Normalize `2608.20318v2` and `2608.20318` to one canonical ID for
pipeline deduplication and iPhone state.

**Reason:** Revised arXiv versions and appearances in multiple topic/day feeds
are the same research paper for triage purposes.

**Consequence:** Reviewed progress is global per paper. It does not reset merely
because a new feed was generated.

## D-004 — Daily execution is 9:00 PM New York time

**Decision:** Configure `21:00` in `America/New_York`, generate both possible UTC
cron candidates, serialize them, explicitly check out the latest `main` after
the concurrency wait, and enforce an application-level due/already-succeeded
gate against that current state.

**Reason:** GitHub cron is UTC and cannot itself preserve a local wall-clock
time across daylight-saving transitions.

**Consequence:** Both 01:00 and 02:00 UTC triggers exist, but at most one normal
run succeeds per New York local date. A queued trigger cannot repeat work from
its stale event SHA after the preceding trigger publishes. Manual dispatch
bypasses the due gate.

## D-005 — OpenRouter is the only LLM boundary

**Decision:** Filtering and summary code call one injectable OpenRouter
abstraction using model chains from `configs/models.yaml`.

**Reason:** Centralized retries, structured-output validation, usage accounting,
model fallback, and secret redaction are easier to test and audit.

**Consequence:** `OPENROUTER_API_KEY` is a GitHub repository secret and never
ships in iOS.

## D-006 — PDFFigures2 is the V1 extractor

**Decision:** Use only AllenAI PDFFigures2 at pinned revision
`3d7ad46753d4a315cccd1c2bcab398380e88c534`, built with Java 17 in the daily
workflow. Docling remains evaluation-only.

**Reason:** The owner selected PDFFigures2 after a five-paper side-by-side pilot;
it produced useful figure/table coverage at substantially lower runtime in that
sample.

**Consequence:** Hero choice is deterministic and introduces no figure-selection
LLM call. All usable crops are published. Per-paper failure falls back to a
placeholder and does not fail the complete daily run.

This decision is also recorded by `decisions/ADR-0001-figure-extractor.md`. The
2026-08-20 blocked evaluation note is historical and superseded.

## D-007 — Taxonomy is configured data with explicit migrations

**Decision:** Author topics, subtopics, include/exclude guidance, names, and SF
Symbol icons in `configs/topics.yaml`. Require version increments and explicit
`previous_ids`/`moved_from` metadata for identity or parent changes.

**Reason:** The taxonomy must evolve without silently corrupting historical
assignments or requiring SwiftUI changes.

**Consequence:** Additions affect future filtering. Presentation-only edits keep
assignments. In-use removals without a destination block publication. Valid
renames and moves rewrite canonical assignments before stale generated paths
are cleaned.

## D-008 — Publication is staged, validated, and conservatively cleaned

**Decision:** Render public outputs into staging, validate exact JSON contracts,
atomically replace accepted files, and remove only recognized generated stale
paths after validation.

**Reason:** The public app/feed must never observe partially written or malformed
canonical files.

**Consequence:** A failed workflow creates no generated commit; the prior Pages
deployment remains usable. A successful daily workflow triggers Pages through
`workflow_run`; publication does not depend on the generated commit's
`GITHUB_TOKEN` push starting another push-triggered workflow.

## D-009 — Saved papers carry persistent local snapshots

**Decision:** On first save, store a `SavedPaperSnapshot` related to the unique
personal paper state.

**Reason:** A deep-reading paper must remain available when its originating day
falls out of the downloaded public cache or a topic is later removed.

**Consequence:** Saved metadata persists through ordinary feed refreshes and app
launches. It is device-local and can retain historical topic labels until
explicitly refreshed from current public metadata.

## D-010 — Reviewed means an explicit Save or Skip decision

**Decision:** Save and Skip both mark the canonical paper seen. Opening detail
does not. Swipe defaults to unreviewed papers and provides an All Papers mode.

**Reason:** Progress should represent completed triage decisions and remain
consistent across Today, Topics, Browse, and Swipe.

**Consequence:** A new daily run can display an existing reviewed count when its
papers overlap papers already reviewed elsewhere. This is expected, not data
copied from GitHub.

## D-011 — Swipe dedicates the viewport to the paper card

**Decision:** Use one centered date in the navigation bar, a chevron-only back
button, top-right undo/filter icons, compact textual progress, a 320-point
figure area, and no bottom Skip/Save/Undo action bar.

**Reason:** The paper figure, title, tags, and summary are the primary decision
surface on an iPhone.

**Consequence:** Triage remains gesture-driven. Undo remains discoverable in the
top bar, and accessibility identifiers remain on navigation controls.

## D-012 — Paper Detail is reusable and figures are zoomable

**Decision:** Keep one `PaperDetailView` implementation for every entry route.
Publish a carousel of extracted figures and open a tapped figure in a
full-screen pinch/pan zoom surface.

**Reason:** Browse, Swipe, Topics, and Saved should expose identical paper
content and interaction semantics.

**Consequence:** Figure metadata is part of both the public paper contract and
the saved snapshot contract.

## D-013 — Topic icons are public taxonomy metadata

**Decision:** Store SF Symbol names on topic records and render a safe fallback
when an icon is absent.

**Reason:** Adding or changing a topic should not require a new hard-coded icon
switch in the app.

**Consequence:** Icons update with the public taxonomy feed after publication.

## D-014 — Website figures resolve from the publication root

**Decision:** Convert stored relative figure paths to publication-root-aware
URLs when rendering nested website pages.

**Reason:** A path that works at the Pages root otherwise breaks under day,
topic, and subtopic route depth.

**Consequence:** The website and iPhone consume the same figure assets without
duplicating image files.

## D-015 — V1 is owner-only, direct from Xcode

**Decision:** Do not add accounts, analytics, CloudKit, TestFlight/App Store
automation, or distribution credentials to V1. Install the app from the shared
Xcode project on the owner's iPhone.

**Reason:** The present product is a private single-owner research workflow.

**Consequence:** The daily content pipeline is fully automatic, while installing
a changed binary or renewing a development install remains an owner/Xcode task.

## Current implementation status

All V1 decisions above are implemented in the checked-in Python pipeline,
workflows, public contracts, generated website, and SwiftUI/SwiftData app. The
latest checked-in production feed contains 127 papers across eight topics and
uses PDFFigures2 extraction. Real Simulator evidence is in `../ui/real/`.

Remaining limitations are product boundaries rather than incomplete V1 steps:
no cloud personal-state backup, no background push refresh, no public app-store
distribution, and no automatic retroactive classification when a new taxonomy
topic is introduced.
