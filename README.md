# 📦 Olist Delivery Performance Analysis

> Understanding delivery times, late orders, and customer reviews with SQL, Python, and Power BI.

![Status: Design stage](https://img.shields.io/badge/status-design%20stage-yellow)
![Python](https://img.shields.io/badge/language-Python-3776AB?logo=python&logoColor=white)
![SQL Server](https://img.shields.io/badge/database-SQL%20Server-CC2927)
![Power BI](https://img.shields.io/badge/dashboard-Power%20BI-F2C811)

The project addresses a practical question: **where do delivery delays appear in Olist's historical orders, and how do those orders compare with on-time deliveries?** The planned analysis uses SQL and Python to prepare the data and Power BI to present the findings.

> [!NOTE]
> This repository currently documents the analysis plan. Implementation has not started.
> No findings, dashboard screenshots, or performance results are claimed yet.

## Purpose

The project is intended to help an analyst answer practical delivery questions: how often orders arrive after the estimated date, how delivery times vary across groups, and whether late orders are associated with different customer review scores.

It is a historical portfolio analysis, not work commissioned by Olist. The findings will describe the supplied data rather than current business performance.

## Data source

The source is the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), published by Olist on Kaggle. The publisher describes approximately 100,000 orders from 2016 to 2018.

Download the files from that source and retain its attribution and license information. Raw dataset files will not be bundled into the repository. The implementation will document its input filenames, file hashes, and loaded row counts so the analysis can be reproduced.

The planned inputs are orders, order items, customers, sellers, products, and reviews. Payment data is optional and is not required to answer the delivery questions.

## Questions to answer

- What share of delivered orders arrived on or before the estimated delivery date?
- What are the median and slower-end delivery times?
- How do delivery patterns vary by month and customer state?
- Which sellers or product categories have higher late-delivery rates, with enough orders for a useful comparison?
- How do review-score distributions differ between on-time and late deliveries?
- How many records are excluded from each metric, and why?

The analysis will report group sizes beside rates. Small groups will not be ranked as though they provide equally reliable evidence.

## Planned workflow

1. Download and inventory the original CSV files.
2. Load them into SQL Server staging tables without silently discarding rows.
3. Use Python and SQL to examine keys, missing values, timestamps, and unmatched references.
4. Create documented analytical tables and views at explicit grains.
5. Calculate delivery metrics in SQL and reconcile their totals.
6. Build Power BI pages from the analytical views.
7. Publish the findings, exclusions, and limitations alongside the queries.

The core tools will be Microsoft SQL Server, T-SQL, Python, pandas, Power BI, and Git. Additional infrastructure will be added only if it serves a clear need.

## Proposed analytical model

| Table or view | Grain and purpose |
| --- | --- |
| Staging tables | Preserve the input records and loading provenance. |
| Order delivery table | One row per order, with delivery eligibility and derived durations. |
| Order-item table | One row per source order item. |
| Order-seller bridge | One row per distinct order and seller, for seller-level delivery comparisons. |
| Order-category bridge | One row per distinct order and category, if category comparisons are included. |
| Order-review view | At most one review record per order under a documented selection rule. |
| Reporting views | Monthly, regional, seller, and review summaries. |

Customer records will be joined using the order's customer key. The dataset's unique-customer identifier can support repeat-customer analysis later, but will not replace the order-specific join key.

Order items and reviews can multiply rows when joined directly to orders. The order-level delivery table will remain the basis of overall order counts. Seller and category summaries will document their separate grains and will not be summed to invent a global order total.

## Metric definitions

| Metric | Planned definition |
| --- | --- |
| Eligible delivered order | An order marked delivered with valid actual and estimated delivery dates. |
| Late order | Actual delivery calendar date is after the estimated delivery calendar date. |
| On-time delivery rate | Eligible orders delivered on or before their estimated date divided by all eligible orders. |
| Purchase-to-delivery time | Elapsed time between purchase and actual customer delivery for valid, nonnegative intervals. |
| Days late | Positive calendar-date difference between actual and estimated delivery, calculated for late orders. |
| Review comparison | Review-score distributions for on-time and late orders with usable review data. |

Calendar dates will be used for late/on-time classification so a delivery later on the estimated day is not counted as a full late day. Elapsed delivery duration will be calculated separately.

Canceled, unavailable, undelivered, and incomplete orders will be reported separately rather than treated as zero-day deliveries. Missing dates and invalid intervals will have explicit exclusion reasons. Source timestamps without timezone information will not be labeled UTC.

If multiple reviews exist for one order, the analysis will first inspect them and document a deterministic selection rule. It will not assume the relationship is one-to-one.

## Planned Power BI pages

- **Delivery overview:** eligible orders, on-time rate, delivery-time distribution, and monthly patterns.
- **Seller and regional comparisons:** group sizes, late-delivery rates, and delivery times.
- **Customer reviews:** review distributions alongside delivery outcomes.
- **Data quality:** missing fields, exclusions, unmatched records, and reconciliation totals.

## Validation and completion evidence

Before publishing findings, the project should demonstrate that:

- Input and staging counts reconcile.
- Keys are unique at each declared grain, or exceptions are explained.
- Joins do not inflate the overall order count.
- Every excluded order has an understandable reason.
- SQL results agree with independently checked sample calculations.
- Power BI totals agree with the underlying reporting views.
- A fresh run can reproduce the published outputs from the documented input files.

## Interpretation limits

A late order may contain items from multiple sellers. An order-level delivery timestamp does not establish which seller or carrier caused a delay.

Differences between groups and associations with review scores will be described without causal claims. No business adoption, cost saving, or improvement in delivery performance is currently established.

## Current setup

No runnable analysis or dashboard has been published yet. The first implementation step is to inventory the downloaded source files and create the staging load. Exact setup instructions and a findings section will be added when the corresponding work has been completed.
