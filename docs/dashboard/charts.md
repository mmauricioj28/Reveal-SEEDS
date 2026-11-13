# Chart definitions and acceptance checks

The viewer answers two questions for the research team and the Rutgers/Reveal audience. How does the volume of recorded activity vary across time and jurisdictions? Which current carrier groups account for the portion that can be linked to a Census entry?

## Tables and units

| File | One row represents | Measures and inclusion |
| --- | --- | --- |
| `activity.csv` | Source × year × month × jurisdiction with observations | Three integer counts of retained records. Add `matched`, `unmatched` and `unidentified` for the displayed total. Include unknown locations in national sums. |
| `calendar.csv` | Source × calendar month over the requested years | National counts by linkage status and a coverage label. An observed month can contain zero in one linkage group. A month without observations has empty counts in all three. |
| `carriers.csv` | Year × grouping dimension × current Census category | Counts of matched DOT/year rows and their crash and inspection records. Choose exactly one dimension before summing. Fleet and operation each describe the same carriers. |

`dashboard.json` carries the browser aggregates and run identity. Source hashes describe the three raw inputs. Parquet hashes identify the two files actually consumed. The original receipt records raw hashes and reconciliation totals. Keep the exported fingerprint with figures used in the paper so another reviewer can identify the same run.

The input activity grain also includes `REPORT_STATE` and `match_status`. For crashes the exporter collapses reporting jurisdictions within the same crash location. For inspections it uses the reporting jurisdiction carried by the upstream table. These location fields differ from the principal office state in the Census. No event location is inferred from a carrier address. Each retained crash ID or inspection ID contributes to its own source once, according to the integration rules. A collision can involve several commercial vehicles. Neither file establishes the number of trips or miles traveled.

## Views

| Reader's question | Display and calculation | Filter and interpretation |
| --- | --- | --- |
| How does the recorded volume change from year to year? | Line of monthly counts summed by year. Show the number of months present and mark a boundary inside a month. | Select one source, an inclusive year range and optionally one jurisdiction. Compare totals alongside coverage. No annualized estimate or growth percentage. |
| When did a change or reporting gap occur? | Line with one position per calendar month in the range. Leave a gap when there is no observation. | The state filter selects an event jurisdiction. A month present nationally can still be unobserved for a selected jurisdiction. |
| Is there a recurring calendar-month pattern? | For Jan through Dec, divide summed records by the number of included occurrences of that month. Each eligible year gets equal weight within a month. | Exclude absent months and source boundary months cut short by the first or last recorded date. The data table gives each denominator. A count per observed month does not adjust for month length. |
| Which locations have the most recorded activity? | Descending horizontal bars and an exact-value table by source-specific jurisdiction. | Compare jurisdictions within one source and time window. Keep reported category codes, including exceptional values. Population and traffic differ across places. |
| How much inspection history is available? | Choose inspections in trends. Use calendar rows, date bounds and observed-month counts to locate partial periods. | The November run first observes an inspection on October 30, 2023. Only two calendar dates fall inside that month's observed range. A month with some records does not establish reporting completeness. |
| Where do linked records fall across fleet sizes? | National bars by current `POWER_UNITS`: 0, 1, 2–5, 6–20, 21–100, 101+, or missing. Sum the event column for the selected source. | Use one fleet dimension. Keep a reported zero separate from an absent value. Category assignments come from a single Census vintage even for older events. |
| Which operating classes account for matched records? | Same measure grouped by the Census operating code. A denotes interstate, B intrastate hazardous materials and C intrastate non-hazardous materials. | Keep missing and other reported codes visible. Count distinct DOT numbers separately if a future question needs unique carriers. Adding carrier-years would count recurring carriers again. |

The carrier file has no event-state dimension. Its population is the matched part of the union of DOT/year pairs with a crash or an inspection. A row can have events of only one type. When a source has no observations anywhere in a year, its measure stays blank for every carrier category. Selecting one category filters the matched count, while the exclusions continue to describe the national source for the selected years. Unmatched events have a usable DOT number absent from the Census. Unidentified events lack a usable DOT number. Both groups appear in overall trends and the carrier-view exclusion totals.

## Review checks

1. At the full period, reconcile the three activity counts to the source receipt. For each source and year, the linked and unlinked usable-DOT totals must agree with their corresponding carrier-year sums. Inspect missing months before calculating a seasonal mean.
2. Sum each carrier dimension independently. Its event counts must reproduce the matched portion of the selected national source. State selection must never silently carry into a national carrier comparison.
3. Select a year before inspection coverage and then the first observed year. Look for an empty period followed by a partial-year count. Retrieve exact values in the data table using the keyboard. Check the figure and filter labels at a narrow viewport.
4. Capture the source, years, jurisdiction, dimension and snapshot identity for every figure carried into the white paper. A frequency comparison alone cannot support a safety ranking.
