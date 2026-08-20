# PaperFlow Implementation Plan

Status: planning only; no product code has been implemented.

## 1. Authority and scope

This plan is derived from, in priority order:

1. `docs/specification/PaperFlow_Technical_Plan_v3_2.md` for data models, state semantics, backend behavior, pipeline ordering, and publication guarantees.
2. `docs/ui/PaperFlow_UI_UX_SPEC.md` for iPhone interaction and presentation.
3. `docs/ui/reference/today.png`, `topics.png`, and `saved.png` for visual hierarchy only.

The implementation must proceed one phase at a time. A phase may start only after all exit criteria of its prerequisites pass. Figure evaluation and extraction remain the final workstream and cannot begin until the core soak gate passes.

The repository is currently a greenfield planning repository: it contains the two specifications, three reference boards, and `AGENTS.md`, but no Python package, Xcode project, tests, CI configuration, or generated data.

## 2. Locked system boundaries

- Python 3.12 source lives under `src/paperflow` and uses typed Pydantic models.
- OpenRouter is the single LLM abstraction. No task-specific code calls a model provider directly.
- `configs/topics.yaml` is the only structural taxonomy source. Swift and Python do not hard-code topic IDs or names.
- Public feed data is read-only. Private iPhone interaction state lives in SwiftData and is keyed by canonical versionless arXiv ID.
- AI screening state (`KEPT`, `DROPPED`, `FAILED`) and human state (reviewed, saved, reading status, note, rating) never overwrite one another.
- The root `README.md` is the only view limited to 80 papers. Every other applicable output exposes complete KEEP history.
- Canonical and generated files are published only after validation succeeds. Source-ingestion failure publishes nothing.
- The iPhone core ships with a stable figure placeholder. PDF and figure work starts only after the non-figure system passes its soak gate.
- Permanent tabs are exactly Today, Topics, and Saved. There is one shared Paper Detail implementation and one canonical personal record per paper.

## 3. Dependency and delivery shape

```text
0 Bootstrap
  → 1 Config
  → 2 Taxonomy schema
  → 3 Taxonomy migration
  → 4 Prompt rendering
  → 5 Canonical storage
  → 6 Ingestion
  → 7 Retry backlog
  → 8 OpenRouter
  → 9 Filtering
  → 10 Summaries
  → 11 Public projections/contracts
  → 12 Markdown + JSON
      ├→ 13 Website
      └→ 14 iOS foundation
            → 15 Personal state
            → 16 Public cache/networking
            → 17 Today + Browse + Detail
            → 18 Swipe triage
            → 19 Topics
            → 20 Saved
            → 21 iOS resilience/polish
  → 22 Scheduling/automation
  → 23 Validation/operations
  → 24 Core soak
  → 25 Figure extractor evaluation
  → 26 Figure production integration
```

Phases 13 and 14 are independent in the dependency graph after Phase 12, but the repository rule still requires executing one numbered implementation phase at a time. Phase 22 cannot ship until both the website and iPhone core paths have passed their gates. This does not change the technical plan's locked feature order.

## 4. Implementation phases

### Phase 0 — Repository and test skeleton

1. **Files/modules to create**
   - `pyproject.toml`, `.gitignore`, `.env.example`
   - `src/paperflow/__init__.py`, `src/paperflow/main.py`
   - `src/paperflow/generated_files.py`, `src/paperflow/observability.py`
   - `tests/unit/test_bootstrap.py`, `tests/unit/test_generated_files.py`
   - `tests/integration/`, `tests/fixtures/`
   - `.github/workflows/ci.yml`
2. **Dependencies**
   - Prerequisite phases: none.
   - Runtime/tooling: Python 3.12, Pydantic 2, pytest, Ruff. Add no network or iOS dependency here.
3. **Implementation objective**
   - Establish the package layout, typed-test convention, structured run-ID/logging helper, and exact AUTO-GENERATED marker recognition without implementing product behavior.
4. **Unit tests**
   - Package imports; run IDs are parseable and unique; only the exact marker is recognized; manual files never qualify for generated cleanup.
5. **Integration tests**
   - CI installs the editable package and runs the one bootstrap test on a clean checkout.
6. **Manual/simulator validation**
   - Inspect `.gitignore` and `.env.example`; confirm `.env`, cache, temporary files, and secrets are excluded. No simulator work.
7. **Exact exit criteria**
   - `pytest tests/unit/test_bootstrap.py tests/unit/test_generated_files.py` passes, `ruff check .` passes, `python -c "import paperflow"` exits 0, and CI performs the same checks.
8. **Later phases depending on it**
   - Every later phase.

### Phase 1 — Runtime, model, prompt-manifest, and secret configuration

1. **Files/modules to create**
   - `configs/runtime.yaml`, `configs/models.yaml`, `configs/prompts/manifest.yaml`
   - `src/paperflow/config.py`
   - `src/paperflow/cli/validate_config.py`
   - `tests/unit/test_config.py`, `tests/fixtures/configs/`
2. **Dependencies**
   - Prerequisite: Phase 0.
   - Libraries: Pydantic and a YAML parser; environment access remains behind a small injectable loader.
3. **Implementation objective**
   - Validate all runtime, schedule, source, publishing, model-chain, and prompt-manifest settings; load `OPENROUTER_API_KEY` only from process environment; calculate deterministic runtime/model hashes.
4. **Unit tests**
   - Valid config; missing/unknown model alias; empty task chain; invalid timezone/day/time; invalid numeric bounds; secret missing in offline commands; deterministic normalized hashes; model switch is YAML-only.
5. **Integration tests**
   - Load the checked-in config set together and prove source categories, run time, model IDs, and prompt paths are obtained from configuration rather than Python constants.
6. **Manual/simulator validation**
   - Run config validation with and without an API key; the latter may validate non-network operations and must never print environment contents. No simulator work.
7. **Exact exit criteria**
   - `python -m paperflow.cli.validate_config` passes for checked-in configs; config tests and Ruff pass; repository search finds no secret value and no duplicate configured category/model/schedule lists in source.
8. **Later phases depending on it**
   - Phases 2–13 and 22–26; iOS Phase 14 depends on the published contract/base URL rather than Python runtime config.

### Phase 2 — Taxonomy schema and validation

1. **Files/modules to create**
   - `configs/topics.yaml`
   - taxonomy models in `src/paperflow/models.py`
   - `src/paperflow/taxonomy.py`
   - `src/paperflow/cli/validate_taxonomy.py`
   - `tests/unit/test_taxonomy.py`, taxonomy fixtures under `tests/fixtures/taxonomy/`
2. **Dependencies**
   - Prerequisites: Phases 0–1.
   - Use the configured YAML/Pydantic layer; no LLM or network dependency.
3. **Implementation objective**
   - Represent exactly Large Topic → Subtopic, enforce global stable IDs and migration metadata shape, and expose ordered lookup methods based on YAML order.
4. **Unit tests**
   - ID regex; global uniqueness; non-empty descriptions; `previous_ids` collisions; duplicate parents; invalid `moved_from`; cycles/ambiguity; safe path derivation; valid seed taxonomy.
5. **Integration tests**
   - Load the checked-in taxonomy, create its normalized hash, and validate an empty selected store without generating output.
6. **Manual/simulator validation**
   - Review the validator's human-readable errors against one intentionally invalid fixture. No simulator work.
7. **Exact exit criteria**
   - `python -m paperflow.cli.validate_taxonomy` exits 0 for the checked-in taxonomy and nonzero for every invalid fixture; taxonomy tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 3–4, 9, 11–14, 19, and 23–26.

### Phase 3 — Taxonomy snapshots, rename, and re-parent migrations

1. **Files/modules to create**
   - `src/paperflow/taxonomy_migrations.py`
   - `src/paperflow/atomic.py`
   - `tests/unit/test_taxonomy_migrations.py`
   - migration fixtures under `tests/fixtures/taxonomy/migrations/`
2. **Dependencies**
   - Prerequisite: Phase 2.
   - Pure in-memory planning first; filesystem writes use atomic helpers from this phase.
3. **Implementation objective**
   - Compute and print a deterministic diff; resolve identity rename before parent move; validate all rewritten assignments before any canonical save or stale generated-file removal.
4. **Unit tests**
   - Display rename; topic/subtopic ID rename; move; combined rename+move; removal of empty old assignment; no duplicate target; old-parent conflict; removed in-use ID; cycle; rollback on validation failure.
5. **Integration tests**
   - Migrate a multi-paper canonical fixture in memory, regenerate to a temporary directory, validate, then atomically install; inject failure before install and assert every original byte remains.
6. **Manual/simulator validation**
   - Review dry-run diff output for rename, move, and path cleanup. No simulator work.
7. **Exact exit criteria**
   - All migration matrix cases pass; an invalid migration changes no canonical/generated file; only files with the exact generated marker can enter a cleanup plan.
8. **Later phases depending on it**
   - Phases 5, 11–13, 19, 23, and all publication phases.

### Phase 4 — Prompt rendering, versioning, and hashes

1. **Files/modules to create**
   - `configs/prompts/taxonomy_block.j2`
   - `configs/prompts/filter_system.j2`, `filter_user.j2`
   - `configs/prompts/summary_system.j2`, `summary_user.j2`
   - prompt code in `src/paperflow/llm/structured.py`
   - `src/paperflow/cli/prompt_preview.py`
   - `tests/unit/test_prompts.py`
2. **Dependencies**
   - Prerequisites: Phases 1–2.
   - Jinja2 materially simplifies explicit templates and is shared later by site rendering.
3. **Implementation objective**
   - Render prompts deterministically from config/taxonomy, restrict filter paper input to title/abstract/categories, and calculate prompt/taxonomy hashes used by provenance and cache keys.
4. **Unit tests**
   - Stable render/hash; YAML order preserved; taxonomy edit changes filter hash; summary hash independent of taxonomy; prompt contains required KEEP/DROP constraints; user prompt excludes authors/prestige fields.
5. **Integration tests**
   - Render all checked-in prompts through the manifest and validate that every configured template exists and accepts the expected typed context.
6. **Manual/simulator validation**
   - Review `prompt_preview filter`, `summary`, and `taxonomy` output for a fixture paper. No simulator work.
7. **Exact exit criteria**
   - All preview commands exit 0; two identical inputs are byte-identical; semantically changed prompt/taxonomy input changes its relevant hash; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 8–10 and 23–26.

### Phase 5 — Screening ledger, selected store, and run state

1. **Files/modules to create**
   - screening, paper, summary, and run Pydantic models in `src/paperflow/models.py`
   - `src/paperflow/screening_ledger.py`, `paper_store.py`
   - initial schemas/fixtures for `data/papers.json`, `data/state.json`, `data/screening_events/`
   - `tests/unit/test_screening_ledger.py`, `test_paper_store.py`, `test_run_state.py`
2. **Dependencies**
   - Prerequisites: Phases 2–3.
   - Standard-library JSON/JSONL and atomic filesystem helpers; no database.
3. **Implementation objective**
   - Persist every screening attempt append-only, reduce latest state deterministically, keep only full KEEP records in `papers.json`, and withhold run-state success until validated publication.
4. **Unit tests**
   - KEPT/DROPPED/FAILED schema invariants; timestamp/tie determinism; attempt order; corrupt event detection; selected store requires KEEP + assignment; summary/figure status consistency; atomic write interruption.
5. **Integration tests**
   - Append events across monthly ledger files, reload latest state, save/reload a selected store, and prove earlier failed history remains after later success.
6. **Manual/simulator validation**
   - Inspect a sample JSONL ledger and run-state file for audit fields and absence of secrets/full LLM payloads. No simulator work.
7. **Exact exit criteria**
   - Round-trip tests preserve every typed field; invalid canonical state cannot replace the last valid file; latest-state reduction is deterministic; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 7, 9–13, 22–26.

### Phase 6 — arXiv NEW ingestion, normalization, and deduplication

1. **Files/modules to create**
   - `src/paperflow/arxiv_client.py`, `normalize.py`
   - `tests/unit/test_arxiv_client.py`, `test_normalize.py`
   - `tests/fixtures/arxiv_daily_sample.json` and source-failure/zero-result fixtures
2. **Dependencies**
   - Prerequisites: Phases 1 and 5.
   - Injectable HTTP transport. Prefer the already selected HTTP client; use standard XML parsing unless an added feed dependency proves materially safer.
3. **Implementation objective**
   - Fetch configured NEW submissions, normalize versioned IDs to one canonical base ID, merge cross-list categories, exclude replacements from normal flow, and distinguish source failure from a valid empty result.
4. **Unit tests**
   - Version normalization; legacy IDs if supported by fixture; NEW vs replacement; category union; stable dedup order; scientific text preservation; HTTP/parse error mapping; empty success.
5. **Integration tests**
   - The 12-entry fixture yields 10 unique candidates with merged categories and writes raw data only to the gitignored cache.
6. **Manual/simulator validation**
   - Optional read-only live fetch with a recorded run ID; inspect that no canonical/public output is touched. No simulator work.
7. **Exact exit criteria**
   - Fixture counts and identities exactly match the technical plan; total source failure returns a failure outcome, not an empty candidate list; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 7, 9, 22–26.

### Phase 7 — FAILED retry backlog and workset selection

1. **Files/modules to create**
   - `src/paperflow/retry_queue.py`
   - `src/paperflow/cli/reprocess.py`
   - `tests/unit/test_retry_queue.py`
   - second-run retry fixture under `tests/fixtures/pipeline/`
2. **Dependencies**
   - Prerequisites: Phases 5–6.
   - Injectable clock and metadata refetch client.
3. **Implementation objective**
   - Merge today's unseen papers with eligible FAILED backlog entries even when absent from today's feed; enforce cooldown/max attempts; keep exhausted records FAILED; support explicit manual override.
4. **Unit tests**
   - New unseen inclusion; KEPT/DROPPED terminal; failed cooldown boundaries; absent refetch success/failure; dedup against current feed; attempt exhaustion; manual override; timezone-aware timestamps.
5. **Integration tests**
   - Run one fixture with one FAILED paper, omit it on run two, refetch it, and prove it is processed exactly once and receives a new event.
6. **Manual/simulator validation**
   - Dry-run workset report explains inclusion/exclusion reason per paper. No simulator work.
7. **Exact exit criteria**
   - The mandated two-run retry fixture passes; exhausted failures never become DROP; manual reprocess can select an exhausted ID; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 9, 22–26.

### Phase 8 — Single OpenRouter abstraction

1. **Files/modules to create**
   - `src/paperflow/llm/openrouter.py`, `structured.py`
   - LLM result/error models in `src/paperflow/models.py`
   - `tests/unit/llm/test_openrouter.py`, provider response fixtures
2. **Dependencies**
   - Prerequisites: Phases 1 and 4.
   - Injectable HTTP client, bounded backoff/jitter abstraction, Pydantic JSON schema. No provider SDK is required unless it materially reduces contract risk.
3. **Implementation objective**
   - Provide exactly one structured-chat client with model chains, provider/model fallback, separate transient and semantic errors, actual-model/provider/usage/cost capture, and safe headers/secrets.
4. **Unit tests**
   - Success decode; model fallback; 429/5xx/timeout retry; no retry for 400/401/403/config errors; jitter bounds; missing usage; malformed envelope; redacted logs; requested vs actual model.
5. **Integration tests**
   - Stubbed OpenRouter server exercises ordered fallbacks and response metadata without task business logic.
6. **Manual/simulator validation**
   - Opt-in, secret-backed smoke test for each configured model profile after unit tests pass; record model ID/usage without storing prompt payload or secret. No simulator work.
7. **Exact exit criteria**
   - Stub integration passes; YAML-only task-chain changes alter routing without code edits; authorized live smoke tests confirm configured model reachability or produce a documented external availability block; no secret appears in logs/files.
8. **Later phases depending on it**
   - Phases 9–10 and 22–26.

### Phase 9 — Structured filtering and durable outcomes

1. **Files/modules to create**
   - `src/paperflow/llm/filtering.py`
   - filter schemas/validators in `src/paperflow/models.py` and `taxonomy.py`
   - `tests/unit/llm/test_filtering.py`
   - `tests/integration/test_filter_pipeline.py`
2. **Dependencies**
   - Prerequisites: Phases 2, 4–8.
   - OpenRouter abstraction only; concurrency is bounded from runtime config.
3. **Implementation objective**
   - Batch filter title/abstract/categories, validate schema plus taxonomy semantics, salvage valid subset, retry only invalid results once on the next model, and append KEEP/DROP/FAILED events.
4. **Unit tests**
   - Score bounds; KEEP without assignment; DROP with assignment; duplicate/wrong-parent IDs; missing/extra/duplicate result IDs; unmappable envelope; valid-subset salvage; exactly one semantic retry; second failure becomes FAILED.
5. **Integration tests**
   - Ten-paper fixture produces exactly 3 KEEP, 6 DROP, 1 FAILED and ten ledger events; injected malformed result does not discard valid siblings.
6. **Manual/simulator validation**
   - Review a dry-run filter report containing decisions, hashes, and model provenance but no secret. No simulator work.
7. **Exact exit criteria**
   - No tested malformed path yields DROP by default; every candidate receives one durable terminal-attempt event; expected fixture counts pass; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 10–13 and 22–26.

### Phase 10 — Summaries, cache, retry, and abstract fallback

1. **Files/modules to create**
   - `src/paperflow/llm/summarization.py`
   - cache helpers under `src/paperflow/llm/structured.py`
   - `tests/unit/llm/test_summarization.py`, `test_llm_cache.py`
   - `tests/integration/test_summary_pipeline.py`
2. **Dependencies**
   - Prerequisites: Phases 4, 5, 8–9.
   - Same OpenRouter client; local cache is optional for correctness and gitignored.
3. **Implementation objective**
   - Summarize KEEP papers only, enforce one TL;DR and 3–5 bullets, retry independently from screening, preserve selection on failure, and expose abstract fallback through later public projections.
4. **Unit tests**
   - KEEP-only targeting; schema bounds; cache key components; stale-cache rejection; transient/semantic failure; retry success; status transitions; failure leaves canonical paper selected.
5. **Integration tests**
   - Run mixed success/failure summaries and prove all three KEEP papers remain in the selected store and views receive fallback content for the failed one.
6. **Manual/simulator validation**
   - Preview summary prompt and inspect generated/fallback records. No simulator work.
7. **Exact exit criteria**
   - Summary failure never removes or unassigns a selected paper; cache invalidates for abstract/prompt/model changes; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 11–13, all iOS phases, and 22–26.

### Phase 11 — Shared public projections and contract freeze

1. **Files/modules to create**
   - `src/paperflow/render/view_models.py`, `contracts.py`
   - `tests/unit/render/test_view_models.py`, `test_contracts.py`
   - versioned valid/invalid public JSON fixtures under `tests/fixtures/contracts/v1/`
2. **Dependencies**
   - Prerequisites: Phases 2–3, 5, and 9–10.
   - The resolved contracts in Section 6 must be frozen in the V1 golden fixtures before downstream implementation.
3. **Implementation objective**
   - Build one deterministic projection for paper membership, ordering, topic labels, required public abstract/fallback, unique and per-view full-history counts, day grouping, and publication-root URL fields; all renderers and the app consume this contract.
4. **Unit tests**
   - Unique canonical membership; multi-topic fan-out; parent-only assignments; config-order labels; day/per-view totals; newest-first ordering; required abstract; explicit day/topic feed URLs; safe publication-root URL rules; null figure states; public-field allowlist; fallback behavior.
5. **Integration tests**
   - Compare projected membership/counts across global, day, large-topic, and subtopic views for the canonical fixture.
6. **Manual/simulator validation**
   - Review the versioned JSON contract and its change policy before downstream implementation. No simulator work.
7. **Exact exit criteria**
   - V1 schemas and golden fixtures are approved; every count equals the corresponding projected collection length; no private/retry/secret fields leak; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 12–14, 16–21, and 23–26.

### Phase 12 — Markdown and full-history JSON publication

1. **Files/modules to create**
   - `src/paperflow/render/markdown.py`, `json_api.py`, `validation.py`
   - `src/paperflow/cli/rebuild_outputs.py`
   - generated targets: `README.md`, `daily/`, `topics/`, `data/feed_index.json`, `data/daily_feeds/`, `data/topics.json`, `data/topic_feeds/`
   - `tests/unit/render/test_markdown.py`, `test_json_api.py`, `test_cleanup.py`
   - `tests/integration/test_generated_outputs.py`
2. **Dependencies**
   - Prerequisites: Phases 3 and 11.
   - Pure deterministic renderers and atomic filesystem install.
3. **Implementation objective**
   - Render one Markdown table schema, cap only root README at 80, publish exact full-history daily/topic JSON and Markdown counts, generate empty configured topic pages, and safely clean stale generated files.
4. **Unit tests**
   - README at 0/1/79/80/81/500; escaping; stable sort; zero-day success; feed index totals; daily/topic membership; multi-topic fan-out; marker-only cleanup; `rebuild_outputs` makes no network calls.
5. **Integration tests**
   - Generate all artifacts into a temporary tree, validate cross-format membership/counts/links, inject a validation error, and prove canonical/live outputs remain byte-identical.
6. **Manual/simulator validation**
   - Inspect one daily archive, one empty subtopic, one multi-topic paper, and README row 80/81 boundary. No simulator work.
7. **Exact exit criteria**
   - Generated validation passes; README has at most 80 rows while every other applicable view retains all fixture papers; rebuild is deterministic and network-free; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 13–14, 16–26.

### Phase 13 — Static website

1. **Files/modules to create**
   - `src/paperflow/render/website.py`
   - website templates/assets under `src/paperflow/render/templates/site/` and `site/assets/`
   - generated `site/index.html`, `site/days/`, `site/topics/`
   - `tests/unit/render/test_website.py`, `tests/integration/test_website_contract.py`
2. **Dependencies**
   - Prerequisites: Phases 11–12.
   - Reuse Jinja2 and shared projections; no client framework unless proven necessary.
3. **Implementation objective**
   - Publish full global/topic/subtopic history grouped by day with exact per-view counts, stable taxonomy-derived routes, placeholder figures, and older-day navigation.
4. **Unit tests**
   - Route derivation; HTML escaping; day headers/counts; empty pages; null/failed/ready figure rendering; pagination/day links; no 80-limit import.
5. **Integration tests**
   - Crawl generated internal links and compare all website memberships/counts with JSON and Markdown projections.
6. **Manual/simulator validation**
   - Serve `site/` locally and inspect root, old day, topic, subtopic, zero-result, and placeholder states at narrow/desktop widths.
7. **Exact exit criteria**
   - Link crawl has zero failures; full-history memberships/counts exactly match Phase 12; all history remains reachable; tests and Ruff pass.
8. **Later phases depending on it**
   - Phases 22–26. iOS does not depend on website presentation.

### Phase 14 — iOS project, public models, theme, and shared components

1. **Files/modules to create**
   - `ios/PaperFlow/PaperFlow.xcodeproj` and app/test/UI-test targets
   - `App/PaperFlowApp.swift`, `Views/Root/RootTabView.swift`
   - `Models/PublicFeedModels.swift`
   - `Networking/PublicFeedClientProtocol.swift`
   - `Theme/PaperFlowTheme.swift`
   - shared components: navigation/section headers, buttons, tags, progress, figure/thumbnail placeholder, list card, loading/empty/error shells
   - `PaperFlowTests/PublicFeedDecodingTests.swift`, `ThemeTests.swift`
2. **Dependencies**
   - Prerequisites: Phases 11–12.
   - SwiftUI, Foundation, Observation as supported, and Apple test frameworks only; no third-party package initially.
3. **Implementation objective**
   - Build the app shell with exactly three independent navigation stacks, no speculative Today/Topics Search or Settings controls, semantic design tokens, Codable V1 public models, injectable networking, reusable visuals, accessibility identifiers, and a publication-root base URL via `.xcconfig`/Info.plist.
4. **Unit tests**
   - Decode every golden/invalid JSON contract including required abstract and explicit feed URLs; versionless ID normalization; publication-root URL resolution/rejection; theme/token invariants; count mismatch rejection.
5. **Integration tests**
   - App target loads bundled fixture data through a fake client and renders the three root tabs without network access.
6. **Manual/simulator validation**
   - Build and launch on the agreed simulator; verify only Today/Topics/Saved tabs, native safe areas, 44-point targets, semantic colors, Dynamic Type growth, and stable placeholder geometry.
7. **Exact exit criteria**
   - Relevant scheme builds; iOS unit tests pass; fixture launch shows exactly three tabs; no API key/base URL literal appears in Swift; baseline shell screenshot is captured.
8. **Later phases depending on it**
   - Phases 15–21 and 26.

### Phase 15 — SwiftData personal state and state machine

1. **Files/modules to create**
   - `Models/PersonalPaperState.swift`, `Models/SavedPaperSnapshot.swift`, `Models/ReadingStatus.swift`
   - `Storage/PersonalPaperStore.swift`, `Storage/SwiftDataPersonalPaperStore.swift`
   - `Storage/PersonalActionService.swift`, `Storage/SwipeUndoSnapshot.swift`
   - `PaperFlowTests/PersonalStateMachineTests.swift`, `SwiftDataPersistenceTests.swift`
2. **Dependencies**
   - Prerequisite: Phase 14.
   - SwiftData and injectable clock/model container.
3. **Implementation objective**
   - Keep exactly one personal state per canonical versionless ID; implement first/last Save, Unsave, reading/completion/open timestamps and retained history; make Save, Skip, Unsave, reading transitions, notes, rating, snapshots, and one-action undo atomic and immediately observable across tabs.
4. **Unit tests**
   - Initial Save/Skip; repeated Save idempotence; Save preserves reading/done; Skip preserves saved state; Unsave retains review/status/timestamps/note/rating/snapshot; resave updates `last_saved_at` but preserves first `saved_at`; all legal/illegal status transitions; last-opened rules; exact prior-state restoration; v1/v2 ID collision.
5. **Integration tests**
   - In-memory and disk-backed SwiftData tests prove restart persistence, uniqueness, atomic mutation, snapshot independence from public cache, and cross-context observation.
6. **Manual/simulator validation**
   - Use a temporary store to mutate one paper from two views, terminate/relaunch, and inspect consistent state. Network disabled.
7. **Exact exit criteria**
   - State-machine table in `TEST_PLAN.md` passes; duplicate canonical IDs are prevented; a failed store transaction leaves the prior record intact; all personal mutations work with no network.
8. **Later phases depending on it**
   - Phases 17–21 and 26.

### Phase 16 — Public networking, validated cache, and repositories

1. **Files/modules to create**
   - `Networking/PublicFeedClient.swift`, `Networking/Endpoint.swift`
   - `Storage/PublicFeedCache.swift`, `Storage/FilePublicFeedCache.swift`
   - `Repositories/PaperFlowRepository.swift`
   - `PaperFlowTests/PublicFeedClientTests.swift`, `PublicFeedCacheTests.swift`, `RepositoryTests.swift`
2. **Dependencies**
   - Prerequisites: Phases 14–15.
   - URLSession async/await, injectable session/clock/filesystem; no API secret.
3. **Implementation objective**
   - Fetch index/topics and their explicitly published day/topic URLs lazily, resolve every relative URL against the configured publication root, validate schema and counts before replacing cache, retain last-success metadata, and keep public-cache failure isolated from SwiftData.
4. **Unit tests**
   - Endpoint construction; status/timeout/invalid JSON/version/count errors; relative URLs; cancellation; atomic cache replace; corrupt-cache quarantine; stale-but-valid read; personal store untouched.
5. **Integration tests**
   - Stub server transitions online → invalid refresh → offline; repository continues serving last valid index/feeds and Saved snapshots.
6. **Manual/simulator validation**
   - Launch fixture build online, disable network, relaunch, and verify cached collection availability plus last-updated metadata.
7. **Exact exit criteria**
   - Every valid contract decodes; mismatched payload never replaces valid cache; cache deletion does not remove Saved snapshots/personal state; unit/integration tests and scheme build pass.
8. **Later phases depending on it**
   - Phases 17–21 and 26.

### Phase 17 — Today, Day Browse, and shared Paper Detail

1. **Files/modules to create**
   - `Views/Today/TodayHomeView.swift`, `DayOverviewView.swift`, `DayBrowseView.swift`
   - `Views/Paper/PaperDetailView.swift` plus summary, metadata, personal-state, and external-action sections
   - `ViewModels/TodayViewModel.swift`, `DayBrowseViewModel.swift`, `PaperDetailViewModel.swift`
   - `PaperFlowTests/TodayViewModelTests.swift`, `PaperDetailViewModelTests.swift`
   - `PaperFlowUITests/TodayBrowseTests.swift`
2. **Dependencies**
   - Prerequisites: Phases 14–16.
   - Native `searchable`, menus, Safari/openURL; no in-app PDF reader.
3. **Implementation objective**
   - Bind Today to the current date in the feed index's configured IANA publication timezone, distinguish present zero-day from absent feed, label an older prefetched day Latest Available, show all history and exact public/personal counts, and provide deterministic Browse sorts/status/topic filters plus one shared detail screen with required abstract fallback and placeholder figures.
4. **Unit tests**
   - Progress math; valid/invalid IANA timezone and device-travel boundary; current-day present/zero/absent/offline cases; Latest Available labeling; ordering/sorts; Browse visibility does not mutate state; Save semantics; detail sections for generated/failed summary and figure states; no Today Search/Settings affordance.
5. **Integration tests**
   - Fake repository + SwiftData proves Today and Detail update from one personal state and return to prior browse position/navigation stack.
6. **Manual/simulator validation**
   - Validate Today Home, Day Overview, Browse, and Detail against written hierarchy and reference board; test long titles, zero day, 81+ history, Dynamic Type, and placeholder screenshots.
7. **Exact exit criteria**
   - Exact server paper counts display; Browse render/open alone never marks reviewed; Save updates all visible instances immediately; papers older than newest 80 are reachable; unit/UI tests pass and screenshots are captured.
8. **Later phases depending on it**
   - Phases 18–21 and 26.

### Phase 18 — Reusable Swipe triage, resume, undo, and completion

1. **Files/modules to create**
   - `Views/Components/PFSwipeCard.swift`, `PFSwipeActionBar.swift`
   - `Views/Today/DaySwipeView.swift`, `TriageCompleteView.swift`
   - `ViewModels/SwipeSessionViewModel.swift`, `Models/SwipeCollection.swift`
   - `PaperFlowTests/SwipeSessionTests.swift`
   - `PaperFlowUITests/SwipeTriageTests.swift`
2. **Dependencies**
   - Prerequisites: Phases 15–17.
   - SwiftUI gestures/animation and UIFeedbackGenerator wrappers with injectable no-op test implementation.
3. **Implementation objective**
   - Provide one collection-agnostic deck: left=reviewed/skip, right=reviewed/save/queue, buttons=gestures, consistent reviewed/total plus remaining copy, global eligibility, persisted-state resume, one exact undo, detail round-trip, restrained completion.
4. **Unit tests**
   - Eligibility after public filters and review mode; reviewed/total/remaining progress denominator/copy; first-time/already-saved actions; reading/done preservation; left on saved; exact undo variants; no-action undo disabled; resume rebuild; detail open/back no mutation; completion.
5. **Integration tests**
   - Real in-memory SwiftData plus fake collection verifies action → cross-view update → app recreation → remaining deck; undo restores prior database state and card position.
6. **Manual/simulator validation**
   - Gesture thresholds, max rotation, tint, haptics, buttons, deck stack, sticky detail actions, relaunch resume, and All Done screen; capture Swipe and completion screenshots.
7. **Exact exit criteria**
   - Gesture/button command parity is proven; no human action mutates public/AI fields; all undo cases restore exact prior state; restart resumes remaining unreviewed papers; unit/UI tests and screenshots pass.
8. **Later phases depending on it**
   - Phases 19 and 21; Saved Phase 20 consumes state but not the deck UI.

### Phase 19 — Topics and full-history topic/subtopic flows

1. **Files/modules to create**
   - `Views/Topics/TopicsHomeView.swift`, `TopicDetailView.swift`, `TopicBrowseView.swift`, `SubtopicBrowseView.swift`, `TopicSwipeView.swift`
   - `ViewModels/TopicsViewModel.swift`, `TopicHistoryViewModel.swift`
   - `PaperFlowTests/TopicsViewModelTests.swift`
   - `PaperFlowUITests/TopicsTests.swift`
2. **Dependencies**
   - Prerequisites: Phases 14–18.
   - Reuses public repository, cards, shared detail, and swipe engine.
3. **Implementation objective**
   - Render taxonomy/counts and explicit feed URLs entirely from `topics.json`; label the top count Total Papers as unique canonical membership; open complete large-topic/subtopic histories with per-view day counts; support All/Unread/Saved Browse and globally-unreviewed Swipe.
4. **Unit tests**
   - Dynamic hierarchy; unique overall count semantics versus overlapping row counts; explicit feed URL use; topic/subtopic membership; multi-assignment identity; per-view daily counts; All/Unread/Saved predicates; history lazy loading; no hard-coded topic labels or root Search/Settings.
5. **Integration tests**
   - Skip/save a multi-topic paper in Today, then verify topic Browse and Swipe immediately reflect the same state without duplicate records.
6. **Manual/simulator validation**
   - Compare Topics Home, Topic Detail, Subtopic Browse, and Swipe to written spec/reference hierarchy using the actual seed taxonomy rather than mock labels; capture screenshots.
7. **Exact exit criteria**
   - A taxonomy fixture changed without rebuilding Swift source changes rendered rows/routes; all history and counts match feeds; reviewed papers are absent from default topic decks; tests/build/screenshots pass.
8. **Later phases depending on it**
   - Phases 21 and 26.

### Phase 20 — Saved deep-read library

1. **Files/modules to create**
   - `Views/Saved/SavedHomeView.swift`, `QueueView.swift`, `ReadingView.swift`, `DoneView.swift`
   - reusable saved/reading rows, status picker, note editor, rating control
   - `ViewModels/SavedViewModel.swift`, `SavedSearch.swift`
   - `PaperFlowTests/SavedViewModelTests.swift`
   - `PaperFlowUITests/SavedTests.swift`
2. **Dependencies**
   - Prerequisites: Phases 14–17.
   - SwiftData local queries; native `searchable` and menus.
3. **Implementation objective**
   - Deliver Queue/Reading/Done; Saved-only local search; `last_saved_at`, `last_opened_at`, and `completed_at` backed sorts; status changes, notes, optional 1–5 rating, history-preserving Unsave/resave, external links, and offline-independent retained snapshots. Omit unsupported activity, import, and fake reading-progress features.
4. **Unit tests**
   - Status counts/filters; every timestamp and supported sort/fallback/tie-break; case/diacritic-insensitive title/author/display-summary/topic/subtopic/note search; note autosave; rating set/remove; exact Unsave/resave retention; fresh public metadata refresh preserves personal fields; missing source cache.
5. **Integration tests**
   - Save from Today/Topics/Detail, update Reading/Done/notes/rating in Saved, remove originating public caches, restart offline, and verify one intact library record and correct counts.
6. **Manual/simulator validation**
   - Validate Saved Home, Queue, Reading, Done, note editor, rating, long titles, empty states, and screenshots. Do not show reading percentages without meaningful reader progress data.
7. **Exact exit criteria**
   - Every saved canonical ID appears once; status/note/rating survive restart/offline; Unsave never removes public history or review state; search/sorts are backed by stored fields; unit/UI tests and screenshots pass.
8. **Later phases depending on it**
   - Phases 21 and 26.

### Phase 21 — iOS offline/error/loading polish, accessibility, and restoration

1. **Files/modules to create**
   - finalized `PFLoadingSkeleton`, `PFEmptyState`, `PFErrorBanner`, offline indicator
   - refresh/navigation restoration coordinators and haptic abstraction
   - accessibility identifiers/labels throughout important controls
   - `PaperFlowTests/OfflineBehaviorTests.swift`, `AccessibilityTests.swift`
   - `PaperFlowUITests/OfflineTests.swift`, `NavigationRestorationTests.swift`, `AccessibilityUITests.swift`
   - reviewed screenshots under `docs/ui/screenshots/` if the repository adopts checked-in artifacts
2. **Dependencies**
   - Prerequisites: Phases 17–20.
   - Native refresh, accessibility, animation, and state-restoration APIs.
3. **Implementation objective**
   - Complete contextual loading/empty/error/offline behavior, pull-to-refresh, last-updated state, independent tab navigation, restrained animation/haptics, Dynamic Type, non-color status cues, and safe areas.
4. **Unit tests**
   - Refresh state transitions; cached error banner; valid-zero vs error; tab route preservation; accessibility label/count strings; haptic trigger rules; reduced-motion behavior where supported.
5. **Integration tests**
   - Online → cached → malformed refresh → offline across app restart while personal mutations continue; public and personal stores fail independently.
6. **Manual/simulator validation**
   - Test small and large iPhone simulators, light mode, largest practical Dynamic Type, VoiceOver labels/focus, reduced motion, network loss, long titles, and tab/scroll restoration; capture final screen matrix.
7. **Exact exit criteria**
   - Relevant scheme builds and all iOS unit/UI tests pass; no blank loading screen; cached content survives failed refresh; personal actions work offline; all primary targets are at least 44×44; required screenshots pass written-spec review.
8. **Later phases depending on it**
   - Phases 22, 24, and 26.

### Phase 22 — Schedule gate and GitHub automation

1. **Files/modules to create**
   - `src/paperflow/schedule.py`, `src/paperflow/cli/sync_schedule.py`
   - `.github/workflows/paperflow-daily.yml`
   - `tests/unit/test_schedule.py`, `tests/integration/test_workflow_sync.py`
2. **Dependencies**
   - Prerequisites: Phases 12–13 and iOS core through Phase 21; pipeline Phases 5–10.
   - Standard timezone support, GitHub Actions, repository secret `OPENROUTER_API_KEY` supplied outside source.
3. **Implementation objective**
   - Generate DST-safe cron candidates from runtime config, gate execution by configured local day/time and last success, serialize writers, validate before commit, and ensure failed runs push nothing.
4. **Unit tests**
   - EST/EDT conversion; DST boundaries; disabled/disallowed day; early/late trigger; same-day duplicate; catch-up; manual bypass; stale workflow block; deterministic generated block.
5. **Integration tests**
   - Exercise workflow commands in a temporary Git repository: success commits the exact allowlist; no-op produces no commit; ingestion/validation failure leaves index/HEAD unchanged.
6. **Manual/simulator validation**
   - Review generated workflow permissions/concurrency/secret use; run manual dispatch, then observe two real scheduled executions. No simulator change unless consuming resulting feed as an E2E check.
7. **Exact exit criteria**
   - `sync_schedule --check` passes; CI detects a deliberately stale block; manual run succeeds; two consecutive real due schedules finish without repair or duplicate publication; failure drill pushes nothing.
8. **Later phases depending on it**
   - Phases 23–26.

### Phase 23 — Validation, observability, maintenance CLI, and full regression

1. **Files/modules to create**
   - complete `src/paperflow/render/validation.py`, `observability.py`
   - `src/paperflow/cli/rebuild_outputs.py`, `reclassify.py`, finalized `reprocess.py`
   - persisted `data/run_stats/` schema
   - validation/CLI/metrics tests under `tests/unit/` and `tests/integration/`
2. **Dependencies**
   - Prerequisites: Phases 0–22.
   - No new production service; commands reuse existing injectable clients/renderers.
3. **Implementation objective**
   - Validate every config, taxonomy, state, Markdown, JSON, website, filesystem-safety, and run invariant; report observed KEEP/DROP/FAILED and actual model/cost data; support explicit safe maintenance operations.
4. **Unit tests**
   - Every validator rule; structured event names/redaction; metrics arithmetic; reclassification selection; rebuild network prohibition; manual reprocess; canonical/output mismatch detection.
5. **Integration tests**
   - Full first/second-run fixture, taxonomy migration, reclassify, rebuild, and failure rollback; invoke the exact completion commands from `AGENTS.md`.
6. **Manual/simulator validation**
   - Read one success and one failure report; confirm `KEEP cap: NONE`, actual models/cost, source status, and no abstracts/secrets in noisy logs. Run final iOS regression against generated fixture feeds.
7. **Exact exit criteria**
   - `pytest`, `ruff check .`, and `python -m paperflow.cli.validate_taxonomy` all pass; full iOS unit/UI suites and relevant scheme build pass; all generated outputs validate; maintenance dry runs change nothing.
8. **Later phases depending on it**
   - Phases 24–26.

### Phase 24 — Multi-day core soak with figures disabled

1. **Files/modules to create**
   - No product module. Persist normal `data/run_stats/YYYY-MM-DD.json`; store a dated soak report under `docs/testing/results/`.
2. **Dependencies**
   - Prerequisites: Phases 0–23.
   - Production-like schedule/network/secret environment; `figures.enabled=false` remains locked.
3. **Implementation objective**
   - Demonstrate real operational stability before any PDF work: retries, dedup, migration stability, atomic publication, counts, cost, caches, and private iPhone state.
4. **Unit tests**
   - No new unit scope; rerun the complete regression suite on every change arising from soak findings.
5. **Integration tests**
   - At least five consecutive successful local-date runs, including an injected filter failure recovered from backlog while absent from the next source, a summary failure fallback, and one source-failure/no-publication drill.
6. **Manual/simulator validation**
   - On at least two soak outputs, refresh iPhone, review/Save offline, restart, and confirm history/count/state stability; spot-check website/README/topic membership.
7. **Exact exit criteria**
   - Five consecutive due runs require no manual repair; zero missed eligible retries, duplicate IDs, partial commits, count mismatches, state loss, or unexplained cost anomalies; all regressions remain green; a signed/dated soak report records evidence.
8. **Later phases depending on it**
   - Phases 25–26 only. Figure work is forbidden before this gate.

### Phase 25 — Final-workstream figure extractor evaluation

1. **Files/modules to create**
   - `src/paperflow/figures/models.py`, extractor adapter interfaces/evaluation harness
   - `src/paperflow/figures/adapters/pdffigures2.py`, `docling.py`
   - label manifest under `tests/fixtures/figures/evaluation_labels.json`; PDFs remain in gitignored `cache/pdf/`
   - `tests/unit/figures/test_adapters.py`, `test_evaluation.py`
   - measured decision report under `docs/architecture/decisions/`
2. **Dependencies**
   - Hard prerequisite: Phase 24 exit.
   - At least 50 representative KEEP papers; PDFFigures2/JVM and Docling installed as isolated optional tooling, not core dependencies.
3. **Implementation objective**
   - Compare detection recall, crop correctness, caption association, hero top-1 accuracy, runtime, failure rate, and deployment complexity; select the default extractor from recorded evidence.
4. **Unit tests**
   - Adapter normalization; metadata schema; invalid bbox/image; timeout/process failure; deterministic metric aggregation; missing label/PDF handling.
5. **Integration tests**
   - Run both extractors over the same 50+ labeled corpus in a controlled environment and emit reproducible per-paper and aggregate results.
6. **Manual/simulator validation**
   - Human review of crops/captions/top choice for every labeled paper; no iOS feature change yet.
7. **Exact exit criteria**
   - Dataset spans every layout class required by the technical plan; both candidates have complete measured results; decision report names the selected default and rationale; adapter tests pass; core regression remains green.
8. **Later phases depending on it**
   - Phase 26 only.

### Phase 26 — Non-blocking figure production and hero publication

1. **Files/modules to create**
   - `src/paperflow/figures/extract.py`, `score.py`, finalized `models.py`
   - `src/paperflow/cli/rebuild_figures.py`
   - generated `figures/<arxiv_id>/hero.webp`
   - figure worker integration in `src/paperflow/main.py` and render contracts
   - `tests/unit/figures/test_score.py`, `tests/integration/test_figure_pipeline.py`
   - iOS figure-state integration tests/UI screenshots
2. **Dependencies**
   - Prerequisite: Phase 25.
   - Selected extractor only in the production figure extra; image conversion supporting WebP; low bounded PDF concurrency.
3. **Implementation objective**
   - Download PDFs for KEEP papers only into gitignored cache, extract metadata, choose a hero deterministically, publish bounded WebP, and preserve publication/UI behavior for ready/null/failed states.
4. **Unit tests**
   - Keyword/area/aspect/table/page scoring; deterministic tie-break; output dimensions/quality; KEEP-only downloads; status transitions; malformed PDF; no-figure; timeout; rebuild-one-paper.
5. **Integration tests**
   - Success, no-figure, corrupt PDF, extractor crash, and image-write failure all run through full publication; only success emits a hero URL and no failure blocks other papers or the run.
6. **Manual/simulator validation**
   - Inspect representative web/iPhone cards and shared detail for `ready`, `failed`, and null figures; verify aspect-fit detail, clipped thumbnail, no layout jump, and placeholder consistency; capture screenshots.
7. **Exact exit criteria**
   - Figure failure never blocks selection, summaries, publication, Browse, Swipe, Saved, or personal actions; published URLs resolve; image constraints pass; full Python/iOS/website regression passes; placeholder behavior remains unchanged for missing figures.
8. **Later phases depending on it**
   - None; this is the final implementation phase.

## 5. Phase-level verification policy

After each code change, run the narrowest affected test file. Before closing each Python phase, run its unit and integration slice plus `ruff check` on touched code. Before closing any phase that changes generated contracts, run every downstream contract consumer test. Before closing an iOS phase, build the scheme, run affected unit tests, run affected XCUITests for changed interactions, and capture a simulator screenshot for changed UI.

Before any Python task is reported complete, run exactly:

```bash
pytest
ruff check .
python -m paperflow.cli.validate_taxonomy
```

Before any iOS task is reported complete, record the exact `xcodebuild` project/workspace, scheme, simulator destination, build result, unit-test result, affected UI-test result, and screenshot path.

## 6. Resolved source decisions

The earlier contradictions and contract gaps are now closed in both authoritative specifications. These decisions are implementation requirements, not remaining questions.

### R-1 — Public abstract contract

Every public daily/topic paper includes the full original `abstract`. Paper Detail reads it directly, and failed/missing summary content falls back to it. No second detail endpoint is needed in V1.

### R-2 — Personal timestamps and Saved sorting

Personal state includes first/last Save, Unsave, reading-status transition, reading-start, completion, and last-opened timestamps. Queue defaults to `last_saved_at DESC`; Reading uses `last_opened_at DESC` with the specified status/save fallback; Done uses `completed_at DESC`. No PDF percentage is inferred.

### R-3 — Non-destructive Unsave/resave

Unsave sets `saved=false` and `unsaved_at=now`, removes the item from Saved queries/counts, and retains review state, first/last Save, reading state/timestamps, last opened, note, rating, and offline snapshot. Resave updates `last_saved_at`, clears `unsaved_at`, and restores the retained state. Permanent personal-history deletion is outside V1.

### R-4 — Publication-timezone Today semantics

Today binds to the current date in the IANA publication timezone supplied by `feed_index.json`; device travel does not change feed-day identity. A present zero-count current day is a successful empty state. If current date is absent, show “Today's feed isn't available yet” and an older prefetched day as “Latest Available”; never relabel it as today or guess the cause.

### R-5 — Swipe progress wording

All day/topic/subtopic decks display `<reviewed> of <total> reviewed` and `<remaining> remaining`. Session position remains separate and never changes those persisted collection counts.

### R-6 — Unique Topics total

`topics.json.total_paper_count` counts unique canonical KEEP papers. The Topics root labels it `Total Papers`; topic-row counts may overlap and are not summed.

### R-7 — Saved-only search and no speculative controls

V1 search is local to Saved. Today and Topics have no Search or Settings buttons. A future global search or Settings surface requires a separate written specification.

### R-8 — Runtime taxonomy over PNG labels

All taxonomy labels/counts come from `topics.yaml` through published JSON. PNG taxonomy content is illustrative and only informs hierarchy, density, spacing, and visual tone.

### R-9 — Mock-only features omitted

Core V1 omits streaks, all-time counters, quote, confetti, tomorrow preview, topic analytics/activity, import shortcuts, and fabricated reading percentages. Their presence in a reference board creates no requirement.

### R-10 — Publication-root URL contract

The configured absolute `base_url` ends in `/` and denotes the publication root. `feed_index.json` and `topics.json` explicitly publish every feed URL; the app never derives topic paths. All generated relative paths resolve from `base_url`, use validated/encoded safe segments, and exclude leading slash, traversal, backslash, query, and fragment. `hero_figure` follows the same rule; arXiv/PDF links remain absolute HTTPS.

## 7. Explicitly deferred or excluded from core V1

- Author/citation/prestige ranking, recommendation from reading history, vector/global semantic search, social functions, push notifications, AI chat, extra taxonomy levels, and automatic taxonomy creation.
- A fourth tab, dedicated Swipe tab, global Search tab, dashboard analytics, streaks, badges, leaderboards, quotes, confetti, tomorrow preview, and unsupported import shortcuts.
- In-app PDF reader and fabricated reading percentages. Open PDF uses native external/Safari behavior until separately specified.
- Optional CloudKit sync, onboarding, topic overview analytics, recent-activity log, tappable topic-pill navigation, and dark-mode visual launch polish. Architecture must not block them, but they are not core exit criteria.
- PDF download, figure extraction, figure understanding, and real hero publication before Phase 25.

## 8. Required completion report for each implemented phase

Every future phase handoff must list:

- files changed;
- behavior implemented;
- unit, integration, build, UI, simulator, and validation commands actually run;
- exact pass/fail counts and command exit results;
- screenshot paths when UI changed;
- remaining known issues, deferred options, and any deviation from the resolved decisions in Section 6.
