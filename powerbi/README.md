# Power BI handoff

This directory contains a reproducible dashboard specification, not a generated
`.pbix` file. Power BI Desktop work remains a manual step because the project does
not automate or claim to verify desktop UI operations.

Use the SQL Server reporting views directly when the operator can reach SQL Server.
The supported offline alternative is to import the CSV files created by
`scripts/export_dashboard_data.py`; the export manifest records row counts and
SHA-256 hashes for reconciliation.

Read these files in order:

1. `data_model.md` — tables, grains, and relationship constraints.
2. `measures.dax` — denominator-safe measures and a calendar table definition.
3. `dashboard_specification.md` — page-level visual and interaction design.
4. `reconciliation.md` — checks required before publishing or taking screenshots.

No dashboard result, screenshot, or performance claim is verified until the manual
runbook checks have been completed against the operator's local data.
