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

1. Delivery overview: delivered/eligible cards, rates, duration cards, monthly trend,
   duration distribution, and visible exclusion context.
2. Regions and sellers: state comparison, seller sample-size threshold, seller table
   or scatter, and the non-additivity warning.
3. Customer reviews: review distribution, late/on-time comparison, sample sizes,
   missing-review indicator, and descriptive-association subtitle.
4. Data quality: active snapshot ID, validation run/status, validation table, source
   row reconciliation, and hashes truncated only for display (retain full values in
   the manifest).
5. Optional methods view: model relationships showing the single-direction Calendar
   relationship and disconnected summary tables.

## After capture

- Recheck every image for secrets, personal paths, notifications, and private data.
- Use descriptive filenames and alt text.
- Record which snapshot, validation run, export manifest, and code revision produced
  the images.
- Do not commit screenshots until the operator has reviewed both their values and
  their privacy boundary.
