# Quality decisions and integration contract

These are explicit engineering rules, not invented FMCSA dictionary meanings.
Definitions and dictionary revisions are in [variable selection](variable_selection.md).

1. **Input boundary.** Uncompressed UTF-8 CSV, optional BOM, unique nonempty
   headers after trim/uppercase. Validate every record's width/quoting, even for
   unselected fields. Use selected string columns with pandas chunks; keep source
   files immutable, record SHA-256, schema availability and software versions.
   An empty file is an error; a header-only table is a valid empty extract.
2. **Identifiers.** Reuse the census integer parser: trim, accept positive whole
   decimal strings and `.0` suffixes; `001`, `1`, `1.00` match. Reject zero,
   negative, fractional, scientific notation and >15 significant digits. This
   wider-than-dictionary bound preserves compatibility, not registration validity.
   Missing numeric tokens: blank, NA, N/A, NULL, NAN (case insensitive). Invalid
   DOT rows cannot join; valid event records without DOT still contribute to the
   separate monthly activity table. Missing/invalid event IDs are excluded.
3. **Dates.** Explicit YYYYMMDD or YYYY-MM-DD only; reject impossible dates and
   timestamps rather than infer locale. Keep missing and invalid diagnostics.
   Safety event interval is [2016-01-01, 2026-01-01). Report full parsed coverage
   before filtering and retained coverage. Administrative update/upload dates
   must not substitute for occurrence dates.
4. **Duplicates.** First valid DOT occurrence supplies census attributes. Event
   IDs are unique within each source after valid date/window checks; first
   eligible occurrence wins, across chunks, including records without DOT.
   Compare selected cleaned payloads to report conflicting duplicates. Input order
   can change retained values; do not mix repeated historical extracts. Inspection
   status D (dictionary duplicate) is excluded before event-ID selection. Other
   processing statuses are retained and profiled, so these are observed source
   records, not a certified complete/recordable universe. Exact identity on
   selected fields cannot detect differences in excluded columns.
5. **Measurements.** Reuse nonnegative integer syntax; invalid/missing values
   become nullable with per-field quality counts. Zero is valid. Aggregate sums
   use only observed values; an all-missing sum remains null, and `_observed`
   exposes the denominator. No automatic imputation or safety-rate calculation.
   Crash severity sums may repeat accident casualties across vehicle records.
6. **Geography.** Trim/uppercase; keep country/state jointly for census. Missing
   and malformed codes have separate labels. US states/DC, territories, unknown
   US states, non-US and unknown country remain distinct. Two-letter NA is
   preserved, not treated as a numeric NA token. Syntax-valid unknown codes are
   not asserted to be official. Crash STATE is occurrence geography;
   REPORT_STATE is retained separately. Inspection REPORT_STATE can include
   provinces and federal codes; no country is guessed from it.
7. **Aggregation/join.** Store retained records in temporary indexed SQLite,
   aggregate each source separately to DOT × year, then union keys and join
   the two aggregates one-to-one. Link to one census row per DOT. Include event
   keys absent from census with `census_matched=0`. Census-only carriers remain
   in `carriers.csv`; do not fabricate ten historical years of participation.
   Event counts of zero mean no retained records from that supplied file for
   that observed key/year. Measurement sums stay null when unavailable, even
   when an event count is zero. No row implies verified exposure or safe operation.
8. **Reconciliation.** Raw rows partition into excluded reasons, duplicate IDs
   and retained records. Retained safety rows partition into valid-DOT and
   unidentified records. Aggregate counts must equal retained valid-DOT counts;
   monthly counts include unidentified records. Integrated DOT/year keys must
   equal the union of source keys. Matched plus unmatched counts must reconcile.
9. **Publication.** New output directories only; stage and rename together after
   processing and input-stat checks. Do not modify raw files. SQLite intermediate
   and index growth use disk; pandas/export memory scales with chunk size.
   Parquet uses an explicit schema to avoid null-first-batch type drift. Never
   commit raw extracts, generated outputs, local environments or caches.

The census snapshot relates current attributes to historical events, not historical
fleet state. Full-export coverage, duplicate-resolution suitability, plausible
numeric ranges, revision/status policy and country-code-domain completeness
need review before scientific interpretation. No full-scale processing result is
claimed by this contract.
