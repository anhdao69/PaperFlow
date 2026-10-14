# October 13 publication recovery

The October 14 jobs finished generation and validation for publication October 13,
but failed the pre-commit 100 MiB limit on data/papers.json. Latest failed run:
38547943592, job 115842133243. It generated 862 summaries with zero summary failures;
no new canonical state was pushed. Last committed date remains October 12.

Canonical selected-paper storage now switches to deterministic gzip at 90 MiB.
Readers accept legacy JSON and prefer papers.json.gz when present. Writers validate
and atomically install gzip before removing the legacy JSON. A compressed store
stays compressed. No records or fields are removed; public feed JSON is unchanged.
The GitHub size guard checks the resolved physical file. At 9,805 committed records,
99,152,079 bytes compress to 25,845,098 bytes, with identical decompressed bytes.
Compression is finite headroom; sharding may eventually be needed at greater scale.

Recovery snapshot recovery/2026-10-14/2026-10-13.json preserves all 4,560 raw entries
from artifact 11905927934, yielding exactly the logged 2,084 normalized candidates.
The snapshot records the original raw JSON checksum and originating run. It is
replayed with recovery_date=2026-10-13 on the updated daily workflow. A new dispatch
is required because rerunning the old workflow would retain its old JSON-only size
check. Date validation prevents replay after October 13 is committed.
