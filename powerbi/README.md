# Power BI handoff

This directory contains an editable PBIP/PBIR project, TMDL semantic-model sources,
and a reproducible dashboard specification. The checked-in `.pbix`, if present, is
a separate local deliverable and is not the source of truth. Power BI Desktop is
still required to refresh and visually validate the report.

Use the SQL Server reporting views directly when the operator can reach SQL Server.
The supported offline alternative is to import the CSV files created by
`scripts/export_dashboard_data.py`; the export manifest records row counts and
SHA-256 hashes plus active snapshot and validation provenance. Export is refused
when the active snapshot has no completed Passed or Warning validation run.

The saved project uses enhanced PBIR (`definition.pbir` plus `Report/definition/*.json`)
and TMDL (`SemanticModel/definition/*.tmdl`). The semantic model contains the
order-level table plus disconnected imported reporting tables for monthly, state,
seller, category, review, validation, and provenance exports. Aggregate tables are
deliberately not related to `order_delivery` because their grains are not additive.
The State Detail and Category Detail table Total rows therefore use explicit
order-level benchmarks rather than sums of visible summary rows. On snapshot #1,
those benchmarks are 96,470 eligible orders, 6,534 late orders, 6.77% late rate,
and 245.23 median delivery hours where applicable. Category and seller rows remain
attributed, non-additive comparisons.

Read these files in order:

1. `data_model.md` — tables, grains, and relationship constraints.
2. `measures.dax` — denominator-safe measures and a calendar table definition.
3. `dashboard_specification.md` — page-level visual and interaction design.
4. `reconciliation.md` — checks required before publishing or taking screenshots.

Build in that order. The PBIP source contains machine-specific paths for the eight
CSV partitions. Create or select one complete local export directory with the
documented export command before refreshing; the CSVs and manifest are ignored
artifacts and must not be committed. If the repository is opened on another machine,
update all eight partition paths to that one immutable directory before refreshing.

The four PBIR pages are **Overview**, **Regions & Sellers**, **Customer
Experience**, and **Data Quality**. The project operator reports that snapshot #1
opened, refreshed, and rendered in Desktop, and that the State Detail and Category
Detail global benchmark totals were verified. Reopen the project after any source
or model change, refresh the local partitions, import `Olist_Delivery_Theme.json`
if needed, and complete the visual-level sample-size, local-slicer, color, and
tooltip checks in `reconciliation.md` before taking screenshots. Navigation and
clear-slicer controls are not currently a verified project capability: the prior
source-authored candidates opened but failed runtime testing and are not checked in.
If needed, create and validate a native **Page navigator** and **Clear all slicers**
button on Overview in Desktop, save and close the project, then inspect the
generated PBIR files before replicating verified definitions to other pages. A
clear-slicer button clears only current-page slicer selections; it does not clear
Filters-pane filters, chart selections, or disconnected summaries. Data Quality has
no slicer and needs no clearing control. Full page resets remain Desktop-only: save
one default-state bookmark per page with **Data** and **Current page** enabled, then
attach a blank button's action to the matching bookmark. Do not use one reset
bookmark across disconnected page scopes.

The operator supplied Snapshot #1 evidence of refresh/render, reconciled Overview
KPIs, State/Category benchmark totals, and four page screenshots under
`docs/images/`. Those artifacts do not replace the manual-runbook checks after any
data, model, or visual change, and they do not verify navigation or clear-slicer
interactions.
