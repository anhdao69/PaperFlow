# ADR-0001: Select PDFFigures2 for PaperFlow V1

- Status: accepted by product owner
- Date: 2026-08-21
- Scope: Phase 25/26 figure extraction

## Decision

PaperFlow V1 uses AllenAI PDFFigures2 as its only production figure extractor.
The source revision is pinned to
`3d7ad46753d4a315cccd1c2bcab398380e88c534` and runs as isolated JVM tooling.
Docling remains evaluation-only and is not installed in the daily production job.

## Evidence reviewed

A reproducible exploratory comparison used random seed `20260821` to select five
papers from the nine current KEEP papers assigned to World Action Models. Both
extractors processed the same PDFs.

| Extractor | Usable crops | Mean runtime/paper | Process failures |
|---|---:|---:|---:|
| PDFFigures2 | 39 figures + 14 tables | 6.5 seconds | 0/5 |
| Docling 2.121.0 | 39 picture-class crops | 59.6 seconds | 0/5 |

Matched crops were visually similar. PDFFigures2 also exported tables and was
about nine times faster. In one paper, Docling classified a table as a picture
and did not export the corresponding expected figure crop. Docling preserved
some mathematical caption symbols better, but that advantage did not outweigh
the coverage, runtime, and scholarly-layout advantages in this sample.

## Product-owner decision and evaluation limitation

The implementation plan originally requested a 50-paper human-labeled decision
gate. After reviewing the five-paper side-by-side output, the product owner
explicitly selected PDFFigures2 and directed implementation to continue. This
ADR records that override transparently; the five-paper pilot is not presented
as a statistically complete 50-paper benchmark.

## Consequences

- Hero selection is deterministic and uses extracted caption, crop size,
  aspect ratio, figure/table type, and page position.
- No extra LLM call is introduced for hero selection.
- All usable crops are published for the iPhone detail carousel.
- Extraction and image conversion remain non-blocking. A failure publishes the
  paper with `figure_status=failed`, no image URLs, and the normal placeholder.
- The daily workflow installs Java 17 and builds the pinned extractor outside
  the core Python dependency set.
