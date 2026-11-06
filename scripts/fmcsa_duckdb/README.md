\# FMCSA DuckDB Analytics Database



\## Overview



This module creates and validates a local DuckDB database using integrated FMCSA Census, Crash, and Inspection datasets.



The database supports SQL-based exploratory analysis and preparation of dashboard-ready summaries.



\*\*Data snapshot:\*\* October 24, 2026  

\*\*Analysis period:\*\* 2016–2025



\## Database Tables



| Table | Rows | Description |

|---|---:|---|

| `carriers` | 4,509,823 | Carrier characteristics from the Census snapshot |

| `carrier\_safety\_2016\_2025` | 1,578,012 | Integrated carrier-year safety summaries |

| `crash\_carrier\_year` | 749,386 | Annual crash summaries by carrier |

| `inspection\_carrier\_year` | 967,321 | Annual inspection summaries by carrier |

| `monthly\_activity` | 7,699 | Monthly event counts by source and state |



Total: 7,812,241 rows across five tables.



\## Scripts



\- `create\_duckdb.py`: Creates the DuckDB database from integrated Parquet files.

\- `validate\_duckdb.py`: Checks row counts, carrier identifiers, unique keys, and carrier-year relationships.

\- `create\_views.py`: Creates SQL views for dashboard analysis.



\## Setup



Install DuckDB:



```bash

python -m pip install duckdb

```



Set the `FMCSA\_DATA\_DIR` environment variable to the folder containing the integration outputs.



Example for Windows Command Prompt:



```cmd

set "FMCSA\_DATA\_DIR=C:\\path\\to\\Reveal-SEEDS-integration"

```



The expected Parquet files are located under:



`outputs/full\_integration\_20261024/`



Run the scripts from the repository root:



```cmd

python scripts\\fmcsa\_duckdb\\create\_duckdb.py

python scripts\\fmcsa\_duckdb\\validate\_duckdb.py

python scripts\\fmcsa\_duckdb\\create\_views.py

```



The resulting `fmcsa.duckdb` database is stored in the configured data directory.



\## Dashboard Views



\*\*`dashboard\_annual\_crashes`\*\*



Provides annual crash counts from carrier-linked crash records.



\*\*`dashboard\_fleet\_size`\*\*



Summarizes crash and inspection counts by current carrier fleet size among Census-matched carrier-years.



\## Validation Results



All implemented validation checks passed for the October 24 snapshot:



\- Expected row counts matched.

\- No duplicate carrier or carrier-year keys.

\- No missing `DOT\_NUMBER` values in the four carrier-level tables.

\- Every crash and inspection carrier-year key was present in the integrated carrier-year table.



\## Limitations



\- The October 24 integration snapshot may differ from newer team datasets.

\- Carrier characteristics reflect the available Census snapshot, not necessarily historical characteristics.

\- Annual crash summaries based on carrier-linked records do not represent all retained crash records.

\- Counts by fleet size are descriptive, not exposure-adjusted crash or inspection rates.

\- Inspection reporting coverage varies across the available source data.

\- Database files and raw datasets are maintained separately from the scripts and should not be committed to GitHub without team agreement.

