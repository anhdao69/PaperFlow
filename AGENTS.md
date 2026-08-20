# PaperFlow Codex Instructions

## Source of truth

Read before implementing:

1. docs/specification/PaperFlow_Technical_Plan_v3_2.md
2. docs/ui/PaperFlow_UI_UX_SPEC.md
3. docs/ui/reference/\*.png

Priority when sources conflict:

1. Technical plan for data models, state semantics, pipeline behavior.
2. UI/UX spec for interaction and presentation.
3. PNG mockups only for visual reference.

Never invent functionality solely because it appears in a generated mockup.

## Development rules

- Work on one implementation phase at a time.
- Do not implement unrelated future features.
- Do not add dependencies unless they materially simplify the implementation.
- Run the smallest relevant test after each change.
- Run the broader test suite before completing a task.
- Never commit secrets.
- Never place OPENROUTER_API_KEY in iOS code.
- Keep public PaperFlow state separate from personal iPhone state.

## Python

- Python source lives under src/paperflow.
- Use typed Pydantic models.
- Prefer deterministic pure functions where possible.
- Network clients must be injectable/mockable.
- LLM calls must use the single OpenRouter abstraction.
- All outputs must validate before canonical files are committed.

Before completing Python work run:

pytest
ruff check .
python -m paperflow.cli.validate_taxonomy

## iOS

- SwiftUI.
- SwiftData for personal interaction state.
- Use async/await.
- Use dependency injection for public feed networking.
- No API secrets in the app.
- Public feed is read-only.
- One canonical personal state per versionless arXiv ID.
- Use reusable PaperFlow UI components.
- Use accessibility identifiers for important interactive controls.

After iOS changes:

- build the relevant scheme with xcodebuild
- run affected unit tests
- run affected UI test when interaction behavior changed
- capture a Simulator screenshot when UI changed

## UI

Permanent tabs are exactly:

- Today
- Topics
- Saved

Avoid:

- excessive dashboard density
- unsupported gamification
- tiny typography
- hard-coded taxonomy
- duplicate implementations of PaperDetail
- duplicate paper state

## Completion report

For every task report:

- files changed
- behavior implemented
- tests run
- exact result
- remaining known issues

## Secrets and credentials

Never print, log, cat, echo, serialize, commit, or include secret values
in reports.

The following variables may exist:

- OPENROUTER_API_KEY
- GH_TOKEN, if explicitly configured
- future App Store Connect credentials

Only check whether a credential exists, never display its value.

Never modify .env or secret stores unless the task explicitly requires it.

Never commit:

- .env
- \*.p8
- credentials
- API keys
- authorization headers
- signing certificates

GitHub repository authentication should use the already-authenticated
GitHub CLI whenever available.

Production OpenRouter credentials must be stored as GitHub Actions
repository secrets.
