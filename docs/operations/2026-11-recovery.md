# November 12–13 recovery

The last committed publication is November 11. Runs 43430745116 (November 13)
and 43593543835 (November 14) failed at the first filter batch with OpenRouter
HTTP 402. A fresh one-request diagnostic, run 43607862533 on November 14,
also returned 402. The latest daily runner had 69 GB free; storage is not the
current blocker. Check the OpenRouter account balance and the spending limit on
the key stored as `OPENROUTER_API_KEY`. Do not bypass the provider error or advance
publication state without a successful, validated pipeline run.

## Preserved source inputs

| Publication date | RSS capture date | Original run | Artifact | Raw entries | Normalized candidates |
| --- | --- | --- | --- | ---: | ---: |
| 2026-11-12 | 2026-11-13 | 43430745116 | 14039339085 | 1,875 | 824 |
| 2026-11-13 | 2026-11-14 | 43593543835 | 14113263108 | 0 | 0 |

The snapshots in `recovery/2026-11-14/` retain every original raw entry, including
order and cross-listings. Each records the original raw JSON and artifact ZIP
SHA-256, run, job, artifact, member name, and capture timestamp (run start).
Configured source categories are preserved in their configured order.

The November 14 job was still *scheduled* for November 12 because earlier runs
had failed, but it fetched the *current* RSS feeds. Replaying those empty inputs
for November 12 would discard that day's 824 candidates. They are instead
reserved for November 13. The empty November 14 capture matches arXiv's
[announcement schedule](https://info.arxiv.org/help/availability.html): papers
are announced Sunday through Thursday evenings, with none on Friday or Saturday.
`announcement_date` in the recovery schema denotes the following RSS capture day.
An empty source does not bypass retry-backlog processing or imply an empty
published feed.

## Execution and verification

Dispatch **Recover November 12-13** on `main` after OpenRouter access is restored.
Its preflight sends one small structured-output request through the existing
OpenRouter client before either publication job starts. A 402 stops the chain
without building PDFFigures2 or changing generated state. A successful preflight
does not guarantee enough credit for the full batch.

The jobs then replay November 12 and November 13 sequentially, checking out the
latest `main` and using the existing publication lock, source/date validation,
output validation, and generated-file commit allowlist. Ordinary runs are blocked
while either date is pending, so current RSS cannot replace the preserved inputs.
After both dates succeed, normal scheduling resumes and the recovery workflow's
successful completion triggers Pages deployment.

If November 12 succeeds but November 13 fails, use **Re-run failed jobs** on that
recovery run, or dispatch PaperFlow Daily with `recovery_date=2026-11-13` and
`catch_up=true`. Do not start the two-date chain again after November 12 is
committed: the snapshot date check intentionally rejects a duplicate replay.

Validation before dispatch: verify artifact ZIP checksums and exact raw-entry
equality; load both dated snapshots through the production validator; test the
existing recovery and full pipeline contracts; check workflow YAML, dependencies,
date reservations, and schedule consistency. Final completion requires committed
state through November 13 and a successful Pages deployment.
