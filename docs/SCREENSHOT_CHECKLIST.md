# Screenshot checklist

The four Snapshot #1 PNGs below are present in `docs/images/`, were inspected as
operator-produced report artifacts, and are embedded in the root README. Their
presence documents the captured report content; it does not independently verify
every interactive control after later edits. Do not create placeholder or synthetic
screenshots.

| File | Page | Confirmed visible content | Still requires Desktop verification when recaptured |
| --- | --- | --- | --- |
| `olist-snapshot-1-overview.png` | Overview | Reconciled KPI cards, monthly summaries, separate exclusion cards/reasons, and order-level slicers | Slicer interaction and monthly-summary scope |
| `olist-snapshot-1-regions-sellers.png` | Regions & Sellers | Thresholded state/seller comparisons, the state scatter, and the 96,470 / 6.77% / 245.23 State Detail benchmark total | Local slicer behavior, sorting, and tooltip scope |
| `olist-snapshot-1-customer-experience.png` | Customer Experience | Review distribution, category comparison, and the 96,470 / 6,534 / 6.77% Category Detail benchmark total | Local category-slicer behavior and review-series colour retention |
| `olist-snapshot-1-data-quality.png` | Data Quality | Warning status, 0 failed checks, 3 warnings, snapshot ID 1, 446,802 source rows, exclusions, validation, and provenance | Fresh refresh against any replacement snapshot |

The visible page tabs do not establish that native page navigation works. Clear all
slicers also remains runtime-unverified.

## Before capture

- For a replacement capture, confirm the dashboard validation run belongs to the
  active dataset snapshot and repeat the relevant checks below.
- Confirm all critical checks and cross-engine reconciliations pass.
- Remove or crop server names, login names, local paths, connection dialogs,
  credentials, query histories, browser profiles, and unrelated applications.
- Use real report titles and the verified refresh date; do not annotate unverified
  values as final findings.
- Set a consistent desktop scale and report canvas size.

## Required captures for a replacement snapshot

Replace approved images under `docs/images/` using these exact filenames only after
they pass the privacy review. Update README captions if the page content or snapshot
changes.

1. `olist-snapshot-1-overview.png` — Overview: the seven headline KPI cards, both
   supporting exclusion cards, monthly
   rate/volume charts, and both reason breakdowns. Show that monthly charts are
   snapshot summaries and that the two exclusion cohorts are separate.
2. `olist-snapshot-1-regions-sellers.png` — Regions & Sellers: sorted state and
   seller late-rate comparisons, the visible
   30-order threshold, the state volume/duration scatter and detail table,
   local-slicer scope, and the non-additivity warning.
3. `olist-snapshot-1-customer-experience.png` — Customer Experience: review
   distribution, late/on-time comparison, sample sizes,
   missing-review indicator, local category-filter scope, and the
   descriptive-association subtitle.
4. `olist-snapshot-1-data-quality.png` — Data Quality: active snapshot ID,
   validation status, zero-or-more failed checks,
   warning count, source-row reconciliation, validation table, and provenance table.
   Preserve full hashes in the data/manifest even if the screenshot view scrolls
   horizontally.
5. Optional methods view: model relationships showing the single-direction Calendar
   relationship and disconnected summary tables.

## After capture

- Recheck every image for secrets, personal paths, notifications, and private data.
- Use descriptive filenames and alt text.
- Record which snapshot, validation run, export manifest, and code revision produced
  the images.
- Do not add or replace screenshots until the operator has reviewed both their
  values and their privacy boundary.
