# October 2026 publication recovery

The first October 7 workflow finished processing for publication October 6,
but its push was rejected because data/papers.json reached 100.48 MiB.
Later attempts failed at OpenRouter; the isolated diagnostic confirmed HTTP 402.
The user replenished credits and the same diagnostic subsequently passed.

Canonical papers are now serialized without formatting whitespace. No fields,
records, nulls, or Unicode content are removed. The previous 101,753,016-byte
store becomes 84,273,692 bytes before adding recovered papers. Normal Pydantic,
taxonomy, atomic-write and generated-output validation still apply.

## Historical inputs

Publication dates October 6,7,8 map to arXiv listing dates October 7,8,9,
consistent with the evening announcement and delayed original runs.

| Publication | Dated-list rows | Unique candidates | Input source |
|---|---:|---:|---|
| 2026-10-06 | 1149 | 837 | Dated lists + metadata fetched during recovery |
| 2026-10-07 | 1060 | 781 | Dated lists + metadata fetched during recovery |
| 2026-10-08 | 1082 | 794 | Preserved live RSS, including 1630 raw entries |

New and cross-listed papers are included. Replacements are retained in the
preserved RSS snapshot but excluded by the existing normalizer. Preserved RSS IDs retain their evidenced versions. Historical metadata is
fetched from the official OAI-PMH bulk service after Atom queries were rate
limited. The OAI arXiv format exposes latest metadata without a version number;
those reconstructed source IDs remain unversioned, rather than inventing v1.

The original failed runs did not archive their feeds. October 6's original log
reported 1234 candidates versus 837 in today's dated listing. Therefore this is
recovery of dated announcements, not an exact replay or proof of recovery of
every original candidate. October 7’s 781 and October 8’s 794 match their original
log counts. All five October 9 listing ID sets also match their RSS exactly.

The source archive and input manifest preserve full listing/RSS bytes,
checksums, per-category counts, exact dated IDs and announcement types.
The Atom preparation workflow runs with read-only repository access and no
OpenRouter secret; its failed attempt published nothing. Final reconstructed
inputs use the separately preserved OAI-PMH pages and exact-ID coverage audit.
Require successful preparation and validation of every snapshot before use;
a partial diagnostic artifact is not a successful preparation result.

## Execution gates

Choose the explicit recovery_date in PaperFlow Daily. --source-snapshot
requires scheduled semantics and validates the next due publication date,
announcement date, configured category order and candidate count before
publication changes. It never fetches current RSS during replay. Process and
verify October 6, then 7, then 8; do not bypass state by using --manual.

A failed run cannot publish generated content. Inputs are now uploaded as a
30-day Actions artifact even on failures. Canonical file size is checked before
commit, in addition to the existing full repository validation. Compact JSON
creates headroom for this recovery; long-term growth may eventually require a
separate sharding migration before reaching GitHub’s 100 MiB file limit again.
