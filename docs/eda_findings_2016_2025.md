# Exploratory findings, executed extract

These statements describe the run in
[full_dataset_validation.md](full_dataset_validation.md). Counts are retained
records. They are not crash rates, and they are not evidence that one group is
safer than another. Carrier attributes come from the current Company Census
snapshot and may have differed in the year of a historical event.

Tables: [eda_2016_2025](eda_2016_2025/). Charts: [figures/weeks5_6](figures/weeks5_6/).

## What the extract can support

Crash records in this download run from 2016-01-01 through 2025-12-31, and every
month in that span has at least one retained row. The inspection download's
earliest retained date is 2023-10-30, even though the portal query asked for
2016–2025. Inspection months before October 2023 are unobserved. They are not
zeros. October 2023 itself is a partial month (17,411 records, against 196,703
in November 2023).

The crash file has 1,868,953 rows and no duplicate `CRASH_ID`. Counts below are
crash records in this extract, not vehicle involvements from a different file
and not unique roadway incidents established from a police report.

## Q1. How do retained crash and inspection records vary by year and month?

Crash records by year, including every match status:

| Year | Retained crash records | Change from prior full year |
| ---: | ---: | ---: |
| 2016 | 178,161 | — |
| 2017 | 182,828 | 2.62% |
| 2018 | 196,568 | 7.52% |
| 2019 | 194,804 | −0.90% |
| 2020 | 167,613 | −13.96% |
| 2021 | 197,959 | 18.10% |
| 2022 | 199,395 | 0.73% |
| 2023 | 187,337 | −6.05% |
| 2024 | 186,191 | −0.61% |
| 2025 | 178,097 | −4.35% |

2020 has fewer retained crash records than 2019, and 2021 has more than 2020.
Those are changes in record counts. Traffic volume, reporting, and enforcement
are all possible explanations. This is not a finding about crash risk.

Across the ten crash years, mean records per calendar day are lowest in April
(470.85) and highest in October (561.34). The gap is modest. It is an average
of observed years, divided by calendar days, not by miles. See
`month_of_year.csv` and `month_of_year.png`.

Inspection records are 398,201 in 2023, 2,602,827 in 2024, and 2,851,045 in 2025.
No year-over-year figure is reported from 2023 to 2024, because 2023 does not
have 12 observed months. From 2024 to 2025 the retained count is 9.54% higher.
Both of those years have 12 observed months in this extract. That is still a
count comparison, and it does not establish that reporting is complete or that
inspection intensity changed for a particular reason.

Inspection month-of-year averages use only the years in which that month appears.
January–September have two years (2024 and 2025). October–December also include
2023, and October 2023 is partial, so the October average (5,286 records per
day) is not comparable to the other months. July's two-year mean is 7,906
records per calendar day. That is not an exposure rate.

Unmatched crash records are about 1.4% to 1.6% of linkable crashes in each year
(1.40% in 2022 and 1.51% for 2016–2025 combined). Unidentified crash records,
which have no usable DOT, are about one fifth of retained crashes each year.
Inspection unmatched records stay under 0.01% of linkable inspections, and no
retained inspection lacks a usable DOT.

## Q2. How are retained records distributed across states?

Crash `STATE` is the reported crash location. The largest counts are Texas
(212,725), California (140,256), Florida (101,292), Pennsylvania (82,632), and
Illinois (79,163). These are not rates. States do not have equal mileage,
population, or freight activity, so a higher count is not a higher risk.

Inspection `REPORT_STATE` is the uploading jurisdiction, usually associated with
where the inspection was recorded. It is not the crash state and not the
carrier's headquarters. The largest counts are California (919,359), Texas
(620,640), New York (234,554), and North Carolina (217,317). The code `US`
has 190,661 inspection records. It is not a state boundary and is not ranked
here as one. See `state_year_activity.csv`, `states_crash.png`, and
`states_inspection.png`.

## Q3. Among Census-matched records, how do counts differ by current fleet size and operation?

Carrier comparisons use matched records only.

| Source | Retained | Used (matched) | Excluded unmatched | Excluded unidentified | Excluded share of retained |
| --- | ---: | ---: | ---: | ---: | ---: |
| Crash | 1,868,953 | 1,445,220 | 22,154 | 401,579 | 22.67% |
| Inspection | 5,852,073 | 5,851,766 | 307 | 0 | 0.01% |

The unmatched percentage uses a different denominator: usable DOT records only.
For crashes that is 22,154 / 1,467,374 = 1.51%. Unidentified records are outside
that percentage.

Among matched carrier-years, the current power-unit bin `101+` accounts for
486,781 crash records and 1,708,899 inspection records, from 7,992 carriers and
53,551 carrier-years. The median is 3 crash records per carrier-year in that
bin. One-unit carriers account for 199,484 matched crash records across 314,935
carriers, with a median of 0 crash records per carrier-year. A median of 0
means the typical carrier-year in that bin is present because of an inspection,
not because of a crash. None of these figures is a crash rate per power unit.
Today's fleet size may not be the fleet size at the time of the event.
Thirty-eight matched carrier-years have missing power units; they stay in the
`missing` bin and are not coded as zero. See `by_fleet_size_matched_only.csv`
and `fleet_size_crashes.png`.

Current `CARRIER_OPERATION` A (interstate) has 1,197,577 matched crash records
and 4,957,879 matched inspection records. Code C (intrastate, non-hazardous)
has 244,753 crash records and 893,157 inspection records. Code B (intrastate
hazardous materials) has 94 crash records and 720 inspection records. The B
group is small in this extract. Missing operation is left missing (2,796
matched crash records). Driver-count bins are in
`by_driver_count_matched_only.csv` and follow the same matched-only rule.
Total drivers is missing more often than power units, including 8,031 matched
carrier-years in the driver `missing` bin.

## What this does not answer

Whether a carrier's fleet, operation, or headquarters at the time of a 2016–2025
event matched the current census snapshot. Whether states or months differ after
accounting for exposure. Why 2020 crash records are lower. Whether inspections
before 2023-10-30 exist in another FMCSA product. Whether a crash record is a
single vehicle or a single incident in a file that was not downloaded here.
Causal effects are not identified.
