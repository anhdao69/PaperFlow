# PaperFlow Test Plan

Status: planning only. This document defines the verification strategy for the phased implementation in `docs/architecture/IMPLEMENTATION_PLAN.md`.

## 1. Goals and quality invariants

Testing must prove more than successful rendering. The release is acceptable only when it demonstrates:

- no silent paper loss;
- no malformed LLM result converted into DROP;
- FAILED backlog retry independent of tomorrow's arXiv feed;
- exact, auditable canonical and public counts;
- root README-only 80-row truncation;
- atomic publication and safe taxonomy migration;
- one public paper identity and one private personal state per versionless arXiv ID;
- strict separation of AI and human state;
- local personal actions that succeed without network or sync;
- cache refresh that can fail without erasing the last valid public data;
- identical collection membership across JSON, Markdown, website, and iOS;
- one reusable Swipe behavior and one Paper Detail behavior across entry points;
- no figure dependency on the core release path.

The technical plan is authoritative for backend/state expectations. The UI/UX spec is authoritative for interaction and presentation. PNGs are used for qualitative visual review only and never as a source of test data or unsupported behavior.

## 2. Test layers and locations

```text
tests/
├── unit/
│   ├── llm/
│   ├── render/
│   └── figures/                 # Phase 25+
├── integration/
└── fixtures/
    ├── configs/
    ├── taxonomy/
    ├── contracts/v1/
    ├── pipeline/
    └── figures/                 # labels only; PDFs stay gitignored

ios/PaperFlow/
├── PaperFlowTests/
└── PaperFlowUITests/

docs/testing/results/           # dated soak/E2E reports when execution begins
docs/ui/screenshots/            # reviewed Simulator captures if checked in
```

Test categories:

| Layer | Purpose | Default external network | Release gate |
|---|---|---:|---:|
| Python unit | Pure schemas, transformations, state, rendering helpers | Off | Every phase |
| Pipeline integration | Multi-stage orchestration and atomic files | Off; fakes/fixtures | Backend phases |
| Failure injection | Explicit errors at every boundary | Off | Backend and iOS core |
| JSON contract | Producer/consumer compatibility and count integrity | Off | Contract changes |
| iOS unit | Decoding, repositories, view models, commands | Off | Every iOS phase |
| SwiftData state machine | Persistent private-state semantics | Off | Personal/Saved/Swipe |
| XCUITest | User-visible navigation and actions | Off; launch fixtures | Interaction changes |
| Offline | Cache and personal-state failure-domain separation | Forced offline | iOS release |
| Screenshot review | Written-spec hierarchy and visual regression | Off | UI changes |
| End to end | Generated public output → HTTP → iPhone/website | Local server first | Core release |
| Live smoke/soak | arXiv/OpenRouter/GitHub real-world behavior | Explicitly on | Operations gates |

## 3. Test design rules

1. Network clients, clocks, random jitter, filesystem roots, process runners, haptics, and SwiftData containers must be injectable.
2. Unit and normal integration suites make no live arXiv, OpenRouter, GitHub, or PDF request.
3. Live tests require an explicit marker/environment opt-in and never run just because a secret exists.
4. No test logs an authorization header, secret environment dump, or raw LLM payload by default.
5. Tests write only to per-test temporary directories or in-memory SwiftData containers unless explicitly exercising a disk-backed restart.
6. Golden output comparisons normalize only values defined as variable, such as run IDs/timestamps. They do not normalize counts, IDs, ordering, status, or provenance.
7. Use deterministic clocks and zero-delay retry policies in tests; separately test the production backoff calculation.
8. Every regression bug gets the smallest failing test at its owning layer before or with the fix.
9. Contract fixtures are shared conceptually between Python producer and Swift decoder. A producer change cannot merge until both pass.
10. UI reference images are not pixel-perfect golden masters. Written acceptance criteria and semantic tokens control sign-off.

## 4. Backend unit tests

### 4.1 Configuration

Test `RuntimeConfig`, `ModelConfig`, prompt manifest, and environment loading:

- valid checked-in configuration;
- unknown/missing keys according to the chosen strictness policy;
- invalid timezone, local time, run day, concurrency, retry, batch, and publishing bounds;
- no KEEP-cap field accepted as normal selection behavior;
- model aliases resolve and every task chain is non-empty;
- provider must be OpenRouter in V1;
- deterministic normalized config hashes;
- hash changes on semantic value change, not YAML formatting/comment changes;
- secret read from injected environment only and never serialized;
- config validation that does not need an API call succeeds without a secret;
- base model/task switch occurs through YAML without business-code edits.

### 4.2 Taxonomy and migrations

Test two-level shape and every mandatory rule:

- active topic IDs unique;
- subtopic IDs globally unique;
- valid ID regex and path safety;
- non-empty names/descriptions;
- unique, non-colliding `previous_ids`;
- active ID not reused as historical ID;
- subtopic has one active parent;
- `moved_from` references a valid old/current parent;
- moved item absent from old parent;
- no rename/move cycle or ambiguous chain;
- selected assignments are active or migratable;
- config-order lookup and display ordering.

Migration cases:

- display-name-only change leaves stored IDs untouched;
- topic and subtopic ID rename rewrites history;
- subtopic re-parent moves the child assignment;
- move removes an empty old parent assignment;
- move merges into an existing target without duplication;
- combined rename then move follows the mandated order;
- invalid removal blocks before output cleanup;
- unknown/manual file never enters stale cleanup;
- failed validation leaves snapshot, canonical store, and generated tree unchanged.

### 4.3 Prompt rendering and caching keys

- taxonomy template emits exactly configured topics/subtopics in YAML order;
- filter instructions require KEEP assignment and DROP empty assignment;
- filter user blocks contain only ID/title/categories/abstract;
- summary instruction limits itself to title/abstract and 3–5 bullets;
- same inputs render byte-identically;
- taxonomy change invalidates filter key but not summary key;
- filter prompt/model/abstract change invalidates filter key;
- summary prompt/model/abstract change invalidates summary key;
- corrupt or incomplete cache record is a miss, never canonical truth.

### 4.4 Models and canonical storage

- `FilterResult` score bounds 1–10;
- KEEP with no assignment rejected;
- DROP with assignment rejected;
- selected store accepts only `filter_status=kept` with at least one valid assignment;
- Summary generated/failed/pending fields remain internally consistent;
- initial `hero_figure=null`, `figure_status=not_implemented` accepted;
- screening ledger appends and never rewrites prior history;
- deterministic latest-event reduction, including explicit tie policy;
- monthly ledger boundaries;
- corrupt/truncated ledger line produces an actionable validation error;
- atomic write uses validate-before-replace and preserves prior file on interruption;
- run success state cannot update before generated validation.

### 4.5 arXiv ingestion and normalization

- new v1 submission retained;
- replacement/update excluded from normal NEW flow;
- version suffix maps to base ID while source ID remains;
- cross-list duplicate becomes one candidate;
- categories unioned deterministically;
- title/abstract scientific text meaning is not rewritten by normalization;
- malformed item is surfaced according to source policy;
- complete fetch/parse failure differs from successful zero results;
- raw snapshot targets cache only.

### 4.6 Retry backlog

- unseen current candidate included;
- current FAILED candidate included only when eligible;
- absent eligible FAILED record is refetched and included;
- current/backlog duplicate processed once;
- KEPT/DROPPED skipped during normal daily processing;
- cooldown just-before/at/after boundary;
- attempt numbers increment correctly;
- exhausted failure remains FAILED with `retry_exhausted=true`;
- exhausted failure is omitted automatically;
- manual reprocess can override exhaustion;
- metadata refetch failure records/retains failure without converting to DROP.

### 4.7 OpenRouter client

- structured success and typed parse;
- requested and actual model differ during fallback and both are retained;
- provider/request ID/tokens/cached tokens/cost/latency captured when present;
- missing optional usage fields handled;
- ordered model fallback passed exactly as configured;
- retry 429, 500, 502, 503, 504, timeout, reset, temporary DNS/connectivity failures;
- bounded attempt count and jitter range;
- no blind retry on 400, 401, 403, invalid model, unsupported parameter;
- transport error and semantic error are distinct types;
- malformed response envelope cannot be regex-parsed into success;
- logs redact key and Authorization header.

### 4.8 Filtering

- unknown topic rejected;
- wrong parent-child assignment rejected;
- duplicate topic assignment rejected;
- duplicate subtopic behavior is deterministic and documented;
- requested/result ID sets match exactly;
- missing, extra, and duplicate result IDs rejected;
- valid subset retained when a sibling is invalid;
- invalid subset alone retried on next model;
- unmappable envelope retries full batch once;
- second semantic failure emits FAILED, never DROP;
- every accepted outcome writes complete provenance hashes/model fields;
- concurrency and batch boundaries do not change result ordering/membership.

### 4.9 Summaries

- only KEEP papers targeted;
- one non-empty TL;DR and 3–5 bullets;
- optional problem/method/contribution round-trip;
- failed summary leaves paper selected/assigned/scored;
- retry success changes summary status without a screening event;
- failed summary projects abstract fallback;
- summary model/provenance/cost captured;
- concurrency does not lose or duplicate target papers.

### 4.10 Shared projections, Markdown, JSON, and website

- canonical versionless identity unique;
- first-seen descending then arXiv ID descending ordering;
- topic labels use YAML order;
- multi-topic paper fans out to every correct view once;
- parent-only paper appears in large-topic but no child feed;
- empty configured topic/subtopic still rendered;
- root README cases 0, 1, 79, 80, 81, 500;
- README cap referenced only by root renderer;
- daily/topic/subtopic/API/website histories never inherit cap;
- Markdown escaping and identical table header;
- feed index totals and day counts equal payload memberships;
- topics hierarchy mirrors config exactly;
- topic totals/day counts equal projected memberships;
- public allowlist excludes retry internals, raw LLM requests, and secrets;
- null/failed/ready figure states encode and render;
- generated routes are safe and stable;
- every internal website link resolves;
- only exact AUTO-GENERATED stale files are removable;
- rebuild output command invokes zero network clients.

### 4.11 Schedule, run metrics, and maintenance

- EST and EDT cron candidates;
- DST transition dates;
- wrong candidate trigger exits;
- due and delayed same-day catch-up run;
- disallowed day/disabled schedule;
- same local date after success exits;
- manual dispatch bypasses time gate;
- generated workflow mismatch detected;
- run metric arithmetic and model breakdown;
- report includes `KEEP cap: NONE`;
- source-failure status is not zero-paper success;
- reclassify writes new events and preserves old ledger history;
- historical DROP metadata refetch is injectable;
- maintenance dry-run has no writes;
- `rebuild_outputs` has no arXiv/LLM/PDF calls.

## 5. Pipeline integration tests

### 5.1 Canonical two-run fixture

`tests/fixtures/arxiv_daily_sample.json` must contain:

```text
12 raw entries
2 cross-listed duplicates
10 unique candidates
3 KEEP
6 DROP
1 simulated FAILED
1 KEEP assigned to 3 large topics
1 KEEP assigned to multiple subtopics under one parent
```

First-run assertions:

```text
unique candidates              10
screening events appended      10
KEEP                            3
DROP                            6
FAILED                          1
selected-store papers           3
daily archive rows              3
daily feed papers               3
README rows                     3
```

Second-run source omits the failed paper. The backlog refetch returns it and the fake filter succeeds. Assert:

- backlog contributes exactly one paper;
- it is screened despite source absence;
- prior FAILED event remains;
- latest state becomes KEPT or DROPPED as fixture specifies;
- no terminal paper from run one is screened again;
- all canonical/generated counts update once.

This is a mandatory release test, not an optional smoke test.

### 5.2 Full daily success

Using fake source and LLM transports:

1. Load and validate config/taxonomy/prompts.
2. Plan/apply any migration in memory.
3. Fetch, normalize, deduplicate, and merge backlog.
4. Filter and append events.
5. Build/update selected store.
6. Generate/fail summaries as fixture defines.
7. Render Markdown/JSON/website into staging.
8. Validate staged artifacts.
9. Atomically install canonical/generated files.
10. Update run metrics/state last.

Assert stage events, model usage, counts, hashes, ordering, and exact install order.

### 5.3 Successful zero-result day

- Source fetch succeeds with no new candidates.
- No eligible retry exists.
- Generate an explicit zero-paper daily archive/feed/index day.
- Do not treat the run as source failure.
- Existing full history remains unchanged and reachable.

### 5.4 Source failure

- Fail source at connection, HTTP, parse, and incomplete-fetch boundaries.
- Assert no successful-empty day, no canonical update, no generated install, no success state update, and a failure report.

### 5.5 Partial filter salvage

- Return a batch with valid KEEP, valid DROP, invalid assignment, and duplicate ID.
- Assert safely identifiable valid results persist once.
- Retry only the invalid subset when IDs are safely mapped.
- If envelope mapping is unsafe, retry the whole batch once without duplicating already-final events.
- Remaining invalid results become FAILED.

### 5.6 Summary degradation

- Fail one new summary and one prior-summary retry.
- Assert selection and public membership stay intact.
- Generated views use the specified abstract fallback.
- Later success updates summary fields but not first-seen date or screening outcome.

### 5.7 Taxonomy migration and stale cleanup

- Rename and move a subtopic used by historical papers.
- Validate rewritten in-memory assignments and regenerated routes.
- Inject failure before install and confirm old routes/data remain intact.
- On success, remove only stale AUTO-GENERATED paths after validation.
- Compare JSON, Markdown, website, and prompt taxonomy semantics after migration.

### 5.8 README isolation at scale

- Generate 500 canonical KEEP papers over multiple days/topics.
- Assert README has the newest 80 only.
- Assert selected store, daily archives, feed index, daily feeds, topic feeds, topic Markdown, website, and iOS fixture index expose all applicable 500.

### 5.9 Atomic publication

Run the pipeline in a temporary Git repository and inject failure at each mutation boundary:

- before screening append;
- after screening append but before selected-store staging;
- during summary processing;
- during render;
- during generated validation;
- during stale cleanup planning;
- immediately before install/commit/push.

Assert the documented durable-event behavior, no invalid canonical/generated install, no partial Git commit, and no success-state update. Screening events already durably appended before a later nonfatal stage must remain auditable; the final implementation must document that transaction boundary explicitly.

## 6. Failure injection matrix

| Boundary | Injected failure | Expected result |
|---|---|---|
| Config | Missing/invalid YAML/model alias | Run stops before source/network/write |
| Taxonomy | Collision, ambiguous rename, invalid move | Migration/output blocked; old files intact |
| Source | Timeout/HTTP/parse/incomplete fetch | Run failure; no successful zero day; no publication |
| Metadata refetch | FAILED backlog paper unavailable | Remains FAILED/retry-governed; never DROP |
| OpenRouter auth/config | 400/401/403/invalid model | No blind retry; actionable run failure/outcome policy |
| OpenRouter transient | 429/5xx/timeout/reset | Bounded backoff/fallback; attempt metadata correct |
| LLM envelope | Invalid JSON/schema | Semantic retry policy; then FAILED |
| Filter member | Unknown topic/wrong parent | Valid siblings salvaged; invalid subset retried |
| Filter ID set | Missing/extra/duplicate IDs | Unsafe batch never accepted silently |
| Ledger | Truncated/corrupt line | Validation failure; no guessed latest state |
| Summary | Timeout/malformed output | Paper stays KEEP; fallback publishes |
| Cache | Missing/corrupt/stale key | Cache miss; correctness unaffected |
| Filesystem | Permission/full disk/replace interruption | Prior canonical/output retained; run not successful |
| Renderer | Count/membership/link mismatch | Staged output rejected; no commit |
| Schedule | Both DST cron candidates fire | Only due one works; same-day duplicate exits |
| Git | Push conflict/permission failure | No false success state; recoverable next run |
| iOS HTTP | Offline/timeout/non-2xx | Cached content retained; contextual error |
| iOS JSON | Schema/count mismatch | Payload rejected; last valid cache retained |
| iOS cache | Corrupt file/failed atomic replace | Valid prior cache or explicit no-cache state |
| SwiftData | Save/transaction failure | No contradictory partial personal state |
| Sync | Private sync unavailable | Local mutation remains successful |
| Image | Bad URL/timeout/decode | Stable placeholder; no layout jump |
| Figure worker | PDF/extractor/image failure | `hero_figure=null`, failed state, publication continues |

Every row needs at least one automated test. High-risk rows (source, semantic filtering, filesystem publication, cache replacement, SwiftData transaction, figure non-blocking) need both a focused test and an integration scenario.

## 7. JSON contract tests

### 7.1 Contract artifacts

Maintain versioned fixtures for:

- `feed_index.json`;
- successful zero-day feed;
- populated daily feed;
- `topics.json`;
- large-topic feed;
- subtopic feed;
- paper with generated summary;
- paper with failed summary/fallback;
- paper with `hero_figure=null`/`not_implemented`;
- later paper with ready and failed figure states;
- intentionally invalid schema/count/parent-child/path fixtures.

The V1 goldens require the full original `abstract` on every public paper and explicit publication-root-relative feed URLs.

### 7.2 Producer assertions

- Exact `schema_version` handling.
- `feed_index.timezone` is a valid IANA identifier and matches the publishing runtime timezone.
- Required fields present with correct nullability and ISO-8601 date/time formats.
- Canonical `arxiv_id` is versionless; source version is not substituted.
- Public paper allowlist excludes private and retry fields.
- `total_paper_count`, `day_count`, and every `paper_count` equal actual projected membership.
- Days newest to oldest; papers use specified stable ordering.
- `topics.json` hierarchy/order mirrors YAML exactly.
- Subtopic belongs to the advertised parent.
- Large-topic `all.json` has `subtopic_id=null`; subtopic feeds require a valid child ID.
- Every day/topic `feed_url` is explicit, publication-root-relative, and contains no leading slash, traversal, backslash, query, or fragment.
- `hero_figure` is null or follows the same publication-root-relative rule; arXiv/PDF links are absolute HTTPS.
- `topics.json.total_paper_count` is unique canonical membership and is not the sum of overlapping topic rows.
- No root README limit influences any JSON count or membership.

### 7.3 Swift consumer assertions

- Every valid producer fixture decodes in `PublicFeedDecodingTests`.
- Feed publication timezone decodes and drives Today date selection independently of the device timezone.
- Missing required/unknown schema version is rejected with a user-safe error.
- Optional fields and null figure states decode without losing identity.
- Count/payload mismatch is rejected before cache replacement.
- Relative URLs resolve against the configured publication-root base URL exactly once, never against the containing JSON file.
- Topic endpoints are consumed from JSON and never reconstructed from IDs.
- Topic and paper IDs remain strings, not Swift enums or hard-coded cases.
- Decoder failure does not mutate SwiftData.

### 7.4 Compatibility gate

For any public schema change:

1. Update authoritative schema/model and version policy.
2. Add forward fixture and retain prior supported fixture.
3. Run Python producer tests.
4. Run Swift decoder/repository tests.
5. Run local-server iOS E2E.
6. Only then regenerate public artifacts.

## 8. iOS unit tests

### 8.1 Models and identity

- Versioned IDs normalize to one canonical ID.
- Codable models accept valid and reject invalid V1 fixtures.
- Public paper equality/identity uses canonical ID, not source collection or object instance.
- Figure states map to placeholder/loading/ready/failed presentation.
- Relevance/novelty display remains numeric or follows one tested mapping.

### 8.2 Repositories and cache

- Async endpoint calls use configured base URL.
- Feed index loads first; day/topic feeds load lazily.
- Concurrent request coalescing does not duplicate cache writes.
- Cancelled task does not publish a partial state.
- Refresh validates before atomic replacement.
- Last-success timestamp changes only on valid refresh.
- Cached feed and Saved snapshot merge preserves personal fields.
- Removing a public cache cannot cascade into personal SwiftData deletion.

### 8.3 View models

Today:

- Today binds to the current date in the feed index's IANA publication timezone; device timezone changes do not change feed-day identity;
- an absent publication date exposes Latest Available separately;
- exact public count remains distinct from reviewed/remaining;
- valid zero, loading, cached error, and no-cache error states;
- Today and Topics expose no Search/Settings state in V1;
- Browse rendering/opening makes no personal mutation;
- only supported sort/filter options are offered.
- topic/status filters and sort tie-breakers are deterministic and make no personal mutation.

Swipe:

- default eligibility is `seen == false` globally;
- collection membership remains public and complete;
- active progress denominator is public membership after topic/subtopic filters and before review mode;
- reviewed/total plus remaining progress values and copy are consistent in every scope;
- completion Saved count is saved membership intersected with the active collection, not global Saved count;
- buttons and gestures dispatch identical commands;
- detail round-trip keeps current item;
- resume derives from persisted state, not saved array index;
- one-action undo availability and exact restoration.

Topics:

- hierarchy, explicit feed URLs, and counts are fully data-driven;
- Total Papers is unique canonical membership rather than summed topic rows;
- large-topic/subtopic day memberships and counts;
- All/Unread/Saved predicates use one personal store;
- a reviewed paper from Today is not unread in Topics.

Saved:

- Queue/Reading/Done partition current saved membership;
- search over every approved local field;
- Saved search is case/diacritic-insensitive and works offline;
- all displayed sorts have real stored values;
- summary fallback/snapshot update behavior;
- notes/rating/status changes are immediate and durable;
- Unsave/resave retains the exact personal history and snapshot defined by the state table.

Paper Detail:

- one view model supports every origin;
- normal Back does not finalize triage;
- swipe-context Save/Skip finalize and return/advance;
- unsaved vs saved personal controls;
- generated summary vs abstract fallback;
- external URLs and share target.

### 8.4 Accessibility and presentation logic

- Localized accessibility value such as “18 of 42 papers reviewed.”
- Save/Skip/Undo/Bookmark/Rating controls have labels and identifiers.
- Status is communicated by text/icon in addition to color.
- Dynamic Type does not force critical text into fixed-height clipping at view-model/component test level.
- Reduced-motion setting chooses restrained/no custom transitions where implemented.

## 9. SwiftData personal state-machine tests

One canonical `PersonalPaperState` must be queried/uniqued by versionless arXiv ID. Public metadata/saved snapshots may be separate storage objects, but they cannot create another mutable source for seen/saved/status/note/rating.

Every row must be covered in both an in-memory model container and at least one disk-backed restart test.

| Prior state | Command | Required post-state |
|---|---|---|
| No record | Skip | `seen=true`, `saved=false`, `lastSeenAt=now` |
| No record | Save | `seen=true`, `last_seen_at=now`, `saved=true`, `saved_at=last_saved_at=now`, `unsaved_at=null`, status `queue`, status timestamp `now`, snapshot present |
| Reviewed/never-saved | Save | Saved/queue; `last_seen_at=now`; `saved_at=last_saved_at=now`; `unsaved_at=null` |
| Previously unsaved | Save | `seen=true`, `last_seen_at=now`, `saved=true`; `last_saved_at=now`; `unsaved_at=null`; first `saved_at`, status/timestamps, note, rating, snapshot preserved |
| Saved/queue | Save again | Review timestamp updates; no duplicate; Save/status timestamps not reset |
| Saved/reading | Save again | Review timestamp updates; remains reading; Save/status timestamps unchanged |
| Saved/done | Save again | Review timestamp updates; remains done; Save/status timestamps unchanged |
| Saved/any | Skip in review-again | Remains saved with same reading state; review timestamp updates |
| Any | Render/open Browse card | No personal mutation |
| Saved/queue | Mark Reading | Saved/reading; status/start timestamps `now`; completion cleared |
| Saved/reading | Mark Done | Saved/done; status/completion timestamps `now` |
| Saved/done | Mark Queue | Saved/queue; status timestamp `now`; completion cleared |
| Saved/done | Mark Reading | Saved/reading; status/start timestamps `now`; completion cleared |
| Saved | Present Detail | `last_opened_at=now` once per presentation; all other fields unchanged |
| Saved | Open arXiv/PDF | `last_opened_at=now`; all other fields unchanged |
| Unsaved | Present Detail | No `last_opened_at` mutation |
| Saved | Edit note | Note autosaved; other fields unchanged |
| Saved | Set/remove rating | Rating 1–5 or null; other fields unchanged |
| Saved | Unsave | `saved=false`, `unsaved_at=now`; seen, Save/status/open timestamps, note, rating, snapshot preserved |
| Any swipe finalization | Undo | Entire exact pre-action record restored or newly-created record removed as appropriate |

Additional persistence tests:

- `2608.12345v1` and `2608.12345v2` cannot create two personal states;
- concurrent Save commands converge to one record;
- failed snapshot write cannot leave `saved=true` with no retrievable Saved item;
- cache metadata refresh preserves all Save/Unsave/status/open timestamps, note, rating, and review timestamps;
- public refresh failure never starts a SwiftData rollback;
- optional sync failure callback never reverts a successful local transaction;
- deletion of all downloaded day/topic files leaves Saved snapshot usable;
- app recreation restores state and swipe eligibility.

## 10. XCUITests

All important controls receive stable accessibility identifiers. Launch arguments select deterministic fixture repositories, in-memory or temporary disk stores, clock, locale, network state, and animation speed.

### 10.1 Root/navigation

- Exactly three tab items: Today, Topics, Saved.
- Today and Topics expose no Search or Settings button; Saved search remains available.
- Each tab preserves its navigation stack when switching away/back.
- Today Browse restores approximate scroll position after Detail/tab round-trip.
- No mock-only fourth tab or Swipe/Search primary tab.

### 10.2 Today/Browse/Detail

- Today displays exact day count and separate reviewed/remaining values.
- Current publication-timezone date is Today; an older successful day is labeled Latest Available rather than today.
- Changing the simulated device timezone does not change the feed date called Today.
- Present current-day zero count shows the zero-matching state; absent current day does not.
- Open older-than-80 day and paper.
- Open Browse; scrolling/visibility does not mark reviewed.
- Exercise required topic/status filters and all four Browse sorts; Reset restores defaults without personal mutation.
- Tap card to shared Detail; Back returns to Browse.
- Tap bookmark Save; Saved label/state and Queue update immediately.
- Explicit Unsave follows confirmation/interaction and preserves review state.
- Valid zero day shows the defined empty state; source/cache error shows contextual error, not zero.

### 10.3 Swipe

- Drag left beyond threshold = Skip; under threshold cancels.
- Drag right beyond threshold = Save.
- Skip and Save buttons produce the same database/result as gestures.
- Left action on already-saved review-again card does not unsave.
- Right action on Reading/Done does not reset to Queue.
- Undo Skip and first-time/already-saved Save cases.
- Undo disabled with no active action.
- Open Detail from current card; Back returns to same card without mutation.
- Save/Skip from Detail returns and advances.
- Terminate/relaunch; remaining unreviewed deck resumes from persisted state.
- Day, large-topic, and subtopic decks all show reviewed/total and remaining with identical semantics.
- Applying a Swipe topic/subtopic filter recomputes progress before Unreviewed/Review Again eligibility.
- Completion screen appears without quote/tomorrow preview/gamification.

### 10.4 Topics

- Rows/counts follow a fixture taxonomy unknown to compiled Swift.
- Total Papers counts unique canonical IDs even when row counts overlap.
- Open Large Topic, Browse All, Subtopic, and full older history.
- All/Unread/Saved filters show correct membership.
- Swipe reviewed paper in Today, then confirm it is absent from topic default Swipe.
- Multi-topic Save appears saved in every Browse view but only once in Saved.

### 10.5 Saved

- Empty Saved explains how to Save and navigates to Today.
- Save a paper; it appears once in Queue.
- Change Queue → Reading → Done and verify counts/pages after restart.
- Search by title/author/TL;DR/topic and approved note behavior.
- Edit/autosave note; set/remove rating.
- Use every advertised sort and assert first/last fixture item.
- Verify Queue uses last Save, Reading uses last opened/fallback, and Done uses completion timestamp.
- Delete source cache, go offline, and open full Saved snapshot/Detail.
- Unsave removes library membership but retains public Browse/reviewed state, timestamps, status, note, rating, and snapshot; resave restores them.

### 10.6 Error/accessibility

- Pull-to-refresh success and failure.
- Cached error banner includes last-updated and Try Again.
- Important controls are discoverable by accessibility labels/identifiers.
- Largest supported test Dynamic Type keeps primary actions reachable.
- Status is perceivable without relying on color.

## 11. Offline tests

Offline behavior is a release gate, not a manual-only scenario.

### 11.1 Automated repository/store scenarios

1. Populate valid feed index, topics, one day, one topic feed, Saved snapshot, and personal state.
2. Force URLSession transport offline.
3. Recreate repository/app state.
4. Assert cached collections and Saved open.
5. Perform Save, Skip, Unsave, status, note, and rating mutations.
6. Assert mutations commit locally and update all loaded views.
7. Restore network with invalid-count payload; assert last valid cache remains.
8. Restore valid network; assert public metadata refreshes while personal fields survive.

Separate cases:

- no cache + offline gives a helpful retry state;
- partial cache exposes only downloaded collections without pretending all history is local;
- corrupt cache does not become an empty valid feed;
- cache eviction never evicts Saved snapshots;
- sync unavailable does not affect local success;
- image network failure uses fixed-size placeholder.

### 11.2 Manual airplane-mode drill

On a Simulator/device with previously downloaded data:

- enable network loss;
- relaunch;
- browse cached Today/topic collection;
- Save one paper, Skip one, edit status/note/rating;
- delete/evict an originating public cache through the test harness;
- confirm Saved remains usable;
- reconnect and refresh;
- confirm no personal action is lost.

Record device/OS/build, preconditions, actions, and result in the phase report.

## 12. Screenshot and visual review

### 12.1 Required captures

Capture after each changed screen and as a final matrix:

- Today Home, Day Overview, Browse, Swipe, All Done;
- Topics Home, Large Topic, Subtopic Browse, Topic/Subtopic Swipe;
- Saved Home, Queue, Reading, Done;
- shared Paper Detail from Browse and from Swipe;
- loading, valid-empty, cached-error/offline;
- missing-figure placeholder and, only in Phase 26, ready/failed real figure.

### 12.2 Device/accessibility matrix

At minimum:

- one narrow/small supported iPhone;
- one current large Pro-size iPhone;
- default Dynamic Type;
- one accessibility Dynamic Type size for representative dense screens;
- light mode for visual launch target;
- dark appearance only as an architectural smoke check unless dark-mode polish is explicitly promoted into V1.

### 12.3 Review rubric

- Only Today/Topics/Saved permanent tabs.
- Approximately 16-point page padding and coherent 8-point spacing system.
- Readable 2–3 line list titles and flexible Detail title.
- Paper content dominates; no dashboard density or tiny typography.
- Shared cards/tags/figure placeholder/save language are visually consistent.
- Swipe card is simpler than Detail and occupies an appropriate screen share.
- Purple is accent, not full-screen decoration; shadows/borders remain quiet.
- Interactive hit regions are at least 44×44.
- Long content/Dynamic Type does not overlap, clip critical content, or hide actions.
- Placeholder prevents figure layout jumps.
- Unsupported mock features are absent.

The PNG boards guide hierarchy and visual tone. Do not fail a build for pixel differences caused by native SwiftUI behavior, actual taxonomy/content, Dynamic Type, or intentional omission of mock-only features.

### 12.4 Review record

For every UI phase, record screenshot paths, simulator device/OS, fixture name, reviewer outcome, and deviations. A deviation that changes specified interaction or information priority is blocking; a decorative difference is documented but not automatically blocking.

## 13. End-to-end tests

### 13.1 Local deterministic E2E

1. Run the full Python pipeline with fake arXiv/OpenRouter over the canonical fixture into a temporary publication directory.
2. Validate all generated artifacts.
3. Serve that directory through a local HTTP server.
4. Point the iOS test build's configured base URL to it.
5. Launch with clean public cache and personal store.
6. Verify Today, Topics, full history, Browse, Swipe, Detail, Save, and Saved.
7. Restart server-offline and verify cache/personal behavior.
8. Restart server with second-run retry output and verify new public data arrives while personal state remains.

Mandatory assertions:

- a paper older than newest 80 opens in iOS;
- displayed public counts equal generated payload counts;
- multi-topic paper has one personal state;
- failed summary shows fallback;
- figure placeholder works for every core paper;
- no iOS action changes served JSON or Python ledger;
- website and iOS show the same fixture membership.

### 13.2 Git/workflow E2E

In a temporary remote/local pair:

- manual pipeline success validates and commits allowlisted generated paths once;
- repeated no-change run creates no commit;
- injected failure creates/pushes no partial commit;
- stale schedule config fails CI with the exact remediation command;
- concurrent writer protection behavior is exercised where GitHub test infrastructure permits.

### 13.3 Live smoke and soak

Live execution is opt-in and records no secrets.

- Read-only arXiv fetch confirms parser assumptions.
- OpenRouter smoke confirms configured model profiles and actual model reporting.
- Manual end-to-end run publishes to a controlled branch/environment.
- Two real scheduled runs validate schedule mechanics.
- Five consecutive local-date runs constitute the core soak gate defined in Implementation Phase 24.
- Figure live evaluation begins only after that gate.

## 14. Figure-phase tests

These tests must not exist on the core critical path and cannot begin before the soak gate.

Evaluation corpus requirements:

- at least 50 KEEP papers;
- single/two-column layouts;
- multi-panel, vector, raster, full-width architecture figures;
- nearby tables and long captions;
- human-selected desired hero per paper.

Adapter/worker tests:

- extractor timeout/crash/empty output;
- figure metadata validation;
- crop and caption normalization;
- deterministic scoring/tie-break;
- table and small-region penalties;
- fallback highest score → largest non-table → first valid → none;
- WebP long edge ≤1600 and intended quality setting;
- PDF only for KEEP and only in gitignored cache;
- low concurrency honored;
- rebuilding one paper does not alter unrelated figures;
- failed/null figure never blocks publication or iOS actions.

Measured acceptance includes recall, crop correctness, caption correctness, hero top-1 accuracy, runtime/paper, failure rate, and deployment complexity. The chosen extractor must be documented from results rather than preference.

## 15. Test execution gates

### 15.1 Per-change

- Run the smallest affected unit test immediately.
- If a state or contract changes, run all producer and consumer tests for that state/contract.
- If an interaction changes, run its XCUITest and capture its screen.

### 15.2 Python phase gate

Run affected tests first, then before completion:

```bash
pytest
ruff check .
python -m paperflow.cli.validate_taxonomy
```

Record test count, failures/skips, Ruff result, taxonomy validation result, and any opt-in/live tests separately.

### 15.3 iOS phase gate

Use the checked-in PaperFlow project/scheme and an explicitly recorded installed simulator destination:

```bash
xcodebuild -project ios/PaperFlow/PaperFlow.xcodeproj \
  -scheme PaperFlow \
  -destination '<recorded Simulator destination>' \
  build

xcodebuild -project ios/PaperFlow/PaperFlow.xcodeproj \
  -scheme PaperFlow \
  -destination '<recorded Simulator destination>' \
  test
```

If unit and UI tests use separate schemes/test plans, record and run both exact commands. UI changes also require a Simulator screenshot. Interaction changes require the affected XCUITest.

### 15.4 Contract/publication gate

- Python producer contract tests pass.
- Swift consumer fixture tests pass.
- Cross-format membership/count validation passes.
- Generated link crawl passes.
- Staged artifacts validate before install.
- `rebuild_outputs --dry-run` makes zero network calls and no writes.

### 15.5 Core release gate

- All Phase 23 tests/commands pass.
- Local deterministic E2E passes.
- Required screenshots are reviewed.
- Two real scheduled runs pass.
- Five-run soak passes with `figures.enabled=false`.
- All resolved decisions in Implementation Plan §6 are represented by contract/state/UI tests.

### 15.6 Final figure release gate

- Measured extractor decision complete.
- Figure failure-injection suite proves non-blocking behavior.
- Full Python, website, JSON contract, iOS unit/UI, offline, and E2E regressions pass.
- Ready/failed/null figure screenshots reviewed.

## 16. Traceability from requested areas

| Requested area | Primary sections |
|---|---|
| Backend unit tests | §4 |
| Pipeline integration tests | §5 |
| Failure injection | §6 |
| JSON contract tests | §7 |
| iOS unit tests | §8 |
| SwiftData state-machine tests | §9 |
| XCUITests | §10 |
| Offline tests | §11 |
| Screenshot/visual review | §12 |
| End-to-end tests | §13 |

## 17. Completion evidence template

Every future test report should contain:

```text
Phase/change:
Commit/worktree identifier:
Environment:
Fixtures:

Commands run:
- <exact command> → <exit code>, <passed/failed/skipped counts>

Manual/Simulator checks:
- <device + OS + scenario> → <result>

Screenshots:
- <path>

Failure injections exercised:
- <boundary> → <observed recovery>

Known issues/open decisions:
- <item or none>
```

Passing tests do not waive the resolved product contracts. Any requested deviation from Implementation Plan §6 requires an explicit specification change and corresponding test updates before implementation.
