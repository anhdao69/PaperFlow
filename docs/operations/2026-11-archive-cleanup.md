# Oldest-month archive cleanup

Requested November 14, 2026: remove the oldest month to reduce storage.
The reviewed interval is August 21 through September 20 inclusive (cutoff
September 21), containing 3,931 of the 15,479 papers present before November
recovery. These papers own 55,969 figure files. Their removal reduces the
compressed canonical store from 41,307,166 to approximately 31,550,398 bytes
before adding the recovered November papers; figure bytes are measured on the
runner and reported separately.

`Prune oldest archive month` is manual and defaults to a read-only preview.
It must run after the November 12–13 recovery, under the same publication lock,
against the latest `main`. Dispatch with `apply=true` for the authorized cleanup.
The expected count of 3,931 prevents a changed deletion plan from being applied.
No new OpenRouter calls are made.

The cleanup removes old selected-paper records, their figure directories, old
daily JSON/Markdown/HTML, and dated run statistics. It rebuilds topics, feeds,
indexes, README, and website from the retained records. Successful zero-paper
days before the cutoff are removed too, so ordinary rebuilds cannot recreate the
old archive. Terminal screening history is retained to prevent old papers from
being ingested again. Publication state, configuration, recovery inputs, newer
records and their assets are preserved. Shared retained figure references and
symlinks block deletion. The CLI defaults to dry run and requires `--apply`.

The workflow validates the repository before and after cleanup and checks
protected paths for changes before its generated-file-only commit. A failed
cleanup is discarded with its runner; no partially changed checkout is pushed.
A successful cleanup triggers Pages deployment. Re-running an already applied
cleanup fails the expected-count check harmlessly.

This reduces the current checkout and deployment footprint. Previous Git commits
retain recoverable copies, so this operation does not purge GitHub history or
reduce all historical repository storage. No force-push or history rewrite is used.

## Queued execution without interrupting recovery

The one-off branch `maintenance/archive-cleanup-2026-11-14` runs this cleanup
through the already registered `recover-november.yml` workflow. On that branch
only, the workflow is named **Cleanup oldest month after November recovery**.
It shares the recovery's caller concurrency group, with cancellation disabled,
so it queues behind the entire active two-day recovery. Its cleanup job also
holds the daily publication lock. The date gate still requires successful state
through November 13 before any deletion.

The job checks out the reviewed cleanup code at its immutable dispatch SHA,
separately checks out the latest `main`, and runs the cleanup script using the
published application's dependencies. Only validated generated content is
committed to `main`. It explicitly dispatches Pages after the push. This avoids
pushing source changes into `main` while recovery is preparing its own commits.
The branch-only replacement of the recovery workflow is an execution wrapper;
do not merge that replacement over the normal November recovery workflow.
