
# FMCSA DuckDB Analytics Database

## Overview

This module creates, validates, and prepares a local DuckDB database using integrated FMCSA Census, Crash, and Inspection datasets.

The database supports SQL-based exploratory data analysis, research questions, and dashboard development using tools such as Tableau.

**Data snapshot:** October 24, 2026  
**Analysis period:** 2016–2025

## Database Tables

| Table | Rows | Description |
|---|---:|---|
| `carriers` | 4,509,823 | Carrier characteristics from the FMCSA Census snapshot |
| `carrier_safety_2016_2025` | 1,578,012 | Integrated carrier-year crash and inspection summaries |
| `crash_carrier_year` | 749,386 | Annual crash summaries by carrier |
| `inspection_carrier_year` | 967,321 | Annual inspection summaries by carrier |
| `monthly_activity` | 7,699 | Monthly event counts by source and state |

**Total:** 7,812,241 rows across five tables.

## Database Structure

The primary linking identifier is `DOT_NUMBER`, the USDOT number assigned to motor carriers.

- `carriers`: One record per `DOT_NUMBER`.
- `carrier_safety_2016_2025`: One record per `DOT_NUMBER` and `YEAR`.
- `crash_carrier_year`: One record per `DOT_NUMBER` and `YEAR`.
- `inspection_carrier_year`: One record per `DOT_NUMBER` and `YEAR`.
- `monthly_activity`: Aggregated monthly event counts by source and geographic fields.

Carrier-level crash and inspection summaries are connected through `DOT_NUMBER` and `YEAR`.

The monthly activity table supports event-level trend summaries but does not contain a carrier-level linking key.

## Python Scripts

### create_duckdb.py

Creates a local DuckDB database from the integrated Parquet datasets.

The script loads all five tables and prints their record counts.

### validate_duckdb.py

Validates database integrity by checking:

- Expected table row counts
- Duplicate carrier and carrier-year keys
- Missing DOT numbers
- Relationships between crash, inspection, and integrated carrier-year tables

All implemented validation checks passed for the October 24 snapshot.

### create_views.py

Creates six SQL views for research analysis and dashboard development.

## Dashboard SQL Views

### 1. dashboard_annual_crashes

Provides annual crash counts from carrier-linked records for 2016–2025.

Supports analysis of changes in recorded crash activity over time.

### 2. dashboard_monthly_crashes

Provides monthly retained crash counts across all available match statuses.

Contains 120 monthly observations covering January 2016 through December 2025.

Supports analysis of monthly trends and potential seasonal patterns.

### 3. dashboard_crashes_by_state

Aggregates retained crash records by the state where the crash occurred.

Supports geographic comparisons and state-level Tableau visualizations.

### 4. dashboard_inspections_by_state

Aggregates retained inspection records by reporting state.

Supports geographic comparisons of inspection activity.

### 5. dashboard_fleet_size

Summarizes crash and inspection counts across fleet-size categories among Census-matched carrier-years.

Fleet-size categories:

- 0 power units
- 1 power unit
- 2–5 power units
- 6–20 power units
- 21–100 power units
- 101+ power units
- Missing fleet-size information

Supports descriptive comparisons of crash and inspection activity by current carrier size.

### 6. dashboard_carrier_operation

Summarizes crash and inspection counts by carrier operation category among Census-matched carrier-years.

Supports comparisons across carrier operation classifications.

## October 24 Snapshot Results

| Metric | Count |
|---|---:|
| Retained crash records | 1,868,397 |
| Carrier-linked crash records | 1,466,869 |
| Retained inspection records | 5,895,908 |
| Monthly crash observations | 120 |
| Crash state categories | 56 |
| Inspection reporting-state categories | 57 |
| Fleet-size categories | 7 |
| Carrier operation categories | 4 |

The difference between retained and carrier-linked crash totals reflects records that are not included in the carrier-year aggregation.

These totals are specific to the October 24 integration snapshot and should not be mixed with results from newer team datasets without reconciliation.

## Research Questions

The database supports the following research questions:

**RQ1: Temporal Patterns**

How do commercial motor vehicle crash and inspection records vary over time?

The monthly crash view also supports exploratory analysis of seasonal crash patterns.

**RQ2: Geographic Distribution**

How are crash and inspection records distributed across states?

**RQ3: Carrier Characteristics**

Among Census-matched carriers, how do crash and inspection counts differ by current fleet size and carrier operation?

## Setup Instructions

### 1. Install Dependencies

Python and the DuckDB package are required.

```bash
python -m pip install duckdb
```

### 2. Configure the Data Directory

Set the `FMCSA_DATA_DIR` environment variable to the directory containing the integrated Parquet outputs.

Example using Windows Command Prompt:

```cmd
set "FMCSA_DATA_DIR=C:\path\to\Reveal-SEEDS-integration"
```

The expected input files are located in:

```text
outputs/full_integration_20261024/
```

Required files:

- `carriers.parquet`
- `carrier_safety_2016_2025.parquet`
- `crash_carrier_year.parquet`
- `inspection_carrier_year.parquet`
- `monthly_activity.parquet`

### 3. Create the Database

From the repository root, run:

```cmd
python scripts\fmcsa_duckdb\create_duckdb.py
```

The script creates `fmcsa.duckdb` in the configured data directory.

### 4. Validate the Database

```cmd
python scripts\fmcsa_duckdb\validate_duckdb.py
```

Successful execution should end with:

```text
ALL DATABASE VALIDATION CHECKS PASSED
```

### 5. Create Dashboard Views

```cmd
python scripts\fmcsa_duckdb\create_views.py
```

This creates six SQL views and displays row counts, source labels, and selected record totals.

## Tableau Integration

The SQL views are designed to support future Tableau dashboard development.

Potential visualizations include:

1. Monthly crash trends and seasonal comparisons
2. State-level crash and inspection maps
3. Fleet-size comparisons using grouped bar charts
4. Carrier operation comparisons

These visualizations should distinguish retained event counts from carrier-linked or Census-matched counts.

Tableau integration and published dashboards are not included in this module.

## Data Limitations

- The October 24 snapshot may differ from newer team integration outputs.
- Carrier characteristics reflect the available Census snapshot rather than historical carrier characteristics.
- Retained crash records include events that may not be linkable to Census carriers.
- Carrier-linked and Census-matched analyses have different inclusion criteria.
- Inspection data coverage is not necessarily complete for every month from 2016 through 2025.
- Raw crash and inspection counts do not account for differences in fleet size, mileage, traffic exposure, or reporting practices.
- Geographic counts reflect recorded activity and should not be interpreted as direct measures of road safety or crash risk.
- Seasonal patterns are descriptive and do not establish weather-related causation.
- FARS data lacks a straightforward USDOT identifier for direct carrier-level linkage and would require a separate integration strategy.

## Reproducibility and GitHub

The repository contains Python scripts and documentation needed to reproduce the database using the specified October 24 Parquet inputs.

The local DuckDB database and large source datasets are stored separately and are not included in this module.

Before using the database for a shared dashboard, the team should agree on the final integration snapshot and reconcile any differences between dataset versions.

## Project

**Program:** SEED2S+X Reveal Scholars  
**Project:** FMCSA Motor Carrier Safety Data Integration and Analysis  
**Repository:** https://github.com/mmauricioj28/Reveal-SEEDS
