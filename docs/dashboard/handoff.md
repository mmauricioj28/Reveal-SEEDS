# Research review and demonstration

## Repository and snapshot audit

The dashboard branch starts at [main revision d6a1298](https://github.com/mmauricioj28/Reveal-SEEDS/tree/d6a1298d7df0ad1d62bc17583eecf99623e4ebb4). Two data routes are available. Their definitions determine which questions a figure can answer.

| Team contribution | What the source establishes | Decision for the viewer |
| --- | --- | --- |
| Michael's [database and file organization](https://github.com/mmauricioj28/Reveal-SEEDS/pull/19), `Python/census`, `Python/crash`, `Python/database` and `SQL` | Separate Census and crash databases, including tables at vehicle and roadway-crash grain. The main README covers 2015–2025. | Use the project dictionaries for field meanings. Avoid substituting the vehicle table for the integrated crash-record series. |
| Harika's [DuckDB integration](https://github.com/mmauricioj28/Reveal-SEEDS/pull/16) and [team EDA](../../analysis/) | The October 24 route loads five Parquets. Its eight views include carrier-linked annual crashes, all retained monthly crashes, seasonal bins, geography and matched carrier groups. Its exporter writes three crash trend tables. Fleet bins also differ between exploratory scripts. | Keep that Tableau workflow available. Linked annual counts cannot be compared directly to all-record monthly counts. The [builder repair](https://github.com/mmauricioj28/Reveal-SEEDS/pull/20) is independently reviewable. |
| Ayaan's integration branch and Raghul's [download checks](https://github.com/mmauricioj28/Reveal-SEEDS/pull/11), [linkage](https://github.com/mmauricioj28/Reveal-SEEDS/pull/12), [EDA](https://github.com/mmauricioj28/Reveal-SEEDS/pull/13) and [run handoff](https://github.com/mmauricioj28/Reveal-SEEDS/pull/14) | At review on November 18, these four PRs remained open. Their successive bases are Ayaan's exploration branch, then the heads of PRs 11, 12 and 13. Earlier PRs 7–9 landed in that upstream line. The archived November 2 run has a monthly linkage breakdown and a checked event-carrier union. | Read two of its five Parquets and its receipts in place. The November 2 run is a **data dependency**. The dashboard implementation and synthetic tests can be reviewed on main without merging the upstream branches. |

The November run used one Census entry per canonical USDOT number, two sets of source-specific carrier/year summaries, one integrated row per event-bearing DOT/year and monthly activity grouped by source, geography and linkage. The dashboard needs only the integrated and monthly tables. DuckDB checks their keys, reconciles monthly and yearly counts and writes aggregates. The browser filters those aggregates locally. Tableau can consume the CSVs at the same grains. This keeps downloads, normalization, deduplication and the carrier join with their existing owners.

For orientation, the October module documents 1,868,397 retained crash records. The November receipt records 1,868,953. Each figure uses a single run. The two numbers should only be compared as an extract-version check.

## Walkthrough for the research team

Use the complete November 2 run for the numbers below. If the fingerprint changes, regenerate and verify the talking points first.

| Step | Presenter action | Check or point to make |
| --- | --- | --- |
| 1 | Start with crash records, all jurisdictions and 2016–2025. Open the chart data. | The national total is **1,868,953**. Read 196,568 for 2018 and 167,613 for 2020. These are recorded volumes. The data do not identify the reason for the difference. |
| 2 | Switch to monthly, then calendar-month grouping. Inspect the months included in one point. | Annual totals add records. Calendar-month means divide by the number of eligible observed months. Explain how gaps or a partial boundary affect that denominator. |
| 3 | Set both years to 2024. In the trend view select NJ, then open the geography view. | New Jersey has **6,508 crash records** by crash location. Its **46,933 inspections** are grouped by reporting jurisdiction. The two state labels answer different questions. |
| 4 | Select inspections, all jurisdictions, 2016–2025. Switch to monthly and inspect October 2023. | **27 of 120** months contain records. The first observed inspection date is **October 30, 2023**. The earlier gap and the short first month explain why a ten-year inspection growth line would mislead. |
| 5 | Open carrier characteristics, select crash records over the full range, then switch from power units to operation. | **1,445,220** crash records link to the Census. Another **22,154** have an identifier absent from the Census and **401,579** lack a usable one. Across both dimensions the matched total is the same. Each event inherits the carrier's snapshot classification. |
| 6 | Open the definitions, record the snapshot ID and download the aggregate used for a slide. | The research group can reproduce the figure from the named source, period, filters, counting rule and denominator. End with the coverage or linkage limitation most relevant to that figure. |

## Acceptance and handoff

**Research and white-paper group.** Select the question and exact comparison window for each figure. Confirm the interpretation against the archived aggregates and carry the data coverage, unit and snapshot into captions. A historical fleet-size question requires dated carrier characteristics. A risk comparison also needs a defensible exposure measure.

**Dashboard and presentation group.** Reproduce the same values in Tableau, check filter scope with the research group, and rehearse the walkthrough before release. The browser viewer is available for the rehearsal. Workbook publication and team approval remain open.

| Stage | Work to finish | Evidence for review |
| --- | --- | --- |
| Week 9 | Agree on the extract, resolve ownership of its archived files, then build Tableau sheets from the three CSVs. Compare national and NJ examples, calendar gaps, category exclusions and state-filter behavior. | A workbook tied to one fingerprint, a reconciliation checklist and proposed paper captions. |
| Week 10 | Review captions with the research group, rehearse the state-to-carrier transition and verify the demo on the presentation machine. Record the release location and refresh owner after team review. | A working demo, the reviewed figures and their filter selections, final slide deck and paper references. |

### Verification on the archived run

All three raw input digests matched the November receipt. An independent query of the original CSVs recovered every crash jurisdiction-month count (6,187 groups) and every inspection jurisdiction-month count (1,509 groups). Comparing the exported categories against the [earlier EDA tables](https://github.com/mmauricioj28/Reveal-SEEDS/tree/cc4143ae0feb318e5678163a77c31277c60ac710/docs/eda_2016_2025) matched all 13 observed source-years, 147 source-months, 696 source/state/year groups, seven fleet groups and four operation groups. Both carrier comparisons reconciled carrier-years and both event measures.

Two independent exports from the same inputs produced byte-identical outputs. The verified snapshot ID was `0fd4457bc8bf379f1e197b83505228f388b15cb926c6fc4fdf5c4697b18ea57a`. Acceptance applies to this archived extract. Portal refreshes and peer-reviewed interpretations require a new check.
