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

Read these files in order:

1. `data_model.md` — tables, grains, and relationship constraints.
2. `measures.dax` — denominator-safe measures and a calendar table definition.
3. `dashboard_specification.md` — page-level visual and interaction design.
4. `reconciliation.md` — checks required before publishing or taking screenshots.

Build in that order. The PBIP source points to
`F:\olist-delivery-performance-analysis\reports\exports\olist_snapshot_1\` for
the eight CSV partitions. Generate that directory locally with the documented
export command before refreshing; the CSVs and manifest are ignored artifacts and
must not be committed. If the repository is opened on another machine, update the
eight partition paths to that machine's one immutable export directory.

The four PBIR pages are **Overview**, **Regions & Sellers**, **Customer
Experience**, and **Data Quality**. The project operator reports that snapshot #1
opened, refreshed, and rendered in Desktop. Reopen the project after any source
change, refresh the local partitions, import `Olist_Delivery_Theme.json` if the
theme is not already applied, and complete the visual-level sample-size,
local-slicer, color, and tooltip checks in `reconciliation.md` before taking
screenshots. The native page tabs are the checked-in navigation. If a persistent
navigator is wanted, create it in Desktop with **Insert > Buttons > Navigator >
Page navigator**, format it with the checked-in theme, copy it to each page, and
test all four destinations. The source has no generated action/bookmark contract,
so create a reset control in Desktop: save one default-state bookmark per page with
**Data** and **Current page** enabled, then attach a blank button's action to the
matching bookmark. Do not use one reset bookmark across disconnected page scopes.

No dashboard result, screenshot, or performance claim is verified until the manual
runbook checks have been completed against the operator's local data.
