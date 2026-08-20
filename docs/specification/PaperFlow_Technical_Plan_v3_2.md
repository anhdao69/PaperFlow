# PaperFlow — Final Technical Implementation Plan v3.2

> **Status: authoritative final implementation specification.**
>
> This document supersedes PaperFlow Technical Implementation Plan v2, Final v3, and v3.1 wherever there is a conflict. It incorporates the v3 correctness feedback, adds a config-first runtime/model/prompt system, hardens retry/state handling, deliberately moves **all PDF/figure extraction work to the final implementation phase**, clarifies that the **80-paper limit applies only to the root GitHub README**, and adds the complete iPhone functional specification for daily browsing, topic browsing, swipe triage, personal saving, and deep-read tracking. The iPhone app, website, topic/subtopic archives, and public feeds expose the complete KEEP history.
>
> **Contract-closure revision:** 2026-08-20. Public abstract delivery, feed URL resolution, publication-timezone Today behavior, progress copy, unique Topics totals, Saved-only search, personal timestamps, and Unsave/resave retention are fully specified below.
>
> **Date of external model verification:** 2026-08-20.

---

# 0. Final Decisions at a Glance

These decisions are locked for the first production version.

1. **Source:** arXiv new submissions from configured categories.
2. **Filtering input:** title + abstract + arXiv categories only.
3. **No author/reputation filtering:** no h-index, institution, citation count, or author prestige.
4. **Taxonomy:** exactly two structural levels: **Large Topic → Subtopic**.
5. **Taxonomy source of truth:** `configs/topics.yaml`.
6. **LLM provider:** **OpenRouter only** for V1.
7. **Supported model pool:**
   - DeepSeek V4 Flash
   - GLM 4.7 Flash (internally may use the requested alias `glm_4_7_flashx`)
   - GPT-5.6 Luna
   - Mistral Small 4
8. **Default model use:** DeepSeek V4 Flash for filtering; GPT-5.6 Luna for summaries; all four are available as configured fallbacks/alternatives.
9. **KEEP count:** **no daily KEEP cap**. If 8 papers are relevant, keep 8. If 120 are relevant, keep 120.
10. **Root README only:** the root GitHub `README.md` shows the latest **80 selected papers** for readability. This is the **only place** where the 80-paper presentation limit applies.
11. **App/website/topic history:** the iPhone app, website, large-topic archives, subtopic archives, and public feed APIs expose the **complete history of every KEEP paper**. They must never inherit the README 80-paper truncation.
12. **Daily counts:** iPhone and website paper lists are grouped by day and display an explicit KEEP count for each day (for example, `2026-08-20 · 42 papers`).
13. **Every filter outcome is durable:** KEEP, DROP, and FAILED decisions are persisted.
14. **FAILED papers are retried from a retry backlog**, not only if they happen to reappear in a later arXiv feed.
15. **KEEP requires at least one topic assignment** at schema-validation time.
16. **Taxonomy migration supports both ID rename and subtopic re-parenting.**
17. **Summary failures never unselect a paper.** The UI falls back to the abstract.
18. **Figure extraction is not part of the initial critical path.**
19. **iPhone figure area ships immediately with a placeholder.** The same UI component later swaps in a real figure URL without a schema redesign.
20. **Figure extraction is the final implementation task after ingestion, filtering, summaries, outputs, scheduling, website, and iPhone behavior are stable.**
21. **Primary iPhone tabs:** `Today`, `Topics`, and `Saved`.
22. **Every day and every subtopic supports both Browse and Swipe triage flows.**
23. **Human swipe state is separate from AI screening state.** Swipe Left/Skip never becomes `DROP`; Swipe Right/Save never becomes pipeline `KEEP`.
24. **Swipe Right means Save for Deep Read.** It creates/updates one personal record keyed by the canonical versionless arXiv ID and places the paper in the `queue` reading state.
25. **Swipe Left means reviewed/skip.** It marks the paper as seen without removing it from PaperFlow history.
26. **Seen and Saved state are global per paper across day/topic/subtopic views.** The same paper must not be repeatedly presented as unreviewed in multiple collections unless the user explicitly chooses an all-papers/review-again mode.
27. **Personal interaction state is private app data**, persisted separately from `papers.json`, screening events, public JSON feeds, and generated website/Markdown outputs.
28. **Swipe progress resumes across launches**, and the user can undo the most recent swipe action.
29. **Saved is a Deep Read Queue**, supporting `queue`, `reading`, and `done` states plus personal notes and optional personal rating.
30. **Saving remains functional offline.** Network or sync failure must never prevent a local Save/Skip/reading-status update.
31. **Public paper JSON includes the full original abstract.** This is the canonical Paper Detail and failed-summary fallback source.
32. **All published relative URLs resolve from one configured publication-root base URL.** Feed URLs are emitted explicitly; the iPhone never derives topic-feed paths.
33. **Today means the current calendar date in PaperFlow's configured publication timezone.** The timezone is published in `feed_index.json`; device travel cannot silently change feed-day identity. An older successful feed may be prefetched and shown as “Latest Available,” but it must never be relabeled as today.
34. **Personal state retains history across Unsave.** Unsave hides the paper from Saved but preserves reading state, notes, rating, timestamps, and its offline snapshot; resaving restores that state.
35. **V1 search is Saved-only.** Today and Topics have no Search or Settings affordances until concrete functionality is specified.

---

# 1. Product Goal

PaperFlow is a daily research-radar pipeline and iPhone feed that answers one question:

> **What new arXiv papers are worth my attention today, why are they relevant, and where do they fit in my research taxonomy?**

The system should be cheap, deterministic enough to audit, easy to reconfigure, and able to evolve without hard-coded topic or model logic.

The architecture prioritizes:

- correct inclusion/exclusion behavior;
- no silent paper loss;
- config-driven taxonomy and prompts;
- easy model switching;
- reproducibility;
- low API cost;
- simple static publication;
- a reliable iPhone browsing experience;
- figure extraction only after the rest works.

---

# 2. Non-Goals for V1

Do **not** implement these before the core pipeline is stable:

- author ranking;
- h-index filtering;
- citation-based ranking;
- personalized collaborative filtering;
- full-PDF LLM summarization;
- semantic search/vector database;
- paper recommendation based on reading history;
- social features;
- push notifications;
- third/fourth-level structural topic hierarchy;
- automatic LLM-created structural topics;
- figure understanding with a VLM;
- figure extraction before the final phase.

Optional free-form tags can be added later without changing structural taxonomy.

---

# 3. Final Architecture

## 3.1 Core pipeline — before figure extraction exists

```text
Configured schedule
        ↓
ArXiv NEW submissions
        ↓
normalize + base-arXiv-ID dedup
        ↓
merge retry-eligible FAILED backlog
        ↓
remove terminal already-screened IDs
        ↓
LLM filter: title + abstract + categories
        ↓
KEEP / DROP / FAILED
        ↓
     KEEP only
        ↓
summary LLM: title + abstract
        ↓
canonical selected-paper store
        ↓
render all static outputs
        ↓
root README (latest 80 only) / full daily + topic archives / full-history JSON / website
        ↓
iPhone refreshes day-indexed JSON
        ↓
figure area = local placeholder
```

## 3.2 Final architecture — after the last implementation phase

```text
                         ┌──────── summary LLM ──────────┐
KEEP paper ──────────────┤                               ├─→ canonical selected-paper record
                         └──── deferred figure worker ───┘

canonical data
   ↓
root README + full topic archives + daily archive + full-history JSON + website + iPhone
```

Figure extraction remains **non-blocking** forever: a failed or missing figure can never prevent publication.

---

# 4. Repository Layout

```text
paperflow/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── configs/
│   ├── runtime.yaml
│   ├── topics.yaml
│   ├── models.yaml
│   └── prompts/
│       ├── manifest.yaml
│       ├── taxonomy_block.j2
│       ├── filter_system.j2
│       ├── filter_user.j2
│       ├── summary_system.j2
│       └── summary_user.j2
│
├── src/paperflow/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── taxonomy.py
│   ├── taxonomy_migrations.py
│   ├── schedule.py
│   ├── arxiv_client.py
│   ├── normalize.py
│   ├── screening_ledger.py
│   ├── paper_store.py
│   ├── retry_queue.py
│   ├── llm/
│   │   ├── openrouter.py
│   │   ├── structured.py
│   │   ├── filtering.py
│   │   └── summarization.py
│   ├── render/
│   │   ├── markdown.py
│   │   ├── json_api.py
│   │   ├── website.py
│   │   └── validation.py
│   ├── cli/
│   │   ├── validate_taxonomy.py
│   │   ├── prompt_preview.py
│   │   ├── rebuild_outputs.py
│   │   ├── reclassify.py
│   │   ├── reprocess.py
│   │   └── sync_schedule.py
│   └── figures/                    # created only in final phase
│       ├── extract.py
│       ├── score.py
│       └── models.py
│
├── data/
│   ├── papers.json                 # full records for selected papers
│   ├── screening_events/           # all KEEP/DROP/FAILED attempts
│   │   └── YYYY-MM.jsonl
│   ├── feed_index.json             # full-history day index + counts
│   ├── daily_feeds/                 # all KEEP papers, partitioned by day
│   │   └── YYYY-MM-DD.json
│   ├── topics.json
│   ├── taxonomy_snapshot.json
│   ├── state.json
│   ├── run_stats/
│   │   └── YYYY-MM-DD.json
│   └── topic_feeds/
│       └── <large-topic>/
│           ├── all.json
│           └── <subtopic>.json
│
├── daily/
│   └── YYYY-MM-DD.md
│
├── topics/
│   └── <large-topic>/
│       ├── README.md
│       └── <subtopic>.md
│
├── site/
│   ├── index.html
│   ├── assets/
│   └── topics/
│       └── <large-topic>/
│           ├── index.html
│           └── <subtopic>.html
│
├── ios/
│   └── PaperFlow/
│       ├── App/
│       ├── Models/
│       ├── Networking/
│       ├── Storage/
│       └── Views/
│
├── cache/                          # gitignored
│   ├── llm_filter/
│   ├── llm_summary/
│   ├── raw/
│   └── pdf/                        # used only in final figure phase
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
└── .github/workflows/
    ├── ci.yml
    └── paperflow-daily.yml
```

---

# 5. Configuration Architecture

The implementation must separate four kinds of configuration.

```text
runtime.yaml   → when/how the pipeline runs
models.yaml    → which models and fallback order are used
topics.yaml    → what scientific interests exist
prompts/*      → how filtering and summaries are instructed
```

No topic list, model chain, run time, category list, or prompt text should be duplicated in application code.

## 5.1 `configs/runtime.yaml`

Recommended V1 schema:

```yaml
schema_version: 1

environment: production

timezone: America/New_York

schedule:
  enabled: true
  run_at_local: "21:00"
  run_days: [monday, tuesday, wednesday, thursday, friday, saturday, sunday]
  same_day_catchup: true

source:
  provider: arxiv
  mode: new_only
  categories:
    - cs.AI
    - cs.CV
    - cs.LG
    - cs.RO
    - cs.CL
  request_timeout_seconds: 30

filtering:
  batch_size: 10
  concurrency: 3
  semantic_retry_count: 1
  transient_retry_count: 3
  failed_auto_retry_max_attempts: 5
  failed_retry_cooldown_hours: 12

summaries:
  concurrency: 5
  semantic_retry_count: 1
  transient_retry_count: 3
  failed_auto_retry_max_attempts: 3

publishing:
  readme_latest_limit: 80            # applies ONLY to root README.md
  generate_daily_archive: true
  generate_feed_index: true
  generate_daily_json_feeds: true
  generate_topic_markdown: true
  generate_topic_json: true
  generate_website: true

figures:
  enabled: false
  iphone_placeholder: true

observability:
  persist_run_stats: true
  log_llm_usage: true
  log_model_used: true
  log_provider_used: true
```

### Important rule

There is intentionally **no** field such as:

```yaml
max_keep_per_day: 37
```

or any other default KEEP cap.

If an emergency candidate-processing safety cap is ever added, it must be explicitly named as an operational safety mechanism and must never silently convert unprocessed papers into DROP.

---

# 6. Model Configuration — OpenRouter

## 6.1 Verified production model IDs

As of 2026-08-20, use these OpenRouter IDs:

| Internal alias | Human name | OpenRouter model ID | Role |
|---|---|---|---|
| `deepseek_v4_flash` | DeepSeek V4 Flash 0731 | `deepseek/deepseek-v4-flash-0731` | default filter |
| `glm_4_7_flashx` | GLM 4.7 Flash | `z-ai/glm-4.7-flash` | fallback / alternative |
| `gpt_5_6_luna` | GPT-5.6 Luna | `openai/gpt-5.6-luna` | default summary |
| `mistral_small_4` | Mistral Small 4 | `mistralai/mistral-small-2603` | fallback / alternative |

`glm_4_7_flashx` is only an internal alias matching the requested name. Until OpenRouter exposes a distinct FlashX model slug, it must resolve to the verified `z-ai/glm-4.7-flash` model.

For DeepSeek, pin `deepseek/deepseek-v4-flash-0731` in production for reproducibility. A development profile may optionally use OpenRouter's family-latest alias, but a moving alias must never be used without recording the actual returned model ID.

## 6.2 `configs/models.yaml`

```yaml
schema_version: 1
provider: openrouter
base_url: https://openrouter.ai/api/v1

models:
  deepseek_v4_flash:
    model_id: deepseek/deepseek-v4-flash-0731
    temperature: 0.0
    max_output_tokens: 8000

  glm_4_7_flashx:
    model_id: z-ai/glm-4.7-flash
    temperature: 0.0
    max_output_tokens: 8000

  gpt_5_6_luna:
    model_id: openai/gpt-5.6-luna
    temperature: 0.0
    max_output_tokens: 8000

  mistral_small_4:
    model_id: mistralai/mistral-small-2603
    temperature: 0.0
    max_output_tokens: 8000

tasks:
  filter:
    primary: deepseek_v4_flash
    fallbacks:
      - glm_4_7_flashx
      - gpt_5_6_luna
      - mistral_small_4

  summary:
    primary: gpt_5_6_luna
    fallbacks:
      - deepseek_v4_flash
      - mistral_small_4
      - glm_4_7_flashx

routing:
  allow_provider_fallbacks: true
  provider_sort: default
  require_structured_outputs: true
```

## 6.3 Why this design

- The application integrates with **one API surface**.
- Model switching is a YAML edit, not a code edit.
- OpenRouter can perform provider-level and model-level failover.
- The app still performs its own semantic-output validation.
- Every response records the actual model returned by OpenRouter.
- A model can be replaced without touching filtering or summary business logic.

---

# 7. OpenRouter Client Contract

Create exactly one reusable client wrapper.

```python
class OpenRouterClient:
    def structured_chat(
        self,
        *,
        task_name: str,
        messages: list[dict],
        schema: type[BaseModel],
        model_chain: list[str],
        request_metadata: dict,
    ) -> LLMCallResult:
        ...
```

`LLMCallResult` must record:

```python
class LLMCallResult(BaseModel):
    parsed: BaseModel | None
    requested_model: str
    actual_model: str | None
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None
    cost_usd: float | None
    latency_ms: int
    request_id: str | None
    attempt: int
```

### Rules

1. Use JSON-schema structured output whenever the selected model supports it.
2. Do not parse arbitrary prose with regex as the normal path.
3. Enable OpenRouter usage reporting and persist actual usage/cost.
4. Never commit the API key.
5. Use `OPENROUTER_API_KEY` from GitHub Actions secrets or local environment.
6. Set optional `HTTP-Referer` and `X-Title` headers for PaperFlow.
7. Record actual returned model ID because a fallback may have been used.
8. Provider/network failures and semantic validation failures are separate error classes.

---

# 8. Retry Model

There are three different kinds of retries and they must not be conflated.

## 8.1 Provider-level failover

Handled by OpenRouter when an endpoint/provider for a model is unavailable.

## 8.2 Transient request retry

Retry on:

```text
429
500
502
503
504
network timeout
connection reset
temporary DNS/connectivity failure
```

Use bounded exponential backoff with jitter.

Recommended:

```text
attempt 1: immediate
attempt 2: ~2 s + jitter
attempt 3: ~5 s + jitter
```

Do not blindly retry deterministic authentication/configuration errors:

```text
400
401
403
unsupported parameter
invalid model ID
```

## 8.3 Semantic structured-output retry

A request can succeed at HTTP level but still be unusable because:

- response envelope is malformed;
- result list has missing/extra arXiv IDs;
- KEEP has no topic assignment;
- topic/subtopic ID is invalid;
- parent-child relation is invalid;
- duplicate IDs create ambiguity;
- score is outside schema bounds.

Policy:

```text
first semantic failure
    ↓
retry once using the next configured model
    ↓
still invalid
    ↓
filter_status = FAILED
```

This preserves the v3 rule that malformed structured output receives one semantic retry and then becomes retry-eligible rather than silently becoming DROP.

---

# 9. Taxonomy — Single Source of Truth

`configs/topics.yaml` is the only structural research-taxonomy source.

Changing taxonomy must be a config operation:

```text
edit topics.yaml
   ↓
validate
   ↓
compute taxonomy hash
   ↓
plan/apply migrations
   ↓
render current filter prompt
   ↓
rebuild topic Markdown
   ↓
rebuild topic JSON
   ↓
rebuild website routes
   ↓
iPhone receives new hierarchy on refresh
```

No Python or Swift source should contain a hard-coded list of research topics.

## 9.1 Exactly two structural levels

```text
Large Topic
  └── Subtopic
```

Additional granularity later should use non-structural tags.

## 9.2 Initial topic families from v2

Keep the v2 seed taxonomy unless intentionally edited in YAML:

```text
Embodied AI
  - Vision-Language Navigation
  - Vision-Language-Action
  - Robot Learning

World Models
  - Latent Action Models
  - World Action Models
  - Video World Models

Multimodal Foundation Models
  - Vision-Language Models
  - Multimodal Large Language Models

Spatial Intelligence
  - Spatial Reasoning
  - Spatial Memory
  - Geometry-Aware Models

3D Vision
  - Depth Estimation
  - 3D Reconstruction
  - 3D Foundation Models

Video Generation
  - Video Diffusion
  - Autoregressive Video Models
  - Video Prediction

Efficient AI
  - Token Pruning and Eviction
  - Efficient Attention
  - KV Cache and Memory Efficiency
```

The taxonomy can grow later without code changes.

---

# 10. Taxonomy Data Models

```python
class MovedFrom(BaseModel):
    topic_id: str


class SubtopicConfig(BaseModel):
    id: str
    name: str
    short_name: str | None = None
    description: str
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    previous_ids: list[str] = Field(default_factory=list)
    moved_from: MovedFrom | None = None


class TopicConfig(BaseModel):
    id: str
    name: str
    short_name: str | None = None
    description: str
    subtopics: list[SubtopicConfig] = Field(default_factory=list)
    previous_ids: list[str] = Field(default_factory=list)


class TaxonomyConfig(BaseModel):
    schema_version: int
    taxonomy_version: int
    topics: list[TopicConfig]
```

## 10.1 Validation rules

The taxonomy validator must enforce:

```text
large-topic active IDs unique
subtopic active IDs unique globally
IDs match ^[a-z0-9][a-z0-9-]*$
names non-empty
descriptions non-empty
previous_ids unique and non-colliding
active IDs cannot appear in another item's previous_ids
subtopic cannot exist under multiple active parents
moved_from old parent must be a valid historical/current parent reference
old parent must NOT still contain the moved subtopic
no migration cycle
no rename chain ambiguity
all existing selected-paper assignments remain active or migratable
```

---

# 11. Taxonomy Rename and Re-parenting Migrations

## 11.1 Display-name change

Changing only `name` is safe and requires no canonical rewrite.

## 11.2 ID rename

Use `previous_ids`.

```yaml
- id: geometric-memory
  name: Geometric Memory
  previous_ids:
    - spatial-memory
```

Historical assignments using `spatial-memory` are rewritten to `geometric-memory` before old generated paths are removed.

## 11.3 Subtopic re-parenting — v3 correctness fix

Example:

```yaml
- id: video-generation
  name: Video Generation
  subtopics:
    - id: video-world-models
      name: Video World Models
      moved_from:
        topic_id: world-models
```

Migration behavior:

```python
def resolve_moved_subtopics(taxonomy, selected_papers):
    moves = {
        (sub.moved_from.topic_id, sub.id): topic.id
        for topic in taxonomy.topics
        for sub in topic.subtopics
        if sub.moved_from is not None
    }

    for paper in selected_papers.values():
        for assignment in list(paper.topic_assignments):
            for subtopic_id in list(assignment.subtopic_ids):
                new_parent = moves.get((assignment.topic_id, subtopic_id))
                if not new_parent or new_parent == assignment.topic_id:
                    continue

                assignment.subtopic_ids.remove(subtopic_id)
                target = get_or_create_assignment(paper, new_parent)
                if subtopic_id not in target.subtopic_ids:
                    target.subtopic_ids.append(subtopic_id)

        remove_empty_duplicate_assignments(paper)
```

## 11.4 Combined rename + move

Support this intentionally:

```yaml
- id: video-generation
  subtopics:
    - id: video-world-models-v2
      previous_ids: [video-world-models]
      moved_from:
        topic_id: world-models
```

Migration planner resolves old identity first, then parent move, then validates the final assignment.

## 11.5 Mandatory migration order

```text
1. parse new taxonomy
2. validate active taxonomy shape
3. load previous taxonomy snapshot
4. load selected canonical papers
5. compute rename map
6. compute re-parenting map
7. print taxonomy diff/migration plan
8. rewrite historical assignments in memory
9. validate rewritten assignments against new taxonomy
10. render outputs
11. validate outputs
12. remove stale AUTO-GENERATED files only
13. save new taxonomy snapshot
```

Never delete stale generated files before migration validation succeeds.

---

# 12. Taxonomy Hashing and Prompt Reproducibility

Normalize YAML deterministically and calculate:

```python
taxonomy_hash = sha256(normalized_topics_yaml)
filter_prompt_hash = sha256(rendered_filter_system_prompt)
summary_prompt_hash = sha256(rendered_summary_system_prompt)
```

Store relevant hashes with LLM processing metadata.

A paper's filter cache namespace includes:

```text
arxiv_id
abstract_hash
taxonomy_hash
filter_prompt_hash
actual/requested model profile
```

A summary cache namespace includes:

```text
arxiv_id
abstract_hash
summary_prompt_hash
model profile
```

---

# 13. Prompt Architecture

## 13.1 Prompt files

```text
configs/prompts/
├── manifest.yaml
├── taxonomy_block.j2
├── filter_system.j2
├── filter_user.j2
├── summary_system.j2
└── summary_user.j2
```

## 13.2 Prompt manifest

```yaml
filter:
  version: filter-v3
  system: filter_system.j2
  user: filter_user.j2

summary:
  version: summary-v2
  system: summary_system.j2
  user: summary_user.j2
```

Changing prompt content should change its hash automatically; bumping the human-readable version is still required for audit clarity.

## 13.3 `taxonomy_block.j2`

```jinja2
{% for topic in topics %}
## LARGE TOPIC: {{ topic.name }}
ID: {{ topic.id }}
Description: {{ topic.description }}

{% for subtopic in topic.subtopics %}
### SUBTOPIC: {{ subtopic.name }}
ID: {{ subtopic.id }}
Description: {{ subtopic.description }}
{% if subtopic.include %}
Relevant examples:
{% for item in subtopic.include %}- {{ item }}
{% endfor %}
{% endif %}
{% if subtopic.exclude %}
Exclude examples:
{% for item in subtopic.exclude %}- {{ item }}
{% endfor %}
{% endif %}
{% endfor %}
{% endfor %}
```

## 13.4 Filter system prompt

The filter prompt must explicitly say:

```text
Use ONLY title, abstract, and arXiv categories.
Do not use author reputation, institution, citation count, or prestige.

KEEP if the paper directly fits at least one configured topic/subtopic OR
contains a technically meaningful idea plausibly transferable to the configured research interests.

DROP only when it is clearly outside all configured interests and lacks a meaningful transferable technical contribution.

For KEEP:
- relevance 1-10
- novelty 1-10
- at least one valid large-topic assignment
- zero or more valid child subtopics under each selected parent
- one short selection reason

For DROP:
- relevance 1-10
- novelty 1-10
- assignments must be []
- one short drop reason

Do not summarize the paper in this stage.
Do not invent claims.
Return structured output only.
```

## 13.5 Filter user prompt

Each paper block contains only:

```text
ARXIV_ID
TITLE
CATEGORIES
ABSTRACT
```

## 13.6 Summary prompt

```text
Generate a compact mobile research-paper summary using only title and abstract.

Return:
- one concise TL;DR sentence
- 3-5 concise bullets
- optional problem
- optional method
- optional contribution

Prefer, when supported by the abstract:
1. problem/motivation
2. core method
3. main contribution
4. main experimental result
5. limitation/scope

Do not invent numeric results, datasets, ablations, model sizes, training details,
or superiority claims absent from the abstract.
```

---

# 14. Filter Output Schema — v3 Correctness Fix

```python
class TopicAssignment(BaseModel):
    topic_id: str
    subtopic_ids: list[str] = Field(default_factory=list)


class FilterResult(BaseModel):
    arxiv_id: str
    keep: bool
    relevance: int = Field(ge=1, le=10)
    novelty: int = Field(ge=1, le=10)
    assignments: list[TopicAssignment]
    reason: str

    @model_validator(mode="after")
    def validate_decision(self):
        if self.keep and not self.assignments:
            raise ValueError(
                f"{self.arxiv_id}: keep=true requires at least one topic assignment"
            )
        if not self.keep and self.assignments:
            raise ValueError(
                f"{self.arxiv_id}: keep=false requires assignments=[]"
            )
        return self


class FilterBatchResponse(BaseModel):
    results: list[FilterResult]
```

This closes the v2 gap where a KEEP result could incorrectly contain `assignments: []`.

---

# 15. Semantic Filter Validation

Pydantic validation is necessary but not sufficient.

For each result:

```python
for assignment in result.assignments:
    if not taxonomy.has_topic(assignment.topic_id):
        raise UnknownTopicError(...)

    if len(assignment.subtopic_ids) != len(set(assignment.subtopic_ids)):
        raise DuplicateSubtopicError(...)

    for subtopic_id in assignment.subtopic_ids:
        if not taxonomy.is_child(assignment.topic_id, subtopic_id):
            raise InvalidParentChildError(...)
```

Also enforce:

```text
result arxiv IDs exactly match requested paper IDs
no duplicate result IDs
no missing result IDs
no extra result IDs
assignment topic IDs unique per paper
```

### Partial-batch salvage

Do not throw away an entire valid batch because one paper has a bad assignment.

Procedure:

```text
parse batch envelope
   ↓
validate result ID set
   ↓
validate each result independently
   ↓
accept valid results
   ↓
retry only invalid subset once using next model
   ↓
remaining invalid subset → FAILED
```

If the response envelope itself cannot be mapped safely to requested IDs, retry the full batch once.

---

# 16. Screening State — Correct Retry Semantics

## 16.1 Filter status

```python
class FilterStatus(str, Enum):
    KEPT = "kept"
    DROPPED = "dropped"
    FAILED = "failed"
```

Only FAILED is retry-eligible automatically.

DROPPED is terminal unless the user explicitly runs historical reclassification.

## 16.2 Important storage refinement

Do **not** make an ever-growing `papers.json` hold hundreds of full DROP records per day.

Use two canonical layers:

```text
data/screening_events/YYYY-MM.jsonl
    → durable outcome/attempt ledger for EVERY candidate

data/papers.json
    → full canonical records for selected/KEEP papers only
```

This preserves the v3 requirement that every candidate has a durable KEEP/DROP/FAILED record while keeping the public selected-paper store reasonably small.

## 16.3 Screening event schema

```python
class ScreeningEvent(BaseModel):
    event_id: str
    run_id: str
    arxiv_id: str
    observed_at: datetime
    abstract_hash: str
    filter_status: FilterStatus
    attempt_number: int

    relevance: int | None = None
    novelty: int | None = None
    topic_assignments: list[TopicAssignment] = Field(default_factory=list)
    reason: str | None = None

    taxonomy_version: int
    taxonomy_hash: str
    filter_prompt_version: str
    filter_prompt_hash: str

    requested_model: str | None = None
    actual_model: str | None = None
    provider: str | None = None

    error_type: str | None = None
    error_message: str | None = None
    next_retry_at: datetime | None = None
    retry_exhausted: bool = False
```

The ledger is append-only. A failed paper that later succeeds receives a new event; old history remains auditable.

## 16.4 Materialized latest screening state

At startup:

```python
def load_latest_screening_state() -> dict[str, ScreeningEvent]:
    latest = {}
    for event in iter_screening_events():
        current = latest.get(event.arxiv_id)
        if current is None or event.observed_at > current.observed_at:
            latest[event.arxiv_id] = event
    return latest
```

For V1 volume, this is simple and sufficient. If the ledger becomes very large later, add an index without changing semantics.

---

# 17. Retry-safe Candidate Detection — v3 Correctness Fix, Hardened

The literal v3 fix based only on papers reappearing in tomorrow's RSS feed is not enough. A NEW-submission entry may never appear again.

The daily workset must combine:

```text
A. today's unseen arXiv candidates
B. retry-eligible FAILED records from prior runs
```

Pseudo-code:

```python
def determine_workset(today_candidates, latest_screening_state, now, retry_cfg):
    work: dict[str, CandidatePaper] = {}

    # A. New feed items
    for paper in today_candidates:
        state = latest_screening_state.get(paper.arxiv_id)

        if state is None:
            work[paper.arxiv_id] = paper
            continue

        if state.filter_status == FilterStatus.FAILED and is_retry_eligible(
            state, now, retry_cfg
        ):
            work[paper.arxiv_id] = paper

        # KEPT / DROPPED are terminal for normal daily processing.

    # B. Failed backlog, even if not in today's feed
    for arxiv_id, state in latest_screening_state.items():
        if state.filter_status != FilterStatus.FAILED:
            continue
        if not is_retry_eligible(state, now, retry_cfg):
            continue
        if arxiv_id in work:
            continue

        paper = refetch_arxiv_metadata(arxiv_id)
        if paper is not None:
            work[arxiv_id] = paper

    return list(work.values())
```

## 17.1 Auto-retry exhaustion

Recommended:

```text
max automatic filter attempts = 5
```

After exhaustion:

```text
filter_status remains FAILED
retry_exhausted = true
automatic daily pipeline no longer retries it
manual reprocess remains available
```

Never convert an exhausted failure to DROP.

---

# 18. arXiv Ingestion

## 18.1 Input categories

Read categories only from `runtime.yaml`.

## 18.2 Normalize IDs

```text
2608.12345v1 → 2608.12345
```

Use the versionless ID as the canonical identity.

Keep `source_arxiv_id` separately for source provenance.

## 18.3 Deduplicate across categories

If one paper appears in `cs.CV` and `cs.RO`:

```text
one candidate record
categories = union of observed categories
```

## 18.4 NEW-only policy

Normal daily processing should target new submissions rather than replacement versions.

If a later arXiv revision changes the abstract, do not silently reclassify the paper during the normal daily flow. Reprocessing/reclassification is an explicit maintenance operation.

## 18.5 Ingestion failure

If arXiv fetch fails completely:

```text
abort publication run
write run failure stats/log
commit nothing
```

Do not publish an apparently valid "0 papers today" feed when the source itself failed.

---

# 19. Selected-Paper Canonical Store

`data/papers.json` stores full records for KEEP papers.

Recommended keyed shape:

```json
{
  "schema_version": 1,
  "papers": {
    "2608.12345": {
      "arxiv_id": "2608.12345",
      "source_arxiv_id": "2608.12345v1",
      "title": "Geometry-Aware Navigation with Persistent Spatial Memory",
      "abstract": "...",
      "authors": ["A", "B"],
      "categories": ["cs.RO", "cs.CV"],
      "first_seen_at": "2026-08-20T21:03:00-04:00",
      "first_seen_date": "2026-08-20",
      "filter_status": "kept",
      "relevance": 10,
      "novelty": 7,
      "topic_assignments": [
        {
          "topic_id": "embodied-ai",
          "subtopic_ids": ["vision-language-navigation"]
        },
        {
          "topic_id": "spatial-intelligence",
          "subtopic_ids": ["spatial-memory", "geometry-aware-models"]
        }
      ],
      "selection_reason": "Uses persistent geometry-aware memory for instruction-guided navigation.",
      "summary_status": "generated",
      "tldr": "...",
      "bullets": ["...", "...", "..."],
      "problem": null,
      "method": null,
      "contribution": null,
      "hero_figure": null,
      "figure_status": "not_implemented",
      "taxonomy_version": 4,
      "taxonomy_hash": "...",
      "filter_prompt_version": "filter-v3",
      "filter_prompt_hash": "...",
      "summary_prompt_version": "summary-v2",
      "summary_prompt_hash": "...",
      "filter_model": "deepseek/deepseek-v4-flash-0731",
      "summary_model": "openai/gpt-5.6-luna"
    }
  }
}
```

### Invariant

Every paper in `papers.json` must satisfy:

```text
filter_status == kept
at least one valid topic assignment
```

---

# 20. Summary State and Failure Handling

```python
class SummaryStatus(str, Enum):
    PENDING = "pending"
    GENERATED = "generated"
    FAILED = "failed"
```

`SummaryResult`:

```python
class SummaryResult(BaseModel):
    arxiv_id: str
    tldr: str
    bullets: list[str] = Field(min_length=3, max_length=5)
    problem: str | None = None
    method: str | None = None
    contribution: str | None = None
```

If summary generation fails:

```text
paper stays KEEP
summary_status = failed
tldr = null
bullets = []
public UI falls back to original abstract
```

The summary worker should retry failed summaries on later runs, independently of filter status.

A summary failure must never cause a paper to disappear.

---

# 21. LLM Caching

Use disk caches locally/GitHub cache for request reuse, but canonical correctness must not depend on cache availability.

Example paths:

```text
cache/llm_filter/<arxiv_id>__<abstract_hash>__<taxonomy_hash>__<prompt_hash>__<model>.json
cache/llm_summary/<arxiv_id>__<abstract_hash>__<prompt_hash>__<model>.json
```

Cache hit acceptance requires all key components to match exactly.

Do not use stale filter cache after a semantically changed taxonomy or filter prompt.

---

# 22. Daily Pipeline — Final Pseudocode

```python
def run_daily(*, manual: bool = False):
    run = start_run_context()

    runtime = load_runtime_config()
    model_config = load_model_config()
    taxonomy = load_taxonomy()
    prompt_manifest = load_prompt_manifest()

    validate_runtime_config(runtime)
    validate_model_config(model_config)
    validate_taxonomy_shape(taxonomy)

    previous_taxonomy = load_taxonomy_snapshot()
    selected_store = load_selected_paper_store()

    migration_plan = plan_taxonomy_migrations(
        previous_taxonomy,
        taxonomy,
        selected_store,
    )
    log_taxonomy_diff(migration_plan)
    apply_taxonomy_migrations_in_memory(selected_store, migration_plan)
    validate_selected_assignments(selected_store, taxonomy)

    prompts = render_all_prompts(taxonomy, prompt_manifest)

    if not manual:
        assert_schedule_due(runtime, load_state())

    raw = fetch_configured_arxiv_new(runtime.source)
    candidates = deduplicate(normalize(raw))
    save_raw_snapshot_to_cache(run, candidates)

    screening_state = load_latest_screening_state()

    workset = determine_workset(
        today_candidates=candidates,
        latest_screening_state=screening_state,
        now=run.started_at,
        retry_cfg=runtime.filtering,
    )

    filter_outcomes = filter_workset(
        workset,
        taxonomy=taxonomy,
        prompts=prompts,
        model_config=model_config,
        runtime=runtime,
    )

    append_screening_events(filter_outcomes.events)

    newly_kept = []
    for outcome in filter_outcomes.valid_kept:
        paper = build_or_update_selected_record(outcome)
        selected_store[paper.arxiv_id] = paper
        newly_kept.append(paper)

    summary_targets = collect_summary_targets(
        selected_store,
        newly_kept,
        runtime.summaries,
    )

    summary_results = summarize_selected(
        summary_targets,
        prompts=prompts,
        model_config=model_config,
        runtime=runtime,
    )

    apply_summary_results(selected_store, summary_results)

    # FIGURE EXTRACTION IS INTENTIONALLY NOT CALLED HERE IN CORE V1.
    ensure_default_figure_state(selected_store)

    build_root_readme(
        taxonomy,
        selected_store,
        latest_limit=runtime.publishing.readme_latest_limit,  # README ONLY
    )
    generate_topic_tree(taxonomy, selected_store)             # full history
    build_daily_archive(taxonomy, selected_store, run.local_date)

    # Public app/web feed is COMPLETE history, partitioned by day.
    build_feed_index(taxonomy, selected_store)
    build_daily_json_feeds(taxonomy, selected_store)
    build_topics_json(taxonomy, selected_store)
    build_topic_json_feeds(taxonomy, selected_store)          # full topic history
    build_static_site(taxonomy, selected_store)               # full history

    stale_plan = plan_stale_generated_topic_cleanup(taxonomy)
    validate_generated_artifacts(
        taxonomy,
        selected_store,
        runtime,
        planned_stale_paths=stale_plan,
    )
    cleanup_stale_generated_topic_files_safely(stale_plan)
    validate_generated_artifacts(taxonomy, selected_store, runtime)

    save_selected_paper_store(selected_store)
    save_taxonomy_snapshot(taxonomy)
    save_run_stats(run, filter_outcomes, summary_results)
    mark_run_success(run)
```

Once figures are implemented, add a **non-blocking** figure worker after summary targeting, but publication must still continue with `hero_figure = null` on failure.

---

# 23. Markdown Rendering

Use one table schema and one row renderer everywhere.

```python
PAPER_TABLE_HEADER = """\
| Date | Paper | Topics | TL;DR | Rel. | Nov. |
|---|---|---|---|---:|---:|
"""
```

Used by:

```text
root README latest 80
large-topic full history
subtopic full history
daily archive
```

Single renderer:

```python
def render_paper_row(paper, taxonomy):
    date = paper.first_seen_date
    title = md_escape(paper.title)
    labels = ", ".join(display_topic_labels(paper, taxonomy))
    tldr = md_escape(paper.tldr or compact_abstract_fallback(paper.abstract))

    return (
        f"| {date} "
        f"| [{title}]({paper.arxiv_url}) "
        f"| {labels} "
        f"| {tldr} "
        f"| {paper.relevance} "
        f"| {paper.novelty} |"
    )
```

Sorting everywhere:

```text
first_seen_at DESC
arxiv_id DESC
```

Topic label ordering follows YAML config order, not LLM output order.

---

# 24. Generated Topic Tree

```text
topics/
├── embodied-ai/
│   ├── README.md
│   ├── vision-language-navigation.md
│   ├── vision-language-action.md
│   └── robot-learning.md
├── world-models/
│   ├── README.md
│   ├── latent-action-models.md
│   ├── world-action-models.md
│   └── video-world-models.md
└── ...
```

Every generated file begins with:

```markdown
<!--
AUTO-GENERATED BY PAPERFLOW.
DO NOT EDIT MANUALLY.
SOURCE: configs/topics.yaml + data/papers.json
-->
```

Only files containing this marker are eligible for stale-file deletion.

Empty configured topics/subtopics must still be generated with a zero-paper state.

---

# 25. Root README — the ONLY 80-paper-limited View

The root GitHub `README.md` contains:

```text
1. generated topic navigation
2. latest 80 selected papers globally
```

The `80` limit exists only to keep the repository landing page readable.

**Hard rule:**

```text
README.md latest table      → latest 80 KEEP papers
iPhone app                  → ALL KEEP papers
website                     → ALL KEEP papers
large-topic README          → ALL matching KEEP papers
subtopic README             → ALL matching KEEP papers
daily archive               → ALL KEEP papers for that day
public JSON feeds           → ALL KEEP papers, day-partitioned
```

No code outside the root README renderer may read or depend on `publishing.readme_latest_limit`.

The README limit must never influence filtering, summaries, canonical storage, daily archives, topic history, website membership, iPhone membership, or public JSON membership.

---

# 26. Daily Archives

Generate:

```text
daily/YYYY-MM-DD.md
```

A daily archive contains all selected papers whose `first_seen_date` equals that date.

At the top of every successful daily archive, render the exact KEEP count:

```markdown
# PaperFlow — 2026-08-20

**Papers kept: 42**
```

There is no daily paper-count cap.

If no papers were selected on a successful source fetch:

```text
# PaperFlow — YYYY-MM-DD

_No papers matched the configured research interests today._
```

If source ingestion failed, do not generate this successful-empty state.

---

# 27. Static JSON API — Full KEEP History

The public API must expose every KEEP paper. Do **not** use the root README's `80` limit here.

To avoid making the iPhone download one ever-growing JSON file on every launch, partition the global feed by day.

## 27.1 `data/feed_index.json`

This is the lightweight entry point for the iPhone and website.

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-20T21:05:00-04:00",
  "timezone": "America/New_York",
  "total_paper_count": 1842,
  "day_count": 97,
  "days": [
    {
      "date": "2026-08-20",
      "paper_count": 42,
      "feed_url": "data/daily_feeds/2026-08-20.json"
    },
    {
      "date": "2026-08-19",
      "paper_count": 35,
      "feed_url": "data/daily_feeds/2026-08-19.json"
    }
  ]
}
```

Rules:

```text
days sorted newest → oldest
timezone = valid IANA timezone copied from runtime.yaml
paper_count = exact number of KEEP papers first_seen on that date
total_paper_count = total KEEP papers in canonical selected store
no 80-paper truncation
zero-paper successful days may be included with paper_count=0
failed source days must not masquerade as successful zero-paper days
```

## 27.2 `data/daily_feeds/YYYY-MM-DD.json`

Each file contains **all** KEEP papers for that date.

```json
{
  "schema_version": 1,
  "date": "2026-08-20",
  "paper_count": 42,
  "papers": []
}
```

The `papers` array is never truncated.

Each public paper includes:

```text
arxiv_id
title
authors
abstract
arxiv_url
pdf_url
first_seen_at
categories
relevance
novelty
topic_assignments
selection_reason
tldr
bullets
summary_status
hero_figure
figure_status
```

Do not expose raw LLM request payloads, secrets, retry internals, or private provenance fields.

## 27.3 `data/topics.json`

Mirrors `topics.yaml` hierarchy exactly and adds full-history counts.

Required V1 shape:

```json
{
  "schema_version": 1,
  "taxonomy_version": 4,
  "total_paper_count": 1842,
  "topics": [
    {
      "id": "world-models",
      "name": "World Models",
      "paper_count": 438,
      "feed_url": "data/topic_feeds/world-models/all.json",
      "subtopics": [
        {
          "id": "video-world-models",
          "name": "Video World Models",
          "paper_count": 196,
          "feed_url": "data/topic_feeds/world-models/video-world-models.json"
        }
      ]
    }
  ]
}
```

`total_paper_count` is the number of unique canonical KEEP papers in the full selected store. It is not the sum of large-topic counts because one paper may belong to multiple topics. Topic and subtopic counts are full-view membership counts and may overlap. Counts are never computed from the README latest-80 slice.

## 27.4 Per-topic feeds — full history + daily counts

```text
data/topic_feeds/<large-topic>/all.json
data/topic_feeds/<large-topic>/<subtopic>.json
```

Each feed contains the **full historical membership** for that large topic/subtopic and groups papers by day.

Required V1 shape:

```json
{
  "schema_version": 1,
  "topic_id": "world-models",
  "subtopic_id": "video-world-models",
  "total_paper_count": 196,
  "days": [
    {
      "date": "2026-08-20",
      "paper_count": 5,
      "papers": []
    },
    {
      "date": "2026-08-19",
      "paper_count": 3,
      "papers": []
    }
  ]
}
```

For `all.json`, `topic_id` is required and `subtopic_id` is `null`. For a subtopic feed, both IDs are required and the subtopic must be an active child of `topic_id`.

A specific subtopic feed/README must contain **every KEEP paper ever assigned to that subtopic**.

Every `papers` element in a topic/subtopic day group uses the exact public paper contract from Section 27.2, including `abstract`.

For a paper assigned to multiple topics/subtopics, it appears in every applicable full-history feed.

## 27.5 Public URL contract

The configured public `base_url` is an absolute directory URL ending in `/` and represents the publication root. Every generated relative URL is resolved against that root, never against the JSON file that contains it.

Examples:

```text
base_url                                 https://example.com/paperflow/
feed index                               data/feed_index.json
day feed_url                             data/daily_feeds/2026-08-20.json
large-topic feed_url                     data/topic_feeds/world-models/all.json
subtopic feed_url                        data/topic_feeds/world-models/video-world-models.json
hero_figure                              figures/2608.12345/hero.webp
```

Rules:

```text
feed_index.json supplies every daily feed_url
topics.json supplies every large-topic and subtopic feed_url
the iPhone does not derive a feed path from a topic ID
relative paths never start with / and contain no .., backslash, query, or fragment
generated path segments use validated taxonomy IDs or canonical arXiv IDs
non-ID path segments are RFC 3986 percent-encoded
arxiv_url and pdf_url remain absolute HTTPS URLs
hero_figure is null or a publication-root-relative URL
```

HTTP `ETag` and `Last-Modified` may reduce downloads but are not correctness inputs. The client validates schema and counts before atomically replacing its last valid cache even when HTTP cache headers are present.

---

# 28. Website — Full KEEP History Grouped by Day

Generate static routes mirroring taxonomy:

```text
site/index.html
site/days/YYYY-MM-DD.html
site/topics/<large-topic>/index.html
site/topics/<large-topic>/<subtopic>.html
```

No hard-coded topic navigation.

## 28.1 Root website feed

The website root is **not** limited to 80 papers.

It must make the entire KEEP history browsable, preferably using day sections and progressive/lazy loading so the initial page does not become enormous.

Required day header:

```text
August 20, 2026 · 42 papers
```

Then render all 42 papers for that day.

Example:

```text
August 20, 2026 · 42 papers
────────────────────────────
[paper card]
[paper card]
...

August 19, 2026 · 35 papers
────────────────────────────
[paper card]
...
```

Older days remain reachable indefinitely through the day index / "Load older days" / pagination-by-day mechanism.

## 28.2 Topic and subtopic website pages

Large-topic and subtopic pages also expose their **full matching history**, grouped by day with a per-day count:

```text
Video World Models
196 papers total

August 20, 2026 · 5 papers
August 19, 2026 · 3 papers
August 18, 2026 · 7 papers
...
```

The displayed per-day count is the count **within the current view**:

```text
root website day count      = all KEEP papers on that day
large-topic day count       = KEEP papers in that large topic on that day
subtopic day count          = KEEP papers in that subtopic on that day
```

Website components must consume the same normalized view models/count helpers used by JSON generation so Markdown, website, and iPhone cannot disagree on membership or counts.

---

# 29. iPhone Application — Functional Specification

This section defines **application behavior only**. It intentionally does not prescribe visual styling, colors, card appearance, spacing, animation style, or other presentation details.

The iPhone app has two data domains:

```text
PUBLIC PAPERFLOW DATA
feed_index.json / daily feeds / topics / topic feeds
    → read-only scientific/feed data

PERSONAL APP DATA
seen / saved / reading status / notes / rating / timestamps
    → private mutable user state
```

The two domains must remain independent.

## 29.1 Public data contract

The app resolves these publication-root-relative paths against one configured `base_url`:

```text
data/feed_index.json
data/daily_feeds/YYYY-MM-DD.json
data/topics.json
data/topic_feeds/.../*.json
```

The app must never use the root README's `80` limit.

The base URL must be configured through an `.xcconfig`/Info.plist build setting, end in `/`, and not be scattered through Swift files. Daily and topic feed locations come from the `feed_url` values in `feed_index.json` and `topics.json`; Swift must not construct topic-feed paths from IDs. URL resolution follows Section 27.5.

The public paper feed remains read-only from the iPhone's perspective. Save, Skip, Seen, reading progress, notes, and ratings must not modify:

```text
data/papers.json
screening_events
daily feed JSON
topic feed JSON
filter_status
taxonomy assignments
```

## 29.2 Primary navigation and app-level behavior

The primary product tabs are:

```text
Today
Topics
Saved
```

`Paper Detail` is reachable from any paper shown in Today, Topics, Swipe, Browse, or Saved.

The app should preserve independent navigation state for each primary tab when practical so switching tabs does not unnecessarily reset the user's place.

Global pull-to-refresh may refresh public PaperFlow data, but it must never clear personal interaction state.

V1 has no Search or Settings affordance in the Today or Topics root headers. Search is local to Saved as defined in Section 29.15. A future Settings surface requires a separately specified function and must not be represented by a dead button.

## 29.3 Today tab

The Today tab is the entry point for day-based discovery.

It must:

```text
fetch feed_index.json
show every successful historical day
show the exact paper_count supplied for each day
prefetch the newest successful day automatically
lazy-load older days as needed
allow opening any day
preserve access to papers older than the newest 80
```

The Today title and hero card refer to the current calendar date in the IANA `timezone` published by `feed_index.json`. Device timezone changes do not alter which feed date is called Today. Display formatting may still follow the user's locale.

```text
current date exists in feed_index
→ render that day's exact payload, including a valid zero-paper day

current date absent, older successful day exists
→ show “Today's feed isn't available yet”
→ show the newest successful day separately as “Latest Available”
→ prefetch that older day, but never relabel it as today

current date absent and cached data is being used
→ use the same unavailable state plus Offline/Last Updated context

no successful or cached day exists
→ show the contextual no-data/error state with Retry
```

The app does not guess whether an absent current day is pending, delayed, or a source failure. Only a present zero-count day is presented as “No papers matched today.”

Opening a day provides two functional paths:

```text
Browse
Swipe
```

A day remains a complete PaperFlow collection regardless of personal actions. A skipped or saved paper is still part of that day's public feed.

The app may show personal review progress for a day:

```text
reviewed_count
remaining_unreviewed_count
total paper_count
```

These progress values are computed locally from personal interaction state and must not replace or alter the server-provided `paper_count`.

## 29.4 Day Browse mode

Browse mode exposes every paper in the selected day.

Functions:

```text
open Paper Detail
save / unsave a paper
show whether a paper is already saved
show whether a paper has already been reviewed
return to the same browse position after viewing details
```

Browse mode must not automatically mark a paper as reviewed merely because its row/card becomes visible.

Explicit Save marks the paper as saved and reviewed.

Browse sorting/filtering follows the UI/UX specification and is computed locally over the loaded public collection. Topic/subtopic filters are derived from published taxonomy/assignments; no filter list is hard-coded. Applying or resetting a filter never mutates seen/saved state.

Opening Paper Detail by itself does not finalize swipe triage; the paper remains unreviewed until the user explicitly Save/Skip actions it, unless another explicit "mark reviewed" function is later added.

## 29.5 Topics tab

The Topics tab is entirely data-driven from `topics.json`.

It must:

```text
list every active Large Topic
show its full-history paper count
open a Large Topic
list its active Subtopics
show each subtopic's full-history paper count
open Large Topic history
open Subtopic history
```

The app must never hard-code topic or subtopic IDs/names in Swift enums.

Taxonomy updates follow:

```text
edit topics.yaml
→ publish topics.json
→ iPhone refresh
→ updated hierarchy becomes available
```

No TestFlight/App Store build is required merely to add, rename, or re-parent a configured topic/subtopic.

## 29.6 Topic and Subtopic history

Large Topic and Subtopic views expose their complete matching PaperFlow history.

They must:

```text
preserve every matching KEEP paper
group or retrieve history by the server-provided day structure
show exact per-view day counts
allow loading older history
allow Browse mode
allow Swipe mode
open Paper Detail
allow Save / Unsave
```

No topic/subtopic view may truncate membership to the global newest 80.

A paper assigned to multiple topics/subtopics remains one canonical paper for personal-state purposes.

## 29.7 Swipe triage

Swipe triage is available for:

```text
a selected day
a selected Large Topic
a selected Subtopic
```

The default swipe deck contains papers that are **not yet globally reviewed** by the user.

An explicit review-again/all-papers mode may include previously reviewed papers without deleting their existing Saved or reading state.

### Swipe actions

```text
Swipe Left  = Skip / reviewed, not saved
Swipe Right = Save / reviewed / add to Deep Read Queue
```

Equivalent explicit action buttons may call the same commands. Gesture and button behavior must be identical.

### Swipe Left semantics

Swipe Left must:

```text
mark the paper as seen/reviewed
record the review timestamp
leave saved=false unless it was already saved
advance to the next eligible paper
```

Swipe Left must **never**:

```text
change filter_status to DROPPED
remove the paper from PaperFlow history
modify public JSON
delete an existing Saved paper silently
```

If a paper is already saved and is later encountered in review-again mode, a left swipe must not silently unsave it. Unsave is an explicit action.

### Swipe Right semantics

Swipe Right must:

```text
mark the paper as seen/reviewed
save the paper
record saved_at if this is the first save
record last_saved_at when saved changes false → true
clear unsaved_at when saved changes false → true
set reading_status = queue unless an existing later state must be preserved
store/update the local saved-paper snapshot
advance to the next eligible paper
```

If the paper is already saved, Swipe Right is idempotent and must not create a duplicate record or reset `reading`/`done` back to `queue`.

### Paper Detail during swipe

The current paper can be opened in Paper Detail without finalizing the swipe decision.

Returning from Paper Detail must return to the same swipe session and current paper unless the user explicitly Save/Skip actions the paper from the detail screen.

### Swipe progress and resume

Public topic/subtopic filters first define the active collection. Personal review mode (`Unreviewed` by default or explicit `All Papers / Review Again`) then defines which cards are eligible without changing public membership.

Each active swipe collection should expose:

```text
total collection papers
reviewed in that collection
remaining unreviewed
current session position
```

Visible progress copy is consistent in every day/topic/subtopic deck:

```text
<reviewed_count> of <total_paper_count> reviewed
<remaining_unreviewed_count> remaining
```

Do not label `<remaining_unreviewed_count> / <total_paper_count>` as reviewed, and do not label the total collection count as unread. Session position may be exposed separately for accessibility/debugging but does not replace persisted collection progress.

`total_paper_count` for Swipe progress is the active public membership after topic/subtopic filters and before personal review-mode filtering. `reviewed_count` is seen membership inside that same set, and remaining is the difference. Changing filters recomputes these values but performs no personal mutation.

If the app closes mid-session:

```text
reopen collection
→ rebuild eligibility from persisted personal state
→ continue with remaining unreviewed papers
```

The implementation must not depend only on an in-memory card index.

### Undo

The user can undo the most recent finalized swipe action in the active session.

Undo must restore both:

```text
the paper's prior personal state
the paper's position in the active swipe session
```

Examples:

```text
undo Skip
→ restore previous seen/review state

undo first-time Save
→ remove that Save and restore prior seen/review state

undo Save on an already-saved paper
→ restore the exact prior saved/reading state rather than deleting it
```

Undo should be transactional from the user's perspective.

### Completion

When no eligible unreviewed papers remain, the collection is considered triaged for the current personal state.

The user can still:

```text
Browse all papers
review Saved papers
enter explicit review-again/all-papers mode
```

Completion never changes the public feed.

## 29.8 Global personal interaction semantics

Personal state is keyed by the canonical versionless arXiv ID:

```text
2608.12345v1 → 2608.12345
2608.12345v2 → 2608.12345
```

Therefore one paper has one personal state even if it appears in:

```text
Today
a Large Topic
multiple Subtopics
older historical views
```

Required personal interaction fields:

```text
arxiv_id
seen
last_seen_at
saved
saved_at                    # first-ever save; retained across Unsave
last_saved_at               # most recent false → true transition
unsaved_at                  # most recent true → false transition, else null
reading_status
reading_status_changed_at
reading_started_at
completed_at
last_opened_at
note
rating
```

Null/default rules:

```text
seen=false and last_seen_at=null until explicit Save/Skip
saved=false initially
saved_at=null and last_saved_at=null until first Save
unsaved_at=null unless the most recent Save membership transition was Unsave
reading_status=null until first Save, then queue/reading/done
reading_status_changed_at=null until a reading status exists
reading_started_at=null until entering Reading
completed_at is non-null only while reading_status=done
last_opened_at=null until a currently saved paper is opened as defined below
note defaults to an empty string
rating defaults to null and otherwise is an integer from 1 through 5
```

Allowed non-null reading states:

```text
queue
reading
done
```

`rating` is optional and may be null until the user assigns a personal rating.

Personal-state transition rules:

```text
every explicit Save action
→ seen=true
→ last_seen_at=now

first Save
→ saved=true
→ saved_at=now
→ last_saved_at=now
→ unsaved_at=null
→ reading_status=queue
→ reading_status_changed_at=now

Save while already saved
→ saved membership is idempotent
→ do not change saved_at, last_saved_at, or reading status

Unsave
→ saved=false
→ unsaved_at=now
→ preserve seen, saved_at, last_saved_at, reading status and its timestamps,
  last_opened_at, note, rating, and saved snapshot

Save after Unsave
→ saved=true
→ last_saved_at=now
→ unsaved_at=null
→ preserve saved_at, reading status/timestamps, last_opened_at, note, rating,
  and saved snapshot
→ if a legacy record has no reading_status, initialize queue

enter Reading
→ reading_status=reading
→ reading_status_changed_at=now
→ reading_started_at=now
→ completed_at=null

enter Done
→ reading_status=done
→ reading_status_changed_at=now
→ completed_at=now

leave Done for Queue or Reading
→ update reading_status and reading_status_changed_at
→ completed_at=null
→ entering Reading also refreshes reading_started_at
```

`last_opened_at` updates, at most once per presentation, when a currently saved paper's Paper Detail becomes visible or the user invokes Open arXiv/Open PDF. Merely rendering a row/card never updates it.

Undo restores the exact prior record, including all timestamps and snapshot state.

The personal state machine is independent from PaperFlow screening:

```text
AI state:
KEPT / DROPPED / FAILED

Human state:
unreviewed / reviewed
unsaved / saved
queue / reading / done
```

No human action may rewrite AI screening history.

## 29.9 Saved tab — Deep Read Queue

Saved is the user's private long-term paper library and deep-read queue.

It must contain every currently saved paper, independent of the day/topic feed currently cached.

Core functions:

```text
view all saved papers
filter by queue / reading / done
change reading status
open Paper Detail
open PDF
open arXiv page
add/edit personal notes
add/edit/remove personal rating
unsave/remove from Saved
search saved papers locally
sort saved papers
```

Required default Queue sort:

```text
last_saved_at DESC
```

Required Queue sort options:

```text
recently saved (last_saved_at DESC)
oldest saved
relevance
novelty
title
```

Required Reading sort options:

```text
last opened (default): last_opened_at DESC
  null fallback: reading_status_changed_at DESC, then last_saved_at DESC
recently saved: last_saved_at DESC
title
```

Required Done sort options:

```text
recently completed (default): completed_at DESC
oldest completed: completed_at ASC
title
```

Removing a paper from Saved must not remove it from PaperFlow's public history or erase the fact that it was previously reviewed. Unsave follows the retention rules in Section 29.8. Resetting or permanently deleting personal history is not a V1 function.

## 29.10 Saved-paper snapshot behavior

Because old daily/topic feeds are loaded lazily and may not be present offline, each Saved record should retain enough paper metadata to remain usable independently.

Required saved snapshot:

```text
arxiv_id
title
authors
arxiv_url
pdf_url
tldr or abstract fallback
topic/subtopic labels or IDs needed for display
relevance
novelty
hero_figure reference if available
```

Personal fields, including save/status timestamps, remain separate from refreshable public metadata.

When fresher valid PaperFlow metadata for the same canonical ID becomes available, the app updates refreshable snapshot fields while preserving:

```text
saved_at
last_saved_at
unsaved_at
reading_status
reading status timestamps
last_opened_at
notes
rating
personal review timestamps
```

Unsave retains the snapshot so later resave and offline history preservation do not depend on a public cache. Only a separately specified permanent personal-data deletion/reset may purge retained personal data. Deleting a downloaded day/topic cache must never delete a Saved paper or retained snapshot.

## 29.11 Paper Detail functions

Paper Detail exposes the complete information currently available in the public paper model and the user's personal state.

Functions:

```text
read TL;DR
read summary bullets
read abstract/fallback content
inspect topic/subtopic assignments
inspect relevance and novelty
inspect authors
open arXiv page
open PDF
share external paper link
Save / Unsave
change reading status when saved
add/edit notes
add/edit/remove rating
```

If Paper Detail is opened from Swipe:

```text
Back
→ return to the same swipe session

Save
→ finalize as Swipe Right semantics

Skip
→ finalize as Swipe Left semantics
```

If Paper Detail is opened from Browse or Saved, Save/Unsave affects only personal state and does not change public feed membership.

When the displayed paper is currently saved, presenting Paper Detail updates `last_opened_at` once for that presentation. Invoking Open arXiv or Open PDF also updates it. An unsaved paper's Detail view does not create/update `last_opened_at` merely by opening.

## 29.12 Personal storage

Personal interaction data must be persisted separately from public feed caches.

Recommended iPhone source of truth:

```text
SwiftData local persistence
```

Cloud synchronization may be added through the user's private CloudKit storage without changing UI semantics.

Local persistence must be sufficient for correct core behavior even when sync is unavailable.

Required guarantees:

```text
Save survives app restart
Skip/review state survives app restart
reading status survives app restart
notes survive app restart
rating survives app restart
same arxiv_id cannot create duplicate Saved records
network failure does not block local personal-state updates
sync failure does not roll back a successful local action
```

The app should persist personal mutations atomically enough that a crash does not leave contradictory states such as `saved=true` with no retrievable saved record.

## 29.13 Offline behavior

Cache at minimum:

```text
last successful feed_index.json
last successful topics.json
daily feed files already opened/downloaded
topic feeds already opened/downloaded
Saved paper snapshots
personal interaction state
```

On network failure:

```text
show cached day index and cached papers
allow browsing already-cached collections
allow opening Saved papers from local snapshots
allow Save/Skip/Unsave/status/note/rating changes locally
show last successful public-data refresh timestamp
never replace cached history with an empty state
```

Public data refresh and personal-state persistence are independent failure domains.

## 29.14 Count and progress consistency

Server-provided public counts:

```text
day paper_count
topic total_paper_count
subtopic total_paper_count
per-topic day paper_count
```

must continue to describe canonical PaperFlow membership.

Personal counts are separate:

```text
reviewed_count
remaining_unreviewed_count
saved_count
saved_in_collection_count
queue_count
reading_count
done_count
```

Rules:

```text
displayed public day paper_count == number of papers in that public day payload
displayed public total_paper_count == canonical membership for that public view
topics.json total_paper_count == unique canonical KEEP paper count, not sum(topic counts)

reviewed_count = papers in the collection whose global personal state is seen=true
remaining_unreviewed_count = collection membership - reviewed_count
saved_count = current local saved membership
saved_in_collection_count = papers in the active public collection whose saved=true
queue/reading/done counts = current saved membership partitioned by reading_status
```

If a public count and payload disagree, treat the public payload as invalid, keep the last valid public cache, and log the mismatch.

A personal-state count mismatch should be repaired from the local personal source of truth rather than by modifying public data.

## 29.15 Search scope

V1 requires local search within Saved.

The Today and Topics roots do not display Search in V1. Saved uses native local search over saved snapshots/personal metadata. There is no V1 Settings button because no settings behavior is specified.

Saved search covers title, authors, displayed summary text (TL;DR or abstract fallback), topic names, subtopic names, and personal notes. Matching is case- and diacritic-insensitive localized substring matching, runs entirely locally, and remains available offline.

Global full-history search across every PaperFlow paper is still optional because the public feed is intentionally day-partitioned and not all history is downloaded at once.

A future global Search feature must not require changing Save/Swipe semantics.

## 29.16 Figure behavior

From day one, the public paper model includes:

```json
"hero_figure": null,
"figure_status": "not_implemented"
```

The iPhone must remain fully functional without figures.

When a valid `hero_figure` URL later appears, existing Browse, Swipe, Paper Detail, and Saved flows consume it without requiring a personal-state schema redesign.

Figure failure or absence must never block:

```text
Browse
Swipe
Save
Skip
Saved
Paper Detail
reading-status updates
notes
rating
```

## 29.17 Functional invariants

The following are mandatory:

```text
AI KEEP/DROP/FAILED state and human Save/Skip state never overwrite each other.
A Swipe Left never removes a paper from canonical history.
A Swipe Right never creates a duplicate Saved record.
Seen state is global by canonical arxiv_id across collections.
Saved state is global by canonical arxiv_id across collections.
Opening Paper Detail alone does not silently finalize triage.
Undo restores the exact prior personal state.
Swipe resume is derived from persisted state, not only an in-memory index.
Saved remains usable when the originating daily/topic feed is unavailable.
Public feed refresh failure cannot erase personal state.
Personal sync failure cannot erase a successful local action.
All public history remains reachable regardless of personal review state.
```

---

# 30. Scheduling — Configurable Local Time

The desired schedule lives in `runtime.yaml`:

```yaml
timezone: America/New_York
schedule:
  run_at_local: "21:00"
```

## 30.1 GitHub Actions constraint

GitHub Actions cron is UTC and cannot directly interpolate a repository YAML value into `on.schedule.cron`.

Therefore use a generated schedule workflow.

## 30.2 `sync_schedule` command

```bash
python -m paperflow.cli.sync_schedule
```

It reads timezone + local run time and updates only the generated schedule block in:

```text
.github/workflows/paperflow-daily.yml
```

For timezones with daylight-saving changes, emit the necessary UTC trigger times for the possible offsets, then use an application-level schedule gate so only the trigger corresponding to the configured local time performs work.

Example concept for `21:00 America/New_York`:

```text
EDT trigger candidate: 01:00 UTC
EST trigger candidate: 02:00 UTC
```

Both may exist in the workflow; the runtime gate checks the actual local time/date and exits immediately when a trigger is not due.

## 30.3 Schedule gate

A scheduled run proceeds only if:

```text
schedule enabled
configured local day is allowed
current local date has not already succeeded
current local time is at/after configured run time
```

This also makes delayed GitHub scheduled jobs safe.

Manual `workflow_dispatch` bypasses the time gate by default.

## 30.4 Config sync validation

CI must fail with a helpful message if:

```text
runtime schedule config changed
but generated workflow cron block is stale
```

Command to fix:

```bash
python -m paperflow.cli.sync_schedule
```

---

# 31. GitHub Actions

## 31.1 Daily workflow

```yaml
name: PaperFlow Daily

on:
  schedule:
    # AUTO-GENERATED schedule block
    - cron: "0 1 * * *"
    - cron: "0 2 * * *"
  workflow_dispatch:

concurrency:
  group: paperflow-daily
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest

    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install -e .

      - name: Run PaperFlow
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: python -m paperflow.main

      - name: Validate generated outputs
        run: python -m paperflow.render.validation

      - name: Commit generated content
        run: |
          git config user.name "paperflow-bot"
          git config user.email "paperflow-bot@users.noreply.github.com"
          git add -A README.md topics/ daily/ data/ site/
          if [ -d figures ]; then
            git add -A figures/
          fi
          if git diff --cached --quiet; then
            echo "No changes."
          else
            git commit -m "chore: update papers for $(date -u +%F)"
            git push
          fi
```

Before figure phase exists, `figures/` may be absent and should not cause failure.

## 31.2 CI workflow

Run full unit/integration tests on:

```text
push that changes source/config/tests
pull request
manual dispatch
```

The daily workflow needs fast validation, not necessarily the entire test suite every day.

---

# 32. Atomicity and Safe Publication

A daily run should behave transactionally at the Git level.

Rules:

1. Do not push/commit partial output.
2. All canonical changes and generated outputs remain only in the Actions working tree until validation passes.
3. If ingestion, filtering orchestration, taxonomy migration, or validation fails, the job exits non-zero and commits nothing.
4. Individual paper filter failures are represented as FAILED events and do **not** fail the whole run.
5. Individual summary failures do **not** fail the whole run.
6. Later, individual figure failures do **not** fail the whole run.
7. Use one GitHub Actions concurrency group to prevent overlapping writers.

---

# 33. Run State

`data/state.json`:

```json
{
  "schema_version": 1,
  "last_successful_run_id": "2026-08-20T21-00-00-04-00",
  "last_successful_at": "2026-08-20T21:07:12-04:00",
  "last_successful_local_date": "2026-08-20",
  "taxonomy_hash": "...",
  "runtime_config_hash": "...",
  "model_config_hash": "..."
}
```

Do not update state until output validation succeeds.

---

# 34. Run Report

Every run prints a report whose counts are observed values, never quotas.

Example:

```text
PaperFlow Daily Run — 2026-08-20

Source fetch status:          OK
RSS/API entries fetched:     612
After base-ID dedup:          487
Previously terminal:          12
Failed backlog added:          3
Candidates screened:         478

KEEP:                         41
DROP:                        434
FAILED:                        3
KEEP cap:                   NONE

Summaries generated:          39
Summary cache hits:            1
Summary failures:              1

Figure extraction:       DISABLED
Figure placeholder:       ENABLED

README rows:                  80
Topic files updated:          17

Filter model usage:
  deepseek/...                ...
Summary model usage:
  openai/...                  ...
Fallback calls:                2

Input tokens:                 ...
Output tokens:                ...
LLM inference cost:         $...

Run status: SUCCESS
```

The old `KEEP: 37` example must never be interpreted as a cap or target.

---

# 35. Persisted Run Metrics

`data/run_stats/YYYY-MM-DD.json`:

```json
{
  "run_id": "...",
  "date": "2026-08-20",
  "source_ok": true,
  "fetched": 612,
  "deduplicated": 487,
  "terminal_skipped": 12,
  "failed_backlog_added": 3,
  "screened": 478,
  "kept": 41,
  "dropped": 434,
  "filter_failed": 3,
  "summary_generated": 39,
  "summary_failed": 1,
  "figure_mode": "placeholder",
  "llm_input_tokens": 0,
  "llm_output_tokens": 0,
  "llm_cost_usd": 0.0,
  "model_breakdown": {}
}
```

Later, dashboards can use these files without changing pipeline semantics.

---

# 36. Cost Model and Expected Monthly LLM Spend

## 36.1 Verified model list-price snapshot on OpenRouter — 2026-08-20

| Model | Input / 1M | Output / 1M |
|---|---:|---:|
| DeepSeek V4 Flash 0731 | $0.065 | $0.14 |
| GLM 4.7 Flash | $0.06 | $0.40 |
| GPT-5.6 Luna | $0.20 | $1.20 |
| Mistral Small 4 | $0.15 | $0.60 |

Prices can change. Do not hard-code them into application business logic; use actual OpenRouter usage/cost data for run reports.

## 36.2 Baseline estimation assumptions

This estimate is deliberately explicit and does **not** treat 37 KEEP/day as a cap.

Example observed-volume assumption:

```text
475 screened papers/day
37 selected papers/day as a sample average only
filter batch size = 10
~4,000 fixed taxonomy/system tokens per filter batch
~300 paper-input tokens per paper
~100 filter-output tokens per paper
~550 summary-input/system tokens per selected paper
~180 summary-output tokens per selected paper
30-day month
no prompt-cache discount assumed
```

Approximate daily tokens:

```text
filter input:   334,500
filter output:   47,500
summary input:   20,350
summary output:   6,660
```

With default routing:

```text
filter  = DeepSeek V4 Flash
summary = GPT-5.6 Luna
```

Estimated inference cost:

```text
~$0.0405/day
~$1.21/month inference
```

OpenRouter pay-as-you-go currently applies a platform fee when credits are purchased; using a 5.5% fee as the current reference gives roughly:

```text
~$1.28/month effective credit cost
```

This is an estimate, not a billing guarantee.

## 36.3 Example higher-volume scenario

If the system instead sees approximately:

```text
1,000 screened/day
100 selected/day
```

under the same token assumptions and default models:

```text
~$2.76/month inference
~$2.91/month including a 5.5% credit-purchase fee reference
```

Therefore V1 is comfortably low-cost. Reliability and filtering quality matter more than shaving the final few cents.

## 36.4 Cost-control rule

Do not implement a paper-selection cap to control LLM cost.

If cost becomes material, optimize in this order:

```text
1. prompt size / taxonomy rendering
2. prompt caching
3. batch size
4. cheaper primary model
5. provider routing
6. only then consider operational candidate safeguards
```

Never hide relevant papers to hit an arbitrary daily KEEP quota.

---

# 37. Taxonomy Reclassification

Normal daily runs classify only unseen + retry-eligible FAILED candidates.

Taxonomy changes do not automatically reclassify all history.

Explicit commands:

```bash
python -m paperflow.cli.reclassify --all-selected
python -m paperflow.cli.reclassify --since 2026-01-01
python -m paperflow.cli.reclassify --topic world-models
python -m paperflow.cli.reclassify --screened-drops --since 2026-08-01
```

For historical DROP records, refetch title/abstract from arXiv by ID as needed rather than storing every full abstract forever in the screening ledger.

Reclassification writes new screening events rather than deleting old ones.

---

# 38. Manual Maintenance CLI

```bash
# Normal/manual run
python -m paperflow.main --manual

# Validate taxonomy
python -m paperflow.cli.validate_taxonomy

# Preview exact prompt
python -m paperflow.cli.prompt_preview filter
python -m paperflow.cli.prompt_preview summary
python -m paperflow.cli.prompt_preview taxonomy

# Rebuild local outputs only; no arXiv/LLM calls
python -m paperflow.cli.rebuild_outputs
python -m paperflow.cli.rebuild_outputs --dry-run

# Reprocess one paper
python -m paperflow.cli.reprocess --paper 2608.12345

# Reclassify historical subset
python -m paperflow.cli.reclassify --since 2026-08-01

# Regenerate GitHub Actions schedule from runtime.yaml
python -m paperflow.cli.sync_schedule

# Final phase only
python -m paperflow.cli.rebuild_figures --paper 2608.12345
```

`rebuild_outputs` must perform **zero** arXiv, LLM, or PDF-network calls.

---

# 39. Validation Before Automated Commit

The validation command must check all of the following.

```text
CONFIG
✓ runtime.yaml parses
✓ models.yaml parses
✓ topics.yaml parses
✓ prompt manifest parses
✓ model aliases resolve
✓ configured task chains are non-empty
✓ schedule config is valid
✓ generated workflow schedule is synchronized

TAXONOMY
✓ active IDs unique
✓ previous_ids valid
✓ moved_from valid
✓ paths safe
✓ descriptions non-empty
✓ no duplicate active parent for a subtopic
✓ migration plan has no ambiguity
✓ all selected canonical assignments valid after migration
✓ prompt renders successfully

SCREENING
✓ screening event IDs valid
✓ latest-state reduction deterministic
✓ KEPT and DROPPED terminal in normal daily processing
✓ FAILED retry eligibility correct
✓ retry-exhausted papers not auto-retried

SELECTED STORE
✓ no duplicate arXiv IDs
✓ every paper has filter_status=kept
✓ every paper has >=1 assignment
✓ all assignments exist in active taxonomy
✓ summary state internally consistent

MARKDOWN
✓ root README has <=80 paper rows (and no other view is truncated by this limit)
✓ every configured large-topic folder exists
✓ every large-topic README exists
✓ every configured subtopic Markdown exists
✓ large-topic histories complete across all KEEP papers
✓ subtopic histories complete across all KEEP papers
✓ all tables use identical schema

JSON
✓ feed_index.json schema valid
✓ feed_index.json timezone matches runtime.yaml
✓ topics.json exactly mirrors config hierarchy
✓ topic feed membership matches canonical assignments
✓ feed_index.json contains every successful historical day and correct counts
✓ every public paper includes the original abstract
✓ every daily/topic feed URL is explicitly published and resolves from base_url
✓ every daily/topic public paper has figure fields even while null/not_implemented

WEBSITE
✓ routes mirror taxonomy
✓ root website exposes full KEEP history
✓ large-topic/subtopic website pages expose full matching history
✓ every rendered day header has the correct paper count
✓ no broken generated internal links

FILESYSTEM SAFETY
✓ only AUTO-GENERATED stale files are removable
✓ no manual file is scheduled for deletion

RUN
✓ state is updated only after successful validation
```

---

# 40. Tests

## 40.1 Ingestion tests

```text
[ ] new v1 submission retained
[ ] update/replacement excluded from normal new-only flow
[ ] cross-listed paper retained
[ ] version suffix normalized
[ ] category union preserved during dedup
[ ] source failure is distinguishable from valid zero-result day
```

## 40.2 Dedup tests

```text
[ ] same base arXiv ID from cs.CV + cs.RO → one candidate
[ ] categories merged
[ ] title/abstract normalization does not alter scientific text meaning
```

## 40.3 Retry tests — mandatory v3

```text
[ ] FAILED paper in today's feed → retried
[ ] FAILED paper absent from today's feed → still retried from backlog
[ ] DROPPED paper reappears → skipped
[ ] KEPT paper reappears → skipped
[ ] FAILED paper succeeds → new latest state becomes KEPT/DROPPED
[ ] failed attempts increment correctly
[ ] exhausted FAILED paper remains FAILED and is not auto-retried
[ ] manual reprocess can override retry exhaustion
```

## 40.4 LLM filter schema tests

```text
[ ] relevance <1 rejected
[ ] relevance >10 rejected
[ ] novelty <1 rejected
[ ] novelty >10 rejected
[ ] KEEP + [] assignments rejected
[ ] DROP + non-empty assignments rejected
[ ] unknown topic rejected
[ ] subtopic under wrong parent rejected
[ ] duplicate topic assignment rejected
[ ] duplicate subtopic removed/rejected deterministically
[ ] missing arXiv ID rejected
[ ] extra arXiv ID rejected
[ ] duplicate result ID rejected
[ ] missing batch result triggers retry
[ ] valid subset retained when another result is invalid
[ ] invalid subset retried once on next model
[ ] second semantic failure → FAILED, never DROP
```

## 40.5 Taxonomy migration tests

```text
[ ] display-name rename changes labels only
[ ] topic ID rename via previous_ids rewrites history
[ ] subtopic ID rename via previous_ids rewrites history
[ ] subtopic move via moved_from rewrites parent
[ ] move removes empty old assignment
[ ] move does not duplicate target assignment
[ ] rename + move together works
[ ] old parent still containing moved ID fails validation
[ ] removed in-use ID without migration blocks rebuild
[ ] stale generated file not removed before successful migration
[ ] manual unknown file is never deleted
```

## 40.6 Summary tests

```text
[ ] only KEEP papers summarized
[ ] 3-5 bullet constraint enforced
[ ] summary failure leaves paper selected
[ ] summary failure uses abstract fallback in views
[ ] summary retry success updates status
[ ] cache invalidates when abstract/prompt/model key changes
```

## 40.7 README tests

```text
[ ] 0 papers
[ ] 1 paper
[ ] 79 papers
[ ] 80 papers
[ ] 81 papers
[ ] 500 papers
[ ] README never exceeds 80 rows
[ ] README latest 80 does not truncate any app/website/topic/daily/public-JSON history
```

## 40.8 Topic tests

```text
[ ] large-topic full history correct
[ ] subtopic full history correct
[ ] no unrelated rows
[ ] newest first
[ ] multi-topic paper appears in all matching views
[ ] parent-only assignment appears in large topic but no child subtopic
[ ] empty configured topic still generated
```

## 40.9 JSON/website tests

```text
[ ] feed_index.json schema stable
[ ] feed_index timezone is valid and matches runtime config
[ ] feed_index contains every successful historical day
[ ] feed_index total_paper_count equals selected-store KEEP count
[ ] each feed_index day paper_count equals that daily feed length
[ ] each daily feed contains all KEEP papers for that day
[ ] no daily feed is truncated to 80
[ ] topics.json hierarchy exact
[ ] topic counts match full canonical assignments
[ ] per-topic feeds contain full matching history
[ ] per-topic day counts match day-section membership
[ ] topics.json total_paper_count counts unique canonical papers rather than summed topic memberships
[ ] each public paper includes abstract for detail/fallback
[ ] feed_index/topics feed_url values resolve against publication-root base_url
[ ] invalid absolute/root-escaping/query/fragment feed paths rejected
[ ] JSON and Markdown topic/subtopic membership match
[ ] root website exposes full KEEP history
[ ] topic/subtopic website pages expose full matching history
[ ] website day counts match rendered paper membership
[ ] website route count matches taxonomy
[ ] internal links resolve
```

## 40.10 iPhone functional tests

```text
[ ] feed index decodes correctly
[ ] main app can reach papers older than the newest 80
[ ] newest daily feed decodes with hero_figure=null
[ ] daily paper decodes required abstract
[ ] daily and topic URLs come from JSON and resolve against configured base_url
[ ] each public day section shows exact paper_count
[ ] day payload length matches displayed public paper_count
[ ] older day feeds lazy-load correctly
[ ] topic list driven entirely by topics.json
[ ] topic/subtopic feeds expose full matching history
[ ] topic/subtopic day counts are correct
[ ] Today binds to the current local date rather than relabeling newest older day
[ ] absent current date shows unavailable + Latest Available, not valid-zero copy
[ ] present zero-count current date shows the zero-matching state
[ ] Today/Topics have no Search or Settings control in V1

[ ] Today opens both Browse and Swipe flows
[ ] Large Topic/Subtopic opens both Browse and Swipe flows
[ ] Browse does not mark a paper reviewed merely by rendering it
[ ] opening Paper Detail alone does not finalize swipe triage
[ ] Swipe Left records reviewed/seen without altering filter_status
[ ] Swipe Right records reviewed + saved + queue without altering filter_status
[ ] Swipe Right is idempotent for an already-saved paper
[ ] Swipe Right does not reset reading/done back to queue
[ ] left-swiping an already-saved paper in review-again mode does not silently unsave it
[ ] same arxiv_id has one global seen state across day/topic/subtopic
[ ] same arxiv_id has one global saved state across day/topic/subtopic
[ ] swipe deck defaults to globally unreviewed papers
[ ] every deck displays reviewed/total plus remaining with the same semantics
[ ] swipe progress is restored after app restart
[ ] undo Skip restores exact prior state
[ ] undo first-time Save restores exact prior state
[ ] undo of already-saved paper preserves its pre-swipe reading state

[ ] Saved contains every currently saved paper
[ ] Saved deduplicates by versionless arxiv_id
[ ] Saved queue/reading/done transitions persist
[ ] first/last save, unsave, status, completion, and last-opened timestamps follow Section 29.8
[ ] Saved notes persist
[ ] Saved rating persists
[ ] unsave does not delete canonical/public history
[ ] unsave does not silently reset seen state
[ ] unsave retains reading state, timestamps, note, rating, and offline snapshot
[ ] resave updates last_saved_at while preserving first saved_at and later reading state
[ ] Reading sorts by last_opened_at with specified fallback
[ ] Done sorts by completed_at
[ ] saved paper remains available after its originating public feed cache is removed
[ ] Saved local search returns matching saved papers
[ ] Saved counts equal local saved-state membership

[ ] cached day index + downloaded day feeds appear offline
[ ] Saved snapshots appear offline
[ ] Save/Skip/status/note/rating updates work offline
[ ] refresh failure does not erase cached feed/history
[ ] public refresh failure does not erase personal state
[ ] sync failure does not roll back successful local state

[ ] placeholder appears when no figure exists
[ ] future non-null hero URL works without public or personal schema migration
```

## 40.11 Scheduler tests

```text
[ ] local time converted correctly during EST
[ ] local time converted correctly during EDT
[ ] wrong DST candidate trigger exits
[ ] due trigger runs
[ ] second trigger after same-day success exits
[ ] delayed scheduled run still catches up same day
[ ] manual dispatch bypasses schedule gate
[ ] stale generated workflow schedule detected in CI
```

---

# 41. Integration Fixture

Create:

```text
tests/fixtures/arxiv_daily_sample.json
```

Fixture characteristics:

```text
12 raw source entries
2 cross-listed duplicates
10 unique candidate papers
3 KEEP
6 DROP
1 simulated FAILED
1 KEEP assigned to 3 large topics
1 KEEP assigned to multiple subtopics under one parent
```

Expected first run:

```text
unique candidates = 10
KEEP = 3
DROP = 6
FAILED = 1
selected store contains 3 papers
screening ledger receives 10 events
daily archive contains 3 rows
README contains 3 rows
```

Second run fixture omits the failed paper from the source but makes its retry succeed.

Expected second run:

```text
failed backlog contributes 1 paper
that paper is processed despite being absent from source feed
latest screening status changes from FAILED to KEEP or DROP
```

This integration test is the proof that F1 is truly fixed.

---

# 42. Observability

Log one structured event per major stage:

```text
run_started
config_loaded
taxonomy_validated
taxonomy_migration_planned
source_fetch_completed
dedup_completed
retry_backlog_built
filter_batch_started
filter_batch_completed
filter_validation_failed
summary_started
summary_completed
render_completed
validation_completed
run_succeeded
run_failed
```

Never log:

```text
OPENROUTER_API_KEY
Authorization headers
secret-bearing environment dump
```

Raw abstracts are already public arXiv data but still do not need to be dumped into verbose CI logs.

---

# 43. Security and Secrets

`.env.example`:

```bash
OPENROUTER_API_KEY=
PAPERFLOW_HTTP_REFERER=
PAPERFLOW_APP_TITLE=PaperFlow
```

`.gitignore`:

```text
.env
cache/
*.tmp
.DS_Store
```

GitHub:

```text
Settings → Secrets and variables → Actions → OPENROUTER_API_KEY
```

Use a dedicated OpenRouter key for PaperFlow so spend can be measured/revoked independently.

---

# 44. Implementation Phases — Required Order

The order below is intentional. Do not start the next major phase before the current phase's acceptance criteria pass.

## Phase 0 — Repository + test skeleton

- package layout
- config directory
- pytest
- basic CI
- generated-file marker helper

**Exit:** import works, unit test runs in CI.

## Phase 1 — Config foundation

- runtime config schema
- model config schema
- prompt manifest
- environment/secret loader
- config hashes

**Exit:** all configs validate; no model/topic/schedule duplicated in code.

## Phase 2 — Taxonomy core + migrations

- taxonomy models
- validation
- stable IDs
- `previous_ids`
- `moved_from`
- migration planner
- taxonomy snapshot/diff
- prompt taxonomy renderer

**Exit:** rename/move tests pass; invalid removal safely blocks.

## Phase 3 — Screening ledger + selected store

- append-only screening events
- latest-state reducer
- selected `papers.json`
- atomic/validated save helpers
- run state

**Exit:** KEEP/DROP/FAILED transitions tested.

## Phase 4 — arXiv ingestion + dedup

- configured categories
- NEW-only normalization
- base-ID dedup
- cross-list category merge
- source error handling
- local raw snapshot cache

**Exit:** fixture produces expected unique candidates.

## Phase 5 — Retry backlog

- `determine_workset`
- failed metadata refetch
- cooldown
- max attempts
- retry exhaustion
- manual override

**Exit:** failed paper is retried even when absent from next source feed.

## Phase 6 — OpenRouter abstraction

- one client
- four model profiles
- structured output
- provider/model fallback
- transient retry
- usage/cost capture
- actual model recording

**Exit:** smoke test can switch among all configured models without business-logic changes.

## Phase 7 — Filtering

- Jinja prompts
- batch filtering
- strict Pydantic schema
- KEEP assignment validator
- taxonomy semantic validator
- partial batch salvage
- one semantic retry
- screening event persistence

**Exit:** no malformed result silently becomes DROP.

## Phase 8 — Summaries

- summary prompt
- structured schema
- cache
- summary status
- failure fallback
- retry backlog for failed summaries

**Exit:** selected paper always publishes even when summary fails.

## Phase 9 — Markdown + JSON outputs

- shared row renderer
- root README latest 80 **only**
- daily archive with exact daily KEEP count
- large-topic full-history archive
- subtopic full-history archive
- `feed_index.json` with full-history day counts
- per-day JSON feeds containing all KEEP papers for each day
- `topics.json`
- per-topic full-history feeds grouped by day
- stale generated-file cleanup

**Exit:** all generated-artifact validation passes.

## Phase 10 — Static website

- shared view model
- root full-history feed grouped by day
- exact paper count in every day header
- topic/subtopic full-history pages grouped by day
- per-view daily counts
- stable routes
- older-day navigation/lazy loading
- internal link validation

**Exit:** website matches Markdown/JSON membership exactly.

## Phase 11 — iPhone V1 functional app + personal triage + figure placeholder

- JSON models and API client
- primary tabs: Today / Topics / Saved
- full-history Today feed with feed index + per-day lazy loading
- exact public day paper counts
- dynamic topics and subtopics from `topics.json`
- topic/subtopic full-history detail with per-view day counts
- Browse mode for day/topic/subtopic collections
- Swipe mode for day/topic/subtopic collections
- global per-paper reviewed/seen state
- Swipe Left = reviewed/skip
- Swipe Right = Save + queue
- idempotent Save keyed by versionless arXiv ID
- resumable swipe progress
- transactional Undo for the latest swipe action
- Paper Detail integration with Browse/Swipe/Saved
- Saved Deep Read Queue
- queue / reading / done status
- personal notes
- optional personal rating
- Saved local search and sorting
- SwiftData personal persistence
- offline Saved snapshots
- optional private CloudKit sync without changing UI semantics
- public-feed cache/offline state
- pull-to-refresh and last-updated state
- figure placeholder behavior
- future real-figure compatibility

**Exit:** all Browse, Swipe, Save, Skip, Saved, reading-tracking, detail, and offline flows work correctly with `hero_figure=null` for every paper, and no human action mutates AI screening/public canonical state.

## Phase 12 — Scheduling + GitHub automation

- schedule gate
- DST-safe workflow schedule generation
- workflow sync validation
- daily Action
- concurrency protection
- secret wiring
- automated commit

**Exit:** two consecutive real scheduled runs complete without manual repair.

## Phase 13 — Hardening + real-world soak

Run the entire system without figure extraction for several days.

Validate:

```text
no missed FAILED retries
no duplicate papers
no unexpected taxonomy drift
no partial Git commits
cost reports plausible
iPhone public cache stable
personal Save/Skip/Saved state stable across restart/offline use
summary failure fallback acceptable
README/topic history correct
schedule correct through real GitHub execution
```

**Exit:** core system is considered stable.

## Phase 14 — FIGURE EXTRACTION — FINAL TASK ONLY

Only begin this phase after Phase 13 passes.

This satisfies the explicit requirement that figure extraction be the last implementation task.

---

# 45. Final Figure Extraction Phase

## 45.1 Non-negotiable behavior

Even after implemented:

```text
figure extraction failure
→ hero_figure = null
→ iPhone/web placeholder
→ publication continues
```

Never put PDF/figure extraction on the critical path for paper inclusion.

## 45.2 Download policy

Download PDFs for KEEP papers only.

```text
cache/pdf/<arxiv_id>.pdf
```

PDFs are temporary and gitignored.

Use low download concurrency.

## 45.3 Two concrete extraction options

### Option A — PDFFigures 2.0

Use AllenAI `pdffigures2` as the first scientific-paper-specific baseline.

Advantages:

- built specifically for scholarly PDFs;
- extracts figure/table regions;
- extracts captions;
- returns bounding boxes/page metadata;
- can rasterize extracted regions;
- has published evaluation tooling/datasets;
- especially relevant to computer-science papers.

Disadvantages:

- Scala/JVM dependency;
- older project;
- unusual PDF encoding/layout can fail;
- maintenance/integration is less Python-native.

### Option B — Docling figure/picture export

Use Docling as the modern Python-native alternative.

Advantages:

- active document-processing ecosystem;
- can generate picture images from PDFs;
- structured document model;
- easier Python integration;
- offers optional picture classification/enrichment later.

Disadvantages:

- heavier pipeline than the smallest custom solution;
- needs empirical evaluation specifically on PaperFlow's arXiv sample;
- picture region semantics may differ from exact paper "Figure N" grouping.

### Decision gate

Do **not** choose by intuition.

Build an evaluation set of at least 50 KEEP papers spanning:

```text
single-column papers
two-column papers
multi-panel figures
vector diagrams
raster figures
full-width architecture figures
tables near figures
figures with long captions
```

Manually label the desired hero figure for each paper.

Compare:

```text
figure detection recall
figure crop correctness
caption association correctness
hero-selection top-1 accuracy
runtime/paper
failure rate
installation/deployment complexity
```

Choose the default extractor only after this comparison.

## 45.4 Figure metadata schema

```python
class FigureMetadata(BaseModel):
    figure_number: str | None
    page: int
    caption: str | None
    bbox: tuple[float, float, float, float]
    image_path: str
    width: int
    height: int
    extractor: str
    extractor_version: str | None
```

## 45.5 Hero scoring

Start with deterministic heuristics rather than another LLM.

```python
HERO_KEYWORDS = {
    "overview": 5,
    "architecture": 5,
    "framework": 5,
    "pipeline": 4,
    "method": 3,
    "system": 3,
    "model": 2,
}
```

Score components:

```text
caption keyword score
large-area bonus
reasonable landscape-aspect bonus
very-small-region penalty
table penalty
appendix/late-page mild penalty
```

Fallback:

```text
1. highest heuristic score
2. largest non-table figure
3. first valid figure
4. no figure → placeholder
```

## 45.6 Output

```text
figures/<arxiv_id>/hero.webp
```

Recommended published image:

```text
WebP
long edge <= 1600 px
quality ~88
```

Optional source/vector crop can remain uncommitted unless there is a concrete need.

## 45.7 iPhone transition

No iPhone architecture change should be needed.

Before figures:

```json
"hero_figure": null,
"figure_status": "not_implemented"
```

After successful extraction:

```json
"hero_figure": "figures/2608.12345/hero.webp",
"figure_status": "ready"
```

On failure:

```json
"hero_figure": null,
"figure_status": "failed"
```

`PaperHeroView` already handles all three states.

---

# 46. Final Implementation Checklist

This is the checklist to execute in order.

## A. Bootstrap

- [ ] Create repository structure.
- [ ] Add `pyproject.toml` and Python 3.12 environment.
- [ ] Add pytest and base CI.
- [ ] Add `.env.example` and `.gitignore`.
- [ ] Add generated-file marker helper.
- [ ] Add logging/run-ID utility.

## B. Configuration

- [ ] Implement `RuntimeConfig`.
- [ ] Implement `ModelConfig`.
- [ ] Implement prompt manifest loader.
- [ ] Implement environment-variable secret loader.
- [ ] Add config hash calculation.
- [ ] Add config validation CLI.
- [ ] Confirm no hard-coded topic/model/category/run-time lists in Python/Swift.

## C. Taxonomy

- [ ] Implement two-level taxonomy models.
- [ ] Implement stable ID regex/uniqueness checks.
- [ ] Implement include/exclude examples.
- [ ] Implement `previous_ids`.
- [ ] Implement `moved_from`.
- [ ] Reject moved subtopic that remains under old parent.
- [ ] Implement taxonomy snapshot.
- [ ] Implement taxonomy diff report.
- [ ] Implement rename migration planner.
- [ ] Implement re-parenting migration planner.
- [ ] Implement combined rename+move migration.
- [ ] Validate migrated historical assignments before any stale-file cleanup.
- [ ] Add taxonomy dry-run CLI.

## D. Prompts

- [ ] Implement `taxonomy_block.j2`.
- [ ] Implement `filter_system.j2`.
- [ ] Implement `filter_user.j2`.
- [ ] Implement `summary_system.j2`.
- [ ] Implement `summary_user.j2`.
- [ ] Add prompt version/hash metadata.
- [ ] Add prompt preview CLI.
- [ ] Verify taxonomy edits change rendered filter prompt without code edits.

## E. Screening state

- [ ] Implement `FilterStatus` with KEPT/DROPPED/FAILED.
- [ ] Implement append-only monthly screening event ledger.
- [ ] Implement latest-state reducer.
- [ ] Add attempt count/cooldown/next retry metadata.
- [ ] Add retry-exhausted state.
- [ ] Verify DROP and KEEP are terminal in normal daily flow.
- [ ] Verify FAILED remains retry-eligible.

## F. Selected store

- [ ] Implement `data/papers.json` keyed selected-paper store.
- [ ] Store full metadata for KEEP papers.
- [ ] Store filter/prompt/taxonomy/model provenance.
- [ ] Add summary state fields.
- [ ] Add `hero_figure=null` and `figure_status=not_implemented` from day one.
- [ ] Validate every selected paper has at least one assignment.

## G. arXiv ingestion

- [ ] Read categories from runtime config.
- [ ] Fetch configured NEW submissions.
- [ ] Normalize versionless canonical arXiv ID.
- [ ] Preserve source version ID.
- [ ] Deduplicate across categories.
- [ ] Merge category lists.
- [ ] Distinguish source failure from successful empty result.
- [ ] Save raw snapshot only to cache/debug area.

## H. Retry queue — mandatory before LLM filtering

- [ ] Build today's unseen candidate set.
- [ ] Build prior FAILED backlog independently of today's feed.
- [ ] Refetch metadata for failed paper absent from current feed.
- [ ] Deduplicate new candidates against backlog.
- [ ] Apply cooldown.
- [ ] Apply max automatic attempt count.
- [ ] Never convert exhausted failure into DROP.
- [ ] Add manual reprocess override.

## I. OpenRouter integration

- [ ] Add `OPENROUTER_API_KEY` support.
- [ ] Add one OpenRouter client wrapper.
- [ ] Configure `deepseek/deepseek-v4-flash-0731`.
- [ ] Configure `z-ai/glm-4.7-flash` under alias `glm_4_7_flashx`.
- [ ] Configure `openai/gpt-5.6-luna`.
- [ ] Configure `mistralai/mistral-small-2603`.
- [ ] Implement task-specific primary/fallback chains.
- [ ] Enable structured JSON-schema output.
- [ ] Implement transient retry policy.
- [ ] Record requested + actual model.
- [ ] Record usage tokens + reported cost.
- [ ] Verify a YAML-only model switch works.

## J. Filtering

- [ ] Implement `TopicAssignment` schema.
- [ ] Implement `FilterResult` schema.
- [ ] Enforce relevance/novelty 1–10.
- [ ] Enforce KEEP → >=1 assignment.
- [ ] Enforce DROP → assignments=[] .
- [ ] Validate active topic IDs.
- [ ] Validate parent-child relationships.
- [ ] Validate exact batch arXiv-ID set.
- [ ] Accept valid results from a partially invalid batch.
- [ ] Retry invalid subset exactly once with next model.
- [ ] Persist final KEEP/DROP/FAILED screening events.
- [ ] Verify no silent invalid→DROP path exists.

## K. Summaries

- [ ] Implement `SummaryResult`.
- [ ] Use title + abstract only.
- [ ] Enforce 3–5 bullets.
- [ ] Add summary cache.
- [ ] Add summary retry behavior.
- [ ] Keep paper selected on summary failure.
- [ ] Use abstract fallback in public view model.
- [ ] Record summary model/cost metadata.

## L. Markdown and JSON rendering

- [ ] Implement one shared paper table header.
- [ ] Implement one shared row renderer.
- [ ] Generate README topic map from YAML.
- [ ] Generate root README latest 80.
- [ ] Confirm `readme_latest_limit` is referenced only by root README rendering.
- [ ] Generate daily archive with no KEEP cap and exact `Papers kept: N`.
- [ ] Generate large-topic full-history files.
- [ ] Generate subtopic full-history files.
- [ ] Verify every subtopic README contains every matching KEEP paper.
- [ ] Generate empty configured topics.
- [ ] Generate `feed_index.json` containing every successful historical day + exact day counts.
- [ ] Publish the configured IANA timezone in `feed_index.json`.
- [ ] Generate `daily_feeds/YYYY-MM-DD.json` with every KEEP paper for each day.
- [ ] Include the full original abstract in every public paper object.
- [ ] Generate `topics.json` using full-history counts.
- [ ] Make `topics.json.total_paper_count` the unique canonical KEEP count.
- [ ] Publish explicit safe day/topic/subtopic `feed_url` values resolved from the publication-root base URL.
- [ ] Generate per-topic full-history JSON feeds grouped by day with counts.
- [ ] Add generated-file markers.
- [ ] Implement safe stale generated-file cleanup.

## M. Static website

- [ ] Build root full-history feed page.
- [ ] Group root feed by day.
- [ ] Show exact KEEP paper count in every day header.
- [ ] Keep every historical day reachable.
- [ ] Build dynamic topic navigation.
- [ ] Build large-topic full-history routes.
- [ ] Build subtopic full-history routes.
- [ ] Group topic/subtopic histories by day with per-view day counts.
- [ ] Reuse same membership/count view-model logic as JSON/Markdown.
- [ ] Validate all generated internal links.

## N. iPhone V1 — functional app, swipe triage, Saved, placeholder figures

- [ ] Define Swift Codable public API models.
- [ ] Add configurable base URL.
- [ ] Require a publication-root base URL and consume explicit feed URLs without deriving topic paths.
- [ ] Build primary tabs: Today / Topics / Saved.
- [ ] Fetch `feed_index.json`.
- [ ] Build full-history Today screen.
- [ ] Derive Today from the IANA publication timezone in `feed_index.json`.
- [ ] Distinguish current-day zero from absent feed and label an older feed Latest Available.
- [ ] Show exact public `paper_count` for every day.
- [ ] Lazy-load `daily_feeds/YYYY-MM-DD.json`.
- [ ] Verify papers older than the newest 80 remain reachable.
- [ ] Build Topics from `topics.json`.
- [ ] Build Large Topic full-history behavior.
- [ ] Build Subtopic full-history behavior.
- [ ] Preserve per-view public day counts.
- [ ] Label Topics total as unique `Total Papers`, not summed topic memberships.
- [ ] Add Browse mode for day/topic/subtopic collections.
- [ ] Add Swipe mode for day/topic/subtopic collections.
- [ ] Default Swipe to globally unreviewed papers.
- [ ] Show reviewed/total and remaining with identical semantics in every deck.
- [ ] Implement canonical versionless arXiv ID personal identity.
- [ ] Implement global reviewed/seen state.
- [ ] Implement Swipe Left = reviewed/skip.
- [ ] Implement Swipe Right = reviewed + saved + `queue`.
- [ ] Ensure Save is idempotent.
- [ ] Ensure review-again left swipe cannot silently unsave.
- [ ] Persist swipe progress from personal state.
- [ ] Resume incomplete swipe sessions across launches.
- [ ] Implement transactional Undo of the most recent swipe action.
- [ ] Build Paper Detail.
- [ ] Ensure opening Paper Detail alone does not finalize triage.
- [ ] Allow Save/Skip from Paper Detail when entered from Swipe.
- [ ] Implement Saved Deep Read Queue.
- [ ] Implement `queue` / `reading` / `done`.
- [ ] Implement first/last Save, Unsave, status/start/completion, and last-opened timestamps.
- [ ] Implement personal notes.
- [ ] Implement optional personal rating.
- [ ] Implement local Saved search.
- [ ] Implement Saved sorting.
- [ ] Back Queue/Reading/Done sorts with the specified timestamps and fallbacks.
- [ ] Implement history-preserving Unsave/resave exactly as specified.
- [ ] Store enough Saved snapshot metadata for offline use.
- [ ] Use SwiftData as the personal local source of truth.
- [ ] Ensure personal mutations work offline.
- [ ] Ensure network/sync failure does not roll back successful local mutations.
- [ ] Optionally enable private CloudKit synchronization without changing interaction semantics.
- [ ] Cache feed index plus downloaded day/topic feeds.
- [ ] Add pull-to-refresh.
- [ ] Add last-updated public-data state.
- [ ] Omit Today/Topics Search and Settings controls; keep search local to Saved.
- [ ] Implement figure placeholder handling.
- [ ] Confirm app is fully usable when every `hero_figure` is null.
- [ ] Confirm future non-null hero URL requires no public or personal schema redesign.
- [ ] Confirm AI `KEEP/DROP/FAILED` and human `Save/Skip` remain independent.

## O. Scheduling and automation

- [ ] Implement local timezone schedule gate.
- [ ] Implement `sync_schedule` CLI.
- [ ] Generate DST-safe UTC cron candidates.
- [ ] Add workflow schedule/config mismatch validation.
- [ ] Add `workflow_dispatch`.
- [ ] Add GitHub concurrency lock.
- [ ] Add OpenRouter secret.
- [ ] Run fast generated-output validation before commit.
- [ ] Commit only after success.
- [ ] Confirm failed workflow pushes nothing.
- [ ] Verify two real scheduled runs.

## P. Metrics + hardening

- [ ] Persist run stats.
- [ ] Report KEEP/DROP/FAILED separately.
- [ ] Explicitly report `KEEP cap: NONE`.
- [ ] Report filter/summary model breakdown.
- [ ] Report actual token usage/cost.
- [ ] Add source-failure alert in logs.
- [ ] Add duplicate-paper invariant check.
- [ ] Add full test matrix from Section 40.
- [ ] Run multi-day soak test with figures disabled.
- [ ] Do not start figure work until soak test is stable.

## Q. FIGURE EXTRACTION — LAST TASK

- [ ] Freeze working core release before figure work.
- [ ] Build 50+ paper labeled figure-evaluation set.
- [ ] Implement PDFFigures2 adapter.
- [ ] Implement Docling adapter.
- [ ] Evaluate detection/crop/caption/hero quality.
- [ ] Pick default extractor from measured results.
- [ ] Download PDFs for KEEP papers only.
- [ ] Keep PDFs in gitignored cache.
- [ ] Implement figure metadata schema.
- [ ] Implement deterministic hero scoring.
- [ ] Render `hero.webp`.
- [ ] Add figure concurrency limit.
- [ ] Make every extraction failure non-blocking.
- [ ] Publish `hero_figure` URL when ready.
- [ ] Keep placeholder for null/failed hero figure.
- [ ] Add `rebuild_figures --paper` CLI.
- [ ] Add figure tests only after the core release remains green.

---

# 47. Definition of Done

PaperFlow V1 core is done **before** figure extraction when all of these are true:

```text
[ ] Config controls topics, prompts, model routing, source categories, and run time.
[ ] OpenRouter is the only LLM integration surface.
[ ] All four requested model families are switchable from config.
[ ] The verified GLM slug mismatch is handled explicitly.
[ ] New papers are deduplicated correctly.
[ ] No daily KEEP cap exists.
[ ] Every screening attempt has a durable event.
[ ] FAILED papers retry even if absent from the next arXiv feed.
[ ] DROP remains terminal during normal daily operation.
[ ] KEEP always has >=1 valid topic assignment.
[ ] Taxonomy rename and re-parenting migrations work.
[ ] Summary failures do not remove papers.
[ ] Every public paper includes the original abstract for Detail/fallback.
[ ] Public day/topic/figure URLs obey the publication-root contract and are not derived in Swift.
[ ] Root README is the only 80-paper-limited view; app/website/topic/daily/public-JSON views expose full applicable KEEP history.
[ ] iPhone and website display exact paper counts for every rendered day section.
[ ] iPhone topics are dynamic.
[ ] Topics Total Papers is the unique canonical count; overlapping topic rows are not summed.
[ ] Today uses the feed's publication timezone and distinguishes absent feed from successful zero.
[ ] Today, Large Topic, and Subtopic collections support Browse and Swipe.
[ ] Swipe Left records human review/skip without changing AI filter status.
[ ] Swipe Right saves globally by canonical arXiv ID and enters the Deep Read Queue.
[ ] Swipe progress resumes from persisted state and Undo restores exact prior state.
[ ] Every Swipe deck uses reviewed/total plus remaining semantics.
[ ] Saved supports queue/reading/done, notes, local search, and optional rating.
[ ] Saved sorts use real Save/open/completion timestamps.
[ ] Unsave/resave retains personal history and offline snapshot exactly as specified.
[ ] Search is Saved-only; Today/Topics contain no inactive Search or Settings controls.
[ ] Saved/personal state remains usable offline and is never erased by public refresh failure.
[ ] iPhone shows a stable figure placeholder.
[ ] GitHub Actions runs at configured local time correctly across DST.
[ ] Only validated successful runs are committed.
[ ] Actual OpenRouter usage/cost is recorded.
[ ] Multi-day soak test passes with figures disabled.
```

Only then begin the final figure-extraction phase.

PaperFlow including figures is done when:

```text
[ ] figure extractor chosen by measured evaluation
[ ] figure failures never block publication
[ ] iPhone automatically displays real hero figures when present
[ ] placeholder remains correct when a figure is absent or extraction fails
```

---

# 48. External Verification Notes — 2026-08-20

The implementation plan uses the following externally verified facts at the time of writing:

- OpenRouter model fallback supports an ordered `models` list and charges according to the model ultimately used.
- OpenRouter exposes structured-output capability information per model.
- DeepSeek V4 Flash 0731 is available as `deepseek/deepseek-v4-flash-0731`.
- GPT-5.6 Luna is available as `openai/gpt-5.6-luna`.
- GLM 4.7 Flash is available as `z-ai/glm-4.7-flash`; a distinct GLM 4.7 FlashX slug was not verified.
- Mistral Small 4 is available as `mistralai/mistral-small-2603`.
- PDFFigures2 explicitly extracts figures/tables/captions/bounding boxes from scholarly PDFs.
- Docling can generate/export picture images from PDFs and is a viable Python-native figure-extraction alternative.

Reference URLs:

```text
https://openrouter.ai/docs/guides/routing/model-fallbacks
https://openrouter.ai/deepseek/deepseek-v4-flash-0731
https://openrouter.ai/openai/gpt-5.6-luna-20260709
https://openrouter.ai/z-ai/glm-4.7-flash/pricing
https://openrouter.ai/mistralai/mistral-small-2603
https://openrouter.ai/pricing
https://github.com/allenai/pdffigures2
https://docling-project.github.io/docling/_generated/examples/export_figures/
```

Because model availability and pricing can change, the production code should record actual returned model IDs and actual per-request usage/cost instead of depending on this static snapshot.

---

# 49. Final Locked Implementation Order

```text
1. Repository/test skeleton
2. Runtime/model/prompt config schemas
3. Taxonomy schema + validation
4. Taxonomy rename/re-parent migrations
5. Prompt rendering + hashes
6. Screening event ledger + selected paper store
7. arXiv NEW ingestion + dedup
8. FAILED retry backlog
9. OpenRouter client + 4-model configuration
10. Structured filtering + semantic validation
11. Summary pass + summary retry/fallback
12. Markdown/JSON output generation
13. Static website
14. iPhone app: Today/Topics/Saved + Browse/Swipe triage + deep-read tracking + figure placeholder
15. Configurable schedule + GitHub Actions
16. Metrics, cost accounting, validation, full tests
17. Multi-day core soak test
18. **Figure extraction and hero-figure publication — FINAL TASK**
```

That order is authoritative.
