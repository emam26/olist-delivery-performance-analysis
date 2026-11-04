# Findings

## Status

**No empirical findings are verified yet.**

This file is intentionally a publication template. Populate it only after the
source inventory, SQL load, SQL validation, independent metric reconciliation, and
Power BI reconciliation have all passed using recorded evidence.

## Required provenance

- Analysis date (UTC): `NOT RUN`
- Source file hashes: `NOT RECORDED`
- Active dataset snapshot/manifest hash: `NOT RECORDED`
- Mapped successful load-batch IDs: `NOT RECORDED`
- SQL validation run ID: `NOT RECORDED`
- Independent metric validation artifact: `NOT CREATED`
- Dashboard export manifest or Power BI refresh: `NOT CREATED`
- Code/Git revision recorded by operator: `NOT RECORDED`

## Population and exclusions

Record:

- all canonical orders;
- delivery-eligible and excluded orders;
- duration-eligible and excluded orders;
- exclusion reasons;
- reviewed and unreviewed orders;
- date coverage;
- material duplicate, orphan, timestamp, and missingness findings.

Do not report percentages without their denominators.

## Overall delivery performance

Record on-time and late counts/rates, average duration, median duration, P90, P95,
and days early/late. Include reconciliation evidence and uncertainty where relevant.

## Variation over time and geography

Describe verified purchase-month and customer-state patterns. Distinguish stable
patterns from sparse or uncertain estimates and avoid interpreting temporal
co-movement as a causal mechanism.

## Seller and category attribution

Report only groups meeting the documented minimum denominator. State that
multi-seller and multi-category order attributions are not additive to the global
order total. Avoid ranking claims that are sensitive to a few observations.

## Reviews

Describe the observed association between selected review score and delivery
outcomes. Do not write that delivery timing caused a score difference. Discuss
review-selection effects and plausible confounding.

## Limitations

At minimum discuss historical scope, dataset selection, missingness, source
duplication, attribution, review selection, unmeasured confounding, and external
validity.

## Conclusion

Conclusions must be bounded by the validated population and methods above. If any
critical quality or reconciliation check fails, report the failure instead of a
substantive conclusion.
