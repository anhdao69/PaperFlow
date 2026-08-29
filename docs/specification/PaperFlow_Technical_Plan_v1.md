# PaperFlow V1 Technical Plan

- Status: as-built product contract
- Product version: V1
- Updated: 2026-08-29
- Supersedes for implementation: `PaperFlow_Technical_Plan_v3_2.md`
- Decisions: `../architecture/IMPLEMENTATION_DECISIONS_v1.md`
- UI contract: `../ui/PaperFlow_UI_UX_SPEC.md`
- Real-app evidence: `../ui/real/2026-08-22-paperflow-four-screen.png`

## 1. Purpose

PaperFlow V1 is an owner-operated research-paper triage system. A scheduled
GitHub Actions pipeline discovers new arXiv papers, applies the configured
taxonomy, generates structured summaries, extracts figures, validates a public
read-only feed, and publishes a website. The SwiftUI iPhone app consumes that
feed and stores the owner's private reading activity locally with SwiftData.

This document describes the implementation that exists now. The older v3.2
document remains historical planning context; unchecked future-plan items in
that file are not V1 commitments unless they also appear here.

## 2. V1 scope and completion boundary

V1 includes:

- new-only arXiv ingestion for `cs.AI`, `cs.CV`, `cs.LG`, `cs.RO`, and `cs.CL`;
- deterministic normalization and versionless arXiv identity;
- structured OpenRouter filtering and summarization with configured fallbacks;
- a versioned, configurable topic/subtopic taxonomy with SF Symbol icons;
- deterministic taxonomy rename and re-parent migration validation;
- PDFFigures2 extraction, WebP conversion, hero selection, and figure galleries;
- validated JSON feeds, topic/day pages, and GitHub Pages publication;
- an iPhone app with exactly Today, Topics, and Saved tabs;
- browse, swipe triage, undo, filters, paper detail, figure carousel and zoom;
- local saved snapshots, notes, ratings, and Queue/Reading/Done state;
- offline use of the most recently cached public feed and saved snapshots;
- automated daily execution at 9:00 PM America/New_York.

V1 intentionally does not include accounts, CloudKit, cross-device personal
state sync, analytics, push notifications, App Store distribution, or API
secrets in the iPhone app. The owner installs the app directly from Xcode.

## 3. System architecture

```text
arXiv export API
      |
      v
GitHub Actions daily pipeline
  normalize -> filter -> summarize -> PDFFigures2 -> validate -> commit
      |                                                |
      |                                                v
      |                                      GitHub Pages public feed/site
      |                                                |
      +------------------------------------------------v
                                              SwiftUI iPhone app
                                              | public cache: files
                                              | private state: SwiftData
```

The public and personal data boundaries are deliberate:

| Data | Location | Mutable by iPhone | Public |
|---|---|---:|---:|
| Taxonomy source | `configs/topics.yaml` | No | Repository source |
| Runtime/model/prompt config | `configs/` | No | Repository source |
| Canonical selected papers | `data/papers.json` | No | Not deployed by Pages |
| Screening ledger and run state | `data/screening_events/`, `data/state.json` | No | Not deployed by Pages |
| Public feed contracts | `data/feed_index.json`, `data/topics.json`, `data/daily_feeds/`, `data/topic_feeds/` | No | Yes |
| Extracted figures | `figures/` | No | Yes |
| Rendered website | `site/` | No | Yes |
| Downloaded public cache | iPhone Application Support, `PaperFlow/PublicFeed` | Cache only | Private to device |
| Seen/saved/notes/rating/status | iPhone SwiftData store | Yes | No |
| Saved paper snapshot | iPhone SwiftData store | Yes | No |

The Pages workflow deploys only the site, public feed allowlist, and figures. It
does not deploy canonical pipeline state, logs, caches, credentials, or iPhone
personal state.

## 4. Configuration source of truth

### 4.1 Runtime

`configs/runtime.yaml` controls timezone, schedule, arXiv categories, retry and
concurrency limits, publication URL, figure settings, and observability.

The current production values are:

- timezone: `America/New_York`;
- schedule: every day at `21:00`, with same-day catch-up enabled;
- source mode: `new_only`;
- figures: enabled, extractor `pdffigures2`, concurrency 2;
- maximum figure long edge: 1600 pixels;
- WebP quality: 88;
- public root: `https://anhdao69.github.io/PaperFlow/`.

### 4.2 Taxonomy

`configs/topics.yaml` is the only authored taxonomy. Topic and subtopic rows in
the app and website are data-driven; they must not be hard-coded in SwiftUI.

The current taxonomy is version 2 with eight topics and 23 subtopics:

| Topic | Icon | Subtopics |
|---|---|---:|
| Embodied AI | `figure.walk` | 5 |
| World Models | `globe.americas.fill` | 3 |
| Multimodal Foundation Models | `eye.fill` | 2 |
| 3D Vision | `cube.transparent` | 1 |
| Video Generation and Understanding | `film.stack.fill` | 3 |
| Efficient AI | `bolt.fill` | 3 |
| Adaptation and Memory | `brain.head.profile` | 3 |
| Language Foundation Models | `text.bubble.fill` | 3 |

Every taxonomy edit increments `taxonomy_version`. Validation rejects duplicate
IDs, malformed IDs, missing descriptions, invalid migration declarations, and
assignments that cannot be represented by the new taxonomy.

### 4.3 Models and secrets

`configs/models.yaml` defines the OpenRouter model aliases and task fallback
chains. Filtering currently starts with DeepSeek; summarization starts with the
configured GPT model. Structured outputs are required.

`OPENROUTER_API_KEY` exists only as a GitHub Actions repository secret or a
developer-local environment variable. It is never serialized into generated
content, source control, logs, or the iOS binary.

## 5. Daily production workflow

The scheduled workflow is `.github/workflows/paperflow-daily.yml`.

1. GitHub starts off-the-hour UTC retry candidates from 01:17 through 05:17.
   Their union covers four retry windows beginning shortly after 9:00 PM in
   both daylight and standard time, while avoiding GitHub's top-of-hour load.
2. After acquiring the serialized workflow slot, the job explicitly checks out
   the latest `main`. This prevents a queued cron event from reading the stale
   run state captured before an earlier trigger published.
3. A lightweight application gate runs before Java and figure-extractor setup.
   It converts the trigger to `America/New_York` and selects the oldest missed
   configured publication date no later than the current due date. This lets a
   GitHub trigger delayed across midnight retain its intended feed date. A
   successful date is never repeated; a failed date remains due for the next
   retry window.
4. Configuration, prompts, taxonomy, and prior run state are loaded and
   validated.
5. Taxonomy changes are planned and applied in memory. Ambiguous or unsafe
   migrations stop the run before publication.
6. New arXiv entries are fetched, normalized, replacement entries excluded,
   and duplicates merged by versionless arXiv ID.
7. Terminal prior screening decisions are reused. Eligible failed items enter
   the bounded retry backlog.
8. The filter LLM assigns KEEP/DROP/FAILED, scores relevance and novelty, and
   returns topic assignments under the current taxonomy.
9. Every kept paper without a valid cached summary receives a structured
   summary. Valid unchanged summaries are reused.
10. PDFs are downloaded and processed by the pinned PDFFigures2 revision.
   Crops are normalized to WebP, a deterministic hero is selected, and all
   usable crops are retained for the detail carousel.
11. Day feeds, topic feeds, indexes, Markdown, and website files are rendered
    into a staging area and validated against typed public contracts.
12. Valid staged files replace their destinations atomically. Marker-confirmed
    stale generated topic/day files are removed only after validation.
13. Canonical papers, taxonomy snapshot, run statistics, and successful run
    state are validated and written.
14. The workflow runs repository publication validation, commits only the
    generated allowlist, and pushes it to `main`.
15. Completion of a successful daily workflow triggers the Pages workflow via
    `workflow_run`, which publishes the public site/feed from the updated
    `main` branch. Direct qualifying pushes and manual dispatch remain valid
    deployment paths. The iPhone receives the publication on the next launch
    or pull-to-refresh.

`workflow_dispatch` runs with `--manual`, bypassing the due-time and
already-succeeded gates. Workflow concurrency prevents overlapping daily jobs.

If arXiv ingestion, taxonomy migration, a required contract, or final
validation fails, the workflow exits non-zero and does not create a generated
commit. Figure extraction is deliberately non-blocking per paper: a failed
paper publishes with a placeholder and `figure_status=failed`.

## 6. Taxonomy edit behavior

Taxonomy identity is the stable `id`, not the display name.

### Add a topic or subtopic

- Add a unique ID and complete metadata, increment `taxonomy_version`, and run
  validation.
- Future candidates can be assigned to the new item.
- Existing selected papers are not automatically reclassified merely because a
  new item exists; a deliberate rebuild/re-screen is required for retroactive
  assignment.
- A successful publication creates the new topic feed and UI row. Zero-paper
  topics remain valid if the public contract permits them.

### Change a display name, description, keywords, or icon

- Keep the same ID and increment `taxonomy_version`.
- Existing assignments remain attached to that ID.
- Regenerated website/app metadata reflects the new presentation.
- Keyword changes affect future filtering, not historical decisions, unless a
  rebuild is requested.

### Rename an ID

- Give the destination `previous_ids` containing the old ID.
- The migration planner rewrites historical canonical assignments before the
  new output is validated.
- After successful publication, new paths use the new ID and stale generated
  files for the old ID are removed.
- Removing the old ID without a declared destination is rejected while it is
  still used by any canonical paper.

### Move a subtopic

- Keep its identity or declare `previous_ids`, and declare `moved_from` with the
  prior parent topic.
- Historical assignments move to the new parent in memory, duplicate topic
  assignments are merged, and the complete result is validated before write.
- An undeclared parent change is rejected.

### Remove a topic or subtopic

- An unused ID may disappear after version increment and validation.
- An in-use ID cannot silently disappear. It must be renamed/moved to a valid
  destination, or the canonical paper set must be deliberately rebuilt so no
  assignment references it.
- On successful publication, old generated topic JSON/Markdown/site paths are
  cleaned conservatively. They are not moved to an archive directory.
- The paper itself remains in the canonical collection if it still qualifies
  through another valid assignment. Removal from the taxonomy alone does not
  mean deletion of the research paper.
- Private iPhone state is keyed by arXiv ID, so seen/saved/notes/status survive
  public topic removal. A saved snapshot can retain older topic metadata until
  that snapshot is refreshed from a newer public paper.

## 7. Public feed contracts

The iPhone starts at `data/feed_index.json` and `data/topics.json`, then follows
only relative paths supplied by those validated documents. Public URLs remain
under the configured publication root.

Core contracts:

- `feed_index.json`: publication timezone, generated timestamp, ordered days,
  feed path, and paper count;
- `daily_feeds/YYYY-MM-DD.json`: one day's complete public papers;
- `topics.json`: taxonomy metadata, icons, subtopics, counts, and feed paths;
- `topic_feeds/<topic>/<subtopic-or-all>.json`: topic history projections;
- `figures/<versionless-arxiv-id>/`: hero and gallery WebP assets.

Each public paper includes versionless arXiv identity, title, authors, abstract,
URLs, scores, selection reason, assignments, summary status/content, figure
status, optional hero path, and optional figure gallery metadata.

The website converts relative figure paths to URLs relative to the publication
root, so figures render correctly from nested day and topic pages.

## 8. iPhone implementation

### 8.1 Networking and caching

The production `AppModel` uses an injected `PaperFlowRepository`, a read-only
HTTP client, and `FilePublicFeedCache`. Initial loading fetches the feed index,
topics index, and latest day. A refresh preserves already loaded content if the
network request fails and reports that cached data is being shown.

The app contains no write endpoint and no public-feed credentials.

### 8.2 Personal identity and persistence

`PersonalPaperState.canonicalArxivID` is unique and normalized by removing the
arXiv version suffix. All appearances of the same paper across days, topics,
Browse, Swipe, Detail, and Saved resolve to one personal state.

Saving creates a `SavedPaperSnapshot` containing enough paper, summary, topic,
and figure metadata to reopen the paper independently of a later public-cache
eviction. Notes, rating, Queue/Reading/Done, and timestamps persist in SwiftData
across normal launches. Deleting the app or its data deletes this private store;
V1 has no cloud backup or cross-device sync.

### 8.3 Reviewed semantics

A paper is reviewed when its canonical personal state has `seen=true`. Both
Save and Skip set `seen=true`; opening a detail page alone does not complete a
triage decision. Reviewed counts are global per paper, not per pipeline run or
per topic. Therefore a paper reviewed through an older day or another topic is
already reviewed wherever the same arXiv ID appears.

Swipe defaults to Unreviewed. The All Papers filter permits re-review. Undo
restores the exact prior personal state for the latest session action.

### 8.4 Current navigation and UX

Permanent tabs are exactly Today, Topics, and Saved.

- Today shows the current local date, latest available publication day,
  global reviewed progress, Browse, Swipe, and prior days.
- Swipe uses one centered navigation date, a chevron-only back control, top
  undo icon, top filter icon, compact `x/y reviewed` progress, and a large card.
- The swipe card prioritizes a 320-point figure region, then title, topic tags,
  summary, and scores. Save/Skip occur by gesture; the removed bottom action
  bar no longer consumes card space.
- Paper Detail is one reusable implementation. It provides figure paging,
  captions, Share, summary/abstract/selection details, and private actions.
- Tapping a figure opens a full-screen zoom surface with pinch-to-zoom and pan.
- Topics displays server-provided SF Symbol icons and counts, with topic and
  subtopic browse/swipe routes.
- Saved provides Queue, Reading, and Done workflows plus search, notes, rating,
  and persistent saved snapshots.

Important controls retain accessibility labels/identifiers and support Dynamic
Type, VoiceOver semantics, reduced motion, and minimum tap targets.

## 9. Website

The generated static website provides latest-day, day archive, topic, and
subtopic pages. It uses the same validated public projection as the app. Hero
figures use publication-root-aware URLs, and missing/failed figures use the
normal placeholder path rather than breaking the page.

No server process or database is required at runtime; GitHub Pages serves only
static assets.

## 10. Deployment and owner workflow

### Repository automation

- Keep `OPENROUTER_API_KEY` configured as a repository secret.
- Keep GitHub Actions and GitHub Pages enabled.
- The daily workflow runs automatically every day at 9:00 PM New York time.
- Review failed Actions runs; a failed run leaves the last successful public
  feed available.

### iPhone use

1. Install/update PaperFlow from the shared Xcode project when the binary
   changes.
2. Each day after the pipeline and Pages deployment finish, open PaperFlow or
   pull down on Today/Topics to refresh.
3. Tap Swipe and triage with left/right gestures; use the top undo icon when
   needed.
4. Save papers intended for deep reading. Their snapshots and personal reading
   state remain on the iPhone across ordinary app launches and feed refreshes.
5. Use Saved to move papers through Queue, Reading, and Done.

The iPhone does not need to connect to GitHub or Xcode every day. It only needs
network access to refresh the published feed. Xcode is needed when installing a
new app build or renewing the owner's local development installation.

## 11. Validation and release evidence

Required Python checks:

```bash
pytest
ruff check .
python -m paperflow.cli.validate_taxonomy
python -m paperflow.render.validation
```

iOS changes require a relevant `xcodebuild`, affected unit tests, affected UI
tests for interaction changes, and a Simulator screenshot for visual changes.

The checked-in production run dated 2026-08-21 records:

- 782 fetched and 461 deduplicated/screened candidates;
- 127 kept, 264 dropped, and 70 filter failures eligible for retry policy;
- 127 generated summaries and zero summary failures;
- extraction figure mode with published PDFFigures2 galleries;
- approximately USD 0.1108 LLM cost;
- eight topics and 127 unique public papers.

The current real-app capture is stored in `docs/ui/real/` as four individual
screens and one exact four-panel composite.

## 12. Known V1 limitations

- Personal state is local to one installed app data container and is not
  synchronized or backed up by PaperFlow.
- Distribution is owner-only through Xcode, not the App Store or TestFlight.
- New taxonomy categories do not retroactively classify historical papers
  without a deliberate rebuild/re-screen operation.
- Per-paper figure failure degrades to a placeholder by design.
- The app refreshes on launch or user pull-to-refresh; V1 has no background push
  notification telling the app that Pages deployment completed.
