# Weeks 3–4 analytical plan

Period: **2016–2025 inclusive** for safety records. The October 9 mentor guidance
supplied for this task sets the period and priorities; this is not a meeting
transcript. These questions extend Harika's preliminary variable selection and
annual/monthly exploration, and Ayaan's carrier integration work. No findings or
hours personally worked are inferred from this plan.

## 1. How does the registered carrier population differ across states?

- Objective: describe the distribution of registered entities and fleet sizes in
  the supplied Company Census snapshot.
- Data/variables: census DOT_NUMBER, PHY_COUNTRY, PHY_STATE, POWER_UNITS,
  TOTAL_DRIVERS, STATUS_CODE, CARRIER_OPERATION and CARSHIP.
- Unit: one canonical DOT identifier; first occurrence in file order.
- Measures/visuals: carrier counts and shares by US state/DC, separate territory
  counts, POWER_UNITS bins (0, 1, 2–5, 6–20, 21–100, 101+), missingness;
  state map and stacked fleet distribution bars.
- Limits: census contains non-carrier entities; publish the registered-entity
  universe first and specify any later status/CARSHIP restriction. Snapshot
  geography is the principal office, not where vehicles operate. Unknown country
  is not inferred from state. This does not measure state traffic exposure.
- Dashboard value: population context and explicit universe/location filters.

## 2. Do observed safety-record counts differ by current operating characteristics?

- Objective: compare distributions of observed crash-record and inspection
  counts across current fleet bins and CARRIER_OPERATION groups.
- Data/variables: census fields above, mileage and mileage year for context;
  crash CRASH_ID, DOT_NUMBER, REPORT_DATE; inspection INSPECTION_ID,
  DOT_NUMBER, INSP_DATE, VIOL_TOTAL and OOS_TOTAL.
- Unit: DOT × observed event year linked to a single census snapshot. Carriers
  without records remain in a separate census table; absence is not safe driving.
- Measures/visuals: observed counts per linked carrier, medians/quantiles computed
  downstream, missingness and linkage coverage; faceted distributions by year
  and current fleet bin. OOS counts describe violations, not failed inspections.
- Limits: descriptive association only. Historical fleet size, operating status,
  miles and time under observation are unavailable. Selection into inspections
  is nonrandom. Current mileage is not an exposure denominator for 2016–2025.
- Dashboard value: exploratory carrier profiles with snapshot and coverage labels;
  no crash-risk score or causal ranking.

## 3. How do observed records vary annually and geographically in 2016–2025?

- Objective: describe annual reported crash-record and inspection activity and
  identify coverage gaps before interpreting trends.
- Data/variables: event IDs, dates and DOT; crash STATE and REPORT_STATE;
  inspection REPORT_STATE (uploading jurisdiction, usually inspection location).
- Unit: retained source record aggregated by event year and source geography.
- Measures/visuals: source counts, invalid dates, unmatched DOT fractions and
  year-over-year descriptive changes; annual lines and state/year heatmaps.
- Limits: crash records identify vehicle involvements; distinct CRASH_ID is not
  necessarily a distinct roadway incident. STATE and REPORT_STATE differ.
  Reporting policies, revisions and completeness can change; extract date must
  accompany charts. Do not label inspection uploads as precise physical sites.
- Dashboard value: separate event geography from census domicile and expose
  excluded/unlinked records beside linked counts.

## 4. Are monthly patterns repeatable across years?

- Objective: assess whether monthly variation recurs rather than extrapolate a
  single year's peak into a seasonal conclusion.
- Data/variables: validated REPORT_DATE and INSP_DATE; event IDs and geography.
- Unit: source × year × month × event/reporting state, including retained records
  lacking DOT in the separate monthly summary.
- Measures/visuals: monthly counts, shares within each year, observed records per
  calendar day (not per vehicle mile), year/month heatmaps and aligned month lines.
- Limits: month length, reporting delays, enforcement intensity, weather, traffic
  volume and geographic composition are potential explanations. Empty source
  months indicate no observed records, not verified complete zero activity.
- Dashboard value: month/year filters and coverage warnings; causal weather
  effects and formal seasonal models are deferred to Week 5 or later.

## Week 5 acceptance and sampling

Before interpreting full-data EDA, archive extract queries/checksums and dictionary
versions; reconcile raw, excluded, deduplicated, linked and unmatched counts;
inspect all 120 months and resolve duplicate conflicts/status codes. Revisit
historical census availability before any exposure-based analysis. The pipeline
does not sample. If sampling becomes necessary, use a reproducible state-stratified
carrier sample with a fixed seed, document unknown/non-US strata and selection
weights, then retrieve all events for selected carriers. Independently sampled
files must never be treated as a complete linked population. An ordered API smoke
sample is a parser check, not a probability sample.
