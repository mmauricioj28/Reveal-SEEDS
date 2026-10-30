\# FMCSA Integrated Dataset Documentation



\## Project Overview



This project integrates Federal Motor Carrier Safety Administration

(FMCSA) Census, Crash, and Inspection datasets to examine patterns

in commercial motor vehicle safety.



\## Data Files



| Dataset | Rows | Primary Key |

|---|---:|---|

| carriers.parquet | 4,509,823 | DOT\_NUMBER |

| carrier\_safety\_2016\_2025.parquet | 1,578,012 | DOT\_NUMBER + YEAR |

| crash\_carrier\_year.parquet | 749,386 | DOT\_NUMBER + YEAR |

| inspection\_carrier\_year.parquet | 967,321 | DOT\_NUMBER + YEAR |

| monthly\_activity.parquet | 7,699 | Monthly geographic aggregation |



\## Dataset Relationships



\- carriers.parquet contains carrier-level Census characteristics.

\- carrier\_safety\_2016\_2025.parquet contains integrated annual

&#x20; crash and inspection activity.

\- crash\_carrier\_year.parquet contains annual crash summaries.

\- inspection\_carrier\_year.parquet contains annual inspection summaries.

\- monthly\_activity.parquet contains monthly activity summaries

&#x20; and is not keyed by DOT\_NUMBER.



Carrier-level datasets use DOT\_NUMBER as their identifier.



Annual datasets use DOT\_NUMBER and YEAR together.



\## Validation Results



All primary-key validation checks passed.



\- Duplicate primary keys: 0

\- Missing DOT\_NUMBER values: 0

\- Crash carrier-years missing from integrated safety: 0

\- Inspection carrier-years missing from integrated safety: 0

\- Census-matched carrier-years: 1,574,666

\- Census-unmatched carrier-years: 3,346



The integrated carrier-year dataset contains 1,578,012 records.



\## Data Quality Considerations



\### Missing Carrier Identifiers



Some crash records do not contain usable carrier identifiers.



These records should remain in overall crash trend analyses

but cannot be included in comparisons involving Census

carrier characteristics.



\### Unmatched Carrier Records



Some records contain carrier identifiers that do not match

the Census dataset.



The integrated dataset identifies these records using

the census\_matched variable.



\### Historical Limitations



Census carrier characteristics represent a current snapshot

and may not accurately describe carriers in previous years.



\### Fleet Size



Some carriers have zero power units or unusually large

fleet-size values. These should be investigated before

interpreting fleet-size comparisons.



\### Inspection Coverage



Inspection data begins in October 2023, while crash data

covers 2016–2025. These periods should not be treated

as directly comparable without accounting for coverage.



\## Recommended Research Questions



1\. How do reported commercial motor vehicle crash counts

&#x20;  vary by year, month, and state from 2016 to 2025?



2\. How does the percentage of carriers with recorded

&#x20;  crashes or inspections vary across fleet-size categories?



\## Database Integration



The cleaned datasets are stored in Parquet format.



The group has not yet finalized its SQL database system.



The datasets can be imported into a relational database

after the group agrees on the database platform and schema.



\## Next Steps



\- Confirm the SQL database platform with the group.

\- Finalize shared table names and relationships.

\- Document unmatched and unidentified crash records.

\- Investigate unusual fleet-size values.

\- Prepare the final research dataset.

