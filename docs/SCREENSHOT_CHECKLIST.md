# Screenshot checklist

Capture screenshots only after SQL, Python, and Power BI reconciliation is complete.
Do not create placeholder or synthetic screenshots.

## Before capture

- Confirm the dashboard validation run belongs to the active dataset snapshot.
- Confirm all critical checks and cross-engine reconciliations pass.
- Remove or crop server names, login names, local paths, connection dialogs,
  credentials, query histories, browser profiles, and unrelated applications.
- Use real report titles and the verified refresh date; do not annotate unverified
  values as final findings.
- Set a consistent desktop scale and report canvas size.

## Required captures

1. Overview: the seven headline KPI cards, both supporting exclusion cards, monthly
   rate/volume charts, and both reason breakdowns. Show that monthly charts are
   snapshot summaries and that the two exclusion cohorts are separate.
2. Regions & Sellers: sorted state and seller late-rate comparisons, the visible
   30-order threshold, the state volume/duration scatter and detail table,
   local-slicer scope, and the non-additivity warning.
3. Customer Experience: review distribution, late/on-time comparison, sample sizes,
   missing-review indicator, local category-filter scope, and the
   descriptive-association subtitle.
4. Data Quality: active snapshot ID, validation status, zero-or-more failed checks,
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
- Do not commit screenshots until the operator has reviewed both their values and
  their privacy boundary.
