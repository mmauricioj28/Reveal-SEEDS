# Source-verified variable selection

Verified October 16, 2026 against the three live metadata APIs, actual 100-row CSV
samples and attached official PDF dictionaries. Metadata has blank column
descriptions; dictionary definitions control meanings. API names are lowercase;
the pipeline normalizes headers to uppercase. All CSV fields enter as strings.
The tables give cleaned types and the minimal selected schema; optional absent
columns are reported, not silently interpreted as zero.

| Source | Metadata and official dictionary |
| --- | --- |
| Company Census (147 columns) | [metadata](https://data.transportation.gov/api/views/az4n-8mr2.json), [Rev08, January 23 2026](https://data.transportation.gov/api/views/az4n-8mr2/files/05274d1b-8109-4409-a4ef-237e12f870c9?download=true) |
| Crash (59 columns) | [metadata with attachment link](https://data.transportation.gov/api/views/aayw-vxb3.json), dictionary Rev05, November 4 2025 |
| Vehicle Inspection (63 columns) | [metadata with attachment link](https://data.transportation.gov/api/views/fx4q-ay7w.json), dictionary Rev05, October 15 2025 |

Use each metadata response's `metadata.attachments[].assetId` to resolve the
dictionary: `/api/views/{dataset_id}/files/{assetId}?download=true`. The inspection
dictionary also describes unit, violation and citation tables; those are not the
63-column inspection-header resource selected here.

## Company Census: snapshot entity grain

| Columns | Definition and purpose | Cleaned type / treatment |
| --- | --- | --- |
| DOT_NUMBER (required) | Sequential MCMIS census identifier, no internal coded structure; joins all sources | canonical positive integer string; missing/invalid excluded from carrier table |
| PHY_STATE (required), PHY_COUNTRY | Principal office state/province and nationality; population geography | uppercase strings; separate missing/invalid labels; US includes territories; CA means Canada in country field |
| POWER_UNITS, TOTAL_DRIVERS | Total power units and drivers; fleet/operational description | nullable nonnegative integers; zero retained |
| MCS150_MILEAGE, MCS150_MILEAGE_YEAR | Calendar-year mileage reported on MCS-150 and associated year | nullable integers; year plausibility 1900–2100; not matched historical exposure |
| CARRIER_OPERATION | A interstate; B intrastate hazardous material; C intrastate non-hazardous transport | raw uppercase code; blank/unrecognized separate, never guessed |
| STATUS_CODE | A active, I inactive, P pending at snapshot | raw uppercase code; no automatic active-only restriction |
| CARSHIP | Entity types; dictionary includes C carrier, S shipper, B broker, R registrant, F freight forwarder, I intermodal equipment provider, T cargo tank; multiple letters possible | raw uppercase string, retained for future explicit universe filter |
| SAFETY_RATING | Compliance rating type; dictionary lists S, C, U or blank | raw uppercase code; blank remains unknown; never a numeric safety score |

SAFETY_RATING_DATE and REVIEW_DATE are verified source fields but excluded from
this minimal integration: dating reviews requires a separate longitudinal design.
The dictionary does not establish that every blank rating means never reviewed.
FLEETSIZE is a coded category, so bins derive directly from POWER_UNITS. TRUCK_UNITS,
TOTAL_CDL, HM_IND and cargo indicators are verified but deferred until a question
requires them. RECORDABLE_CRASH_RATE is excluded: no compatible historical
denominator has been established. Names, street addresses, contact details and
VINs are unnecessary for these questions and are not loaded/exported.

## Crash: vehicle-involvement record grain

Dictionary pp. 5–7 defines CRASH_ID as a unique crash-record identifier,
REPORT_DATE as the date the crash occurred, and REPORT_SEQ_NO as the vehicle
sequence in a multi-vehicle crash. Counts below are **crash records**, not unique
roadway incidents. Fatality/injury values describe the accident; summing across
vehicle records can repeat people and must not be labeled unique casualties.

| Columns | Definition / analytical purpose | Cleaned type / treatment |
| --- | --- | --- |
| CRASH_ID, DOT_NUMBER, REPORT_DATE (required) | Record identity, census linkage, occurrence date | positive identifier strings; date YYYYMMDD (ISO YYYY-MM-DD also accepted); filter 2016–2025 |
| STATE | State/district in which crash occurred; geography | uppercase location code; no country inferred |
| REPORT_STATE | State reporting crash; separate from occurrence state | uppercase code |
| FATALITIES, INJURIES | Numbers of fatalities and injuries in accident | nullable nonnegative integers; record-reported sums plus observed-value counts; not unique casualty totals |
| CI_STATUS_CODE | Processing status: C complete, H hold, I intrastate, N non-match, P potential resolution, T census search, U initial upload | uppercase code retained/profiled; no status restriction |

REPORT_NUMBER / REPORT_SEQ_NO are verified but deferred: an incident-level design
must first validate a composite jurisdiction/report key and casualty repetition.
Weather/road/light codes and FEDERAL_RECORDABLE are verified but excluded from
this initial minimal workflow; no claim that only federally recordable records
are included. Blank severity is not imputed to zero.

## Vehicle Inspection: inspection-header grain

Dictionary pp. 5–6 defines these counts. They are numbers of **violations**;
DRIVER_OOS_TOTAL is not a count of inspected drivers and VEHICLE_OOS_TOTAL is not
the number of vehicles inspected. Inspection level affects what is assessed.

| Columns | Definition / purpose | Cleaned type / treatment |
| --- | --- | --- |
| INSPECTION_ID, DOT_NUMBER, INSP_DATE (required) | Unique inspection record, census linkage, inspection date | identifier strings; date as above; filter 2016–2025 |
| REPORT_STATE | Uploading state/district/province, usually inspection location | uppercase code; not carrier domicile and not a verified country |
| INSP_LEVEL_ID | Inspection level; dictionary lists 1,2,3,4,5,99 | raw code retained/profiled; no interpretation of unrecognized codes |
| VIOL_TOTAL, OOS_TOTAL | Total violations and total out-of-service violations | nullable nonnegative integer; zero distinct from blank |
| DRIVER_OOS_TOTAL, VEHICLE_OOS_TOTAL | Driver and vehicle out-of-service violation counts | nullable integers; observed-value counts accompany sums |
| CI_STATUS_CODE | U unprocessed, T census search, C complete, D duplicate, N non-match, H hold, I intrastate, P potential resolution, X non-motor carrier | uppercase code; D records excluded separately before ID deduplication |

DRIVER_VIOL_TOTAL, VEHICLE_VIOL_TOTAL, HAZMAT_VIOL_TOTAL and HAZMAT_OOS_TOTAL exist
but are deferred to level-aware follow-up questions. Missing values may mean
unavailable or non-applicable assessment. Their field-specific distinction is
unresolved; preserve blank and report observed counts rather than invent a code.

## Missingness and scope

See [quality decisions](data_quality_decisions.md) for exact parser, duplicate and
integration rules, and [research questions](research_questions.md) for use cases.
Dictionary coverage does not prove a complete local extract or validate a DOT
registration. API samples verify shape, not representativeness or full coverage.
