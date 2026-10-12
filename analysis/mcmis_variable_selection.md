

\# MCMIS Variable Selection and Data Preparation Plan



\*\*Project:\*\* SEED2S + Reveal  

\*\*Analysis Period:\*\* 2015–2025  

\*\*Datasets:\*\* Company Census, Crash, Vehicle Inspection  

\*\*Status:\*\* Preliminary variable selection; pending CSV validation



\## 1. Research Objectives



The project aims to investigate commercial motor vehicle safety trends from 2015 through 2025.



Primary research questions:



1\. How have commercial motor vehicle crash trends changed over time?

2\. Are there seasonal or geographic patterns in reported crashes?

3\. How do weather, lighting, and road conditions relate to crashes?

4\. How do carrier characteristics, including fleet size and hazardous-materials operations, relate to crash records?

5\. How do inspection violations and out-of-service findings vary over time?



\## 2. Company Census Dataset



The Company Census dataset contains information about registered motor carriers.



\### Essential Variables



| Variable | Purpose |

|---|---|

| DOT\_NUMBER | Carrier identifier used to connect datasets |

| STATUS\_CODE | Active, inactive, or pending carrier status |

| CARRIER\_OPERATION | Interstate or intrastate operation |

| PHY\_STATE | Carrier's physical address state |

| FLEETSIZE | Carrier fleet-size category |

| POWER\_UNITS | Number of power units |

| TOTAL\_DRIVERS | Number of drivers |

| HM\_Ind | Hazardous-materials indicator |

| MCS150\_DATE | Date of MCS-150 registration update |



\### Optional Variables



| Variable | Purpose |

|---|---|

| CLASSDEF | Carrier classification |

| TRUCK\_UNITS | Number of truck units |

| MCS150\_MILEAGE | Reported annual mileage |

| MCS150\_MILEAGE\_YEAR | Year associated with reported mileage |

| SAFETY\_RATING | Satisfactory, conditional, or unsatisfactory rating |

| SAFETY\_RATING\_DATE | Date of safety rating |

| REVIEW\_DATE | Date of safety review |

| RECORDABLE\_CRASH\_RATE | Recorded crash rate |

| CRGO\_LIQGAS | Liquid/gas cargo indicator |

| CRGO\_CHEM | Chemical cargo indicator |



\### Data Quality Considerations



\- The full Census file previously analyzed contained 4,509,823 records.

\- SAFETY\_RATING was missing for approximately 94.76% of records.

\- RECORDABLE\_CRASH\_RATE was missing for approximately 79.20% of records.

\- Missing safety ratings should not automatically be interpreted as poor safety performance.

\- MCS150\_MILEAGE\_YEAR should be checked before using mileage as an exposure measure.

\- The September 2026 Census snapshot may not accurately represent carrier characteristics in earlier years.



\## 3. Crash Dataset



The Crash dataset contains records of reported commercial motor vehicle crashes.



\### Essential Variables



| Variable | Purpose |

|---|---|

| CRASH\_ID | Unique crash-file record identifier |

| REPORT\_NUMBER | Crash report identifier |

| REPORT\_SEQ\_NO | Vehicle sequence within a crash report |

| DOT\_NUMBER | Carrier identifier |

| REPORT\_DATE | Actual crash date |

| STATE | State where the crash occurred |

| COUNTY\_CODE | County where the crash occurred |

| WEATHER\_CONDITION\_ID | Weather at the time of the crash |

| ROAD\_SURFACE\_CONDITION\_ID | Road surface conditions |

| LIGHT\_CONDITION\_ID | Lighting conditions |

| TRUCK\_BUS\_IND | Truck or bus indicator |

| FATALITIES | Number of reported fatalities |

| INJURIES | Number of reported injuries |

| FEDERAL\_RECORDABLE | Federally recordable crash indicator |



\### Optional Variables



| Variable | Purpose |

|---|---|

| REPORT\_TIME | Time of crash |

| CARGO\_BODY\_TYPE\_ID | Vehicle cargo body type |

| VEHICLE\_HAZMAT\_PLACARD | Hazardous-materials placard indicator |

| HAZMAT\_RELEASED | Whether hazardous materials were released |

| VEHICLES\_IN\_ACCIDENT | Number of vehicles involved |

| TOW\_AWAY | Whether a vehicle was towed |

| STATE\_RECORDABLE | State-recordable crash indicator |



\### Data Quality Considerations



\- Filter by REPORT\_DATE for the 2015–2025 period.

\- Use STATE for crash geography rather than the carrier's PHY\_STATE.

\- Investigate multiple vehicle records associated with the same crash report.

\- Validate the appropriate unit of analysis before counting crashes or summing fatalities and injuries.

\- Examine missing and unknown weather or road-condition values.



\## 4. Vehicle Inspection Dataset



The Vehicle Inspection dataset contains roadside inspection and violation information.



\### Essential Variables



| Variable | Purpose |

|---|---|

| INSPECTION\_ID | Unique inspection identifier |

| DOT\_NUMBER | Carrier identifier |

| INSP\_DATE | Inspection date |

| REPORT\_STATE | State reporting the inspection |

| INSP\_LEVEL\_ID | Inspection level |

| VIOL\_TOTAL | Total violations |

| OOS\_TOTAL | Total out-of-service violations |

| DRIVER\_VIOL\_TOTAL | Driver violations |

| DRIVER\_OOS\_TOTAL | Driver out-of-service violations |

| VEHICLE\_VIOL\_TOTAL | Vehicle violations |

| VEHICLE\_OOS\_TOTAL | Vehicle out-of-service violations |



\### Optional Variables



| Variable | Purpose |

|---|---|

| REPORT\_NUMBER | Inspection report number |

| COUNTY\_CODE | Inspection county code |

| POST\_ACC\_IND | Post-accident inspection indicator |

| HAZMAT\_VIOL\_TOTAL | Hazardous-materials violations |

| HAZMAT\_OOS\_TOTAL | Hazardous-materials out-of-service violations |

| HAZMAT\_PLACARD\_REQ | Hazardous-materials placard requirement |

| CARGO\_TANK | Cargo tank indicator |



\### Data Quality Considerations



\- Filter by INSP\_DATE for the 2015–2025 period.

\- Check for duplicate inspection identifiers.

\- Distinguish inspections from individual violations.

\- Inspection REPORT\_NUMBER and Crash REPORT\_NUMBER represent different report systems.

\- Missing violation values should be distinguished from confirmed zero violations.



\## 5. Dataset Integration Strategy



The primary shared identifier is DOT\_NUMBER.



Proposed approach:



1\. Validate DOT\_NUMBER formats across datasets.

2\. Identify the unique-record level of each dataset.

3\. Aggregate crash and inspection data by carrier and relevant time period before joining when appropriate.

4\. Use left joins when retaining all crash or inspection records is important.

5\. Check unmatched carriers and duplicate keys.

6\. Verify row counts before and after merging to detect accidental many-to-many expansion.



Important limitation: Company Census is a September 2026 snapshot, while the project studies events from 2015–2025. Historical carrier characteristics cannot be assumed to match their 2026 values.



\## 6. Parquet Data Preparation Plan



1\. Confirm the actual CSV column names.

2\. Select only necessary fields using pandas usecols.

3\. Read large files in manageable chunks.

4\. Parse and validate date fields.

5\. Filter Crash and Inspection records to 2015–2025.

6\. Standardize DOT\_NUMBER and categorical fields.

7\. Check missingness, duplicates, and invalid values.

8\. Export cleaned, reduced datasets to Parquet.

9\. Compare output row counts with the filtered source records.

10\. Keep large CSV and Parquet files out of GitHub.



Proposed output files:



\- census\_selected.parquet

\- crashes\_2015\_2025.parquet

\- inspections\_2015\_2025.parquet



\## 7. Next Steps



\- Validate selected fields against the actual source CSV headers.

\- Confirm dataset coverage through 2025.

\- Coordinate preprocessing responsibilities with teammates.

\- Build a reusable Census Parquet preparation script.

\- Document missingness and data quality findings.

\- Prepare aggregated data for dashboard development.



