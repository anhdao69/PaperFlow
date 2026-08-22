# Phase 25 figure extractor evaluation status

Date: 2026-08-20

Status: **SUPERSEDED on 2026-08-21**

This historical checkpoint was resolved when the product owner selected
PDFFigures2. The accepted production decision is recorded in
`ADR-0001-figure-extractor.md` and
`../IMPLEMENTATION_DECISIONS_v1.md#d-006--pdffigures2-is-the-v1-extractor`.
The blocked status below describes only the state on 2026-08-20.

## Decision

PaperFlow does not yet select PDFFigures2 or Docling as its production
extractor. Phase 26 must not start until the Phase 25 evidence gate is met.

This is intentionally not a preference-based architecture decision. The
required comparative evidence does not exist in the repository:

- `tests/fixtures/figures/evaluation_labels.json` is explicitly marked
  `human_reviewed=false` and contains no paper labels.
- `cache/pdf/` contains no evaluation PDFs.
- `data/papers.json` contains no KEEP papers from which to assemble the
  required representative corpus.
- PDFFigures2/JVM and Docling are not installed in isolated project tooling.

## Infrastructure completed

The repository now has:

- strict extractor-neutral metadata and corpus models;
- injectable PDFFigures2 and Docling CLI adapters;
- normalized process, timeout, missing-input, invalid-metadata, and invalid-image
  failures;
- top-left, 72-DPI PDF bounding-box normalization;
- deterministic matching and aggregation for detection recall, crop
  correctness, caption correctness, hero top-1 accuracy, runtime, and failure
  rate;
- a release-corpus validator requiring 50 papers, every specified layout
  class, human review, present PDFs, and exact PDF SHA-256 hashes;
- deterministic adapter and evaluation tests that do not invoke either real
  extractor or any network service.

The neutral Phase 25 top-choice baseline ranks non-table figures before tables,
then ranks by descending region area, page, and stable figure ID. This baseline
is applied equally to both candidates; Phase 26's final PaperFlow-specific hero
scoring is a separate gate.

## Evidence still required

Before this status can become an accepted decision:

1. Assemble at least 50 real representative KEEP PDFs in gitignored
   `cache/pdf/`.
2. Have a human review every PDF and record all evaluation labels plus one
   desired hero in `evaluation_labels.json`.
3. Cover single-column, two-column, multi-panel, vector-diagram, raster,
   full-width, table-near-figure, and long-caption cases.
4. Install both optional tools inside project-isolated tooling and record exact
   versions.
5. Run both adapters over the identical hashed corpus.
6. Review every crop, caption association, and top choice.
7. Commit the complete aggregate/per-paper results and replace this status with
   a measured decision naming the selected default and deployment rationale.

## Candidate integration contracts

The PDFFigures2 adapter follows the official batch CLI and its zero-based page,
top-left 72-DPI region, caption, type, and rendered-image output contract:

<https://github.com/allenai/pdffigures2>

The Docling adapter follows the current `docling convert` CLI with JSON output,
referenced image export, CPU execution, and `DoclingDocument` picture/table
provenance:

<https://github.com/docling-project/docling/blob/main/docs/reference/cli.md>

<https://github.com/docling-project/docling/blob/main/docs/concepts/docling_document.md>
