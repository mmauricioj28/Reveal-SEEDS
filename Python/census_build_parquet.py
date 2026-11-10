"""Step 2 of the Census pipeline: clean the raw Company Census chunks and split them into relational Parquet tables.

Input : FMCSA_data_raw/census_parquet/census_*.parquet  (from census_download.py)
        Census 2020 county FIPS list (read from census.gov, used for dim_state / dim_county)
        FMCSA_data_processed/crash/crash_vehicle.parquet  (optional - only for the crash linkage check)
Output: FMCSA_data_processed/census/*.parquet  + _build_report.txt

Run from the repo root:  python Python/census_build_parquet.py

Grain: ONE ROW PER USDOT NUMBER (registered entity: carriers, shippers, brokers, ...).
The census is a SNAPSHOT of each entity as it is today - fleet size, drivers and status are current
values, not what they were in a past year.
  add_date   = date the record was created, reactivated OR systematically updated (dictionary Rev08),
               so it is not a clean "first registered" date. Legacy records share a placeholder date.

Tables written:
  census_carrier         1 row per USDOT number   -> status, operation, location, fleet, drivers, mileage, rating
  census_cargo           1 row per USDOT x cargo   -> cargo types hauled (from the crgo_* "X" flags)
  census_classification  1 row per USDOT x class   -> for-hire / private / government ... (from classdef)
  agg_census_state       state rollup of current carriers (dashboard population context)
  agg_census_added_month state x month of add_date (record creation / reactivation activity)
  dim_*                  code lookups from the MCMIS Company Census Data Dictionary (Rev08, 2026-01-23)
"""
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path("FMCSA_data_raw") / "census_parquet"
COUNTY_URL = "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"
CRASH_VEHICLE = Path("FMCSA_data_processed") / "crash" / "crash_vehicle.parquet"
OUT_DIR = Path("FMCSA_data_processed") / "census"
API_COUNT = "https://data.transportation.gov/resource/az4n-8mr2.json?$select=count(*)"
TODAY = pd.Timestamp(date.today())

STR = "string[pyarrow]"
report = []  # lines for _build_report.txt


def log(msg=""):
    print(msg, flush=True)
    report.append(str(msg))


# ---------------------------------------------------------------- lookups (data dictionary)
TEXT_LOOKUPS = {
    "dim_status": {"A": "Active", "I": "Inactive", "P": "Pending (Mexican carrier applying for authority)"},
    "dim_carrier_operation": {"A": "Interstate", "B": "Intrastate hazmat", "C": "Intrastate non-hazmat"},
    "dim_safety_rating": {"S": "Satisfactory", "C": "Conditional", "U": "Unsatisfactory"},
    "dim_review_type": {"C": "Compliance review", "H": "Shipper review", "N": "Non-ratable review",
                        "A": "Safety audit", "S": "Safety review", "E": "Educational contact review",
                        "U": "Historical audit record", "K": "Automatic safety assessment program review",
                        "F": "CTFR only", "G": "CR and CTFR", "I": "Carrier inactivate",
                        "J": "CR and security contact review"},
    "dim_business_org": {"1": "Individual", "2": "Partnership", "3": "Corporation"},
    "dim_entity_type": {"C": "Carrier", "S": "Shipper", "B": "Broker", "R": "Registrant",
                        "F": "Freight forwarder", "I": "Intermodal equipment provider", "T": "Cargo tank"},
}
# FLEETSIZE letter -> power unit range (dictionary p.11); "0" = no power units
FLEETSIZE = {"0": (0, 0), "A": (1, 1), "B": (2, 3), "C": (4, 6), "D": (7, 8), "E": (9, 11), "F": (12, 14),
             "G": (15, 17), "H": (18, 19), "I": (20, 23), "J": (24, 28), "K": (29, 32), "L": (33, 38),
             "M": (39, 44), "N": (45, 55), "O": (56, 75), "P": (76, 100), "Q": (101, 200), "R": (201, 300),
             "S": (301, 400), "T": (401, 550), "U": (551, 999), "V": (1000, 2000), "W": (2001, 3000),
             "X": (3001, 4000), "Y": (4001, 5000), "Z": (5001, None)}
# classdef text values -> dictionary letter
CLASSIFICATION = {"AUTHORIZED FOR HIRE": "A", "EXEMPT FOR HIRE": "B", "PRIVATE PROPERTY": "C",
                  "PRIVATE PASSENGER, BUSINESS": "D", "PRIVATE PASSENGER, NON-BUSINESS": "E", "MIGRANT": "F",
                  "U.S. MAIL": "G", "FEDERAL GOVERNMENT": "H", "STATE GOVERNMENT": "I", "LOCAL GOVERNMENT": "J",
                  "INDIAN TRIBE": "K", "OTHER": "L"}
CLASS_DESC = {"A": "Authorized for hire", "B": "Exempt for hire", "C": "Private (property)",
              "D": "Private passenger (business)", "E": "Private passenger (non-business)", "F": "Migrant",
              "G": "U.S. Mail", "H": "Federal government", "I": "State government", "J": "Local government",
              "K": "Indian tribe", "L": "Other"}
CARGO = {"genfreight": "General freight", "household": "Household goods", "metalsheet": "Metal: sheets, coils, rolls",
         "motoveh": "Motor vehicles", "drivetow": "Driveaway/towaway", "logpole": "Logs, poles, beams, lumber",
         "bldgmat": "Building materials", "mobilehome": "Mobile homes", "machlrg": "Machinery, large objects",
         "produce": "Fresh produce", "liqgas": "Liquids/gases", "intermodal": "Intermodal containers",
         "passengers": "Passengers", "oilfield": "Oilfield equipment", "livestock": "Livestock",
         "grainfeed": "Grain, feed, hay", "coalcoke": "Coal, coke", "meat": "Meat",
         "garbage": "Garbage, refuse, trash", "usmail": "U.S. Mail", "chem": "Chemicals",
         "drybulk": "Commodities dry bulk", "coldfood": "Refrigerated food", "beverages": "Beverages",
         "paperprod": "Paper products", "utility": "Utility", "farmsupp": "Farm supplies",
         "construct": "Construction", "waterwell": "Water well", "cargoothr": "Other"}
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
COUNT_COLS = ["power_units", "truck_units", "bus_units", "owntruck", "owntract", "owntrail", "owncoach",
              "total_drivers", "total_cdl", "driver_inter_total", "total_intrastate_drivers",
              "interstate_within_100_miles", "interstate_beyond_100_miles",
              "intrastate_within_100_miles", "intrastate_beyond_100_miles", "mcs150_mileage"]
DATE_COLS = ["add_date", "mcs150_date", "safety_rating_date", "review_date"]
LEGACY_ADD_DATE = pd.Timestamp("1974-06-01")  # shared by legacy records (see report for its count)


def write(df, name):
    df = df.copy()
    for c in df.columns:  # date-only columns -> SQL DATE instead of TIMESTAMP
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.date
    df.to_parquet(OUT_DIR / f"{name}.parquet", index=False)
    log(f"  wrote {name:24s} {len(df):>10,} rows  {df.shape[1]:>3} cols")


def to_count(s):
    """Nonnegative whole number (accepts '12' and '12.0'); anything else -> NA."""
    n = pd.to_numeric(s, errors="coerce")
    return n.where((n >= 0) & (n == n.round())).astype("Int64")


def check_codes(df, col, allowed):
    """Uppercase a code column and set values not in the dictionary to NA (logged)."""
    df[col] = df[col].str.upper()
    undefined = df[col].notna() & ~df[col].isin(list(allowed))
    if undefined.any():
        log(f"  {col}: {undefined.sum():,} rows with undefined codes "
            f"{sorted(df.loc[undefined, col].unique().tolist())[:10]} -> NA")
    df[col] = df[col].mask(undefined)


# ---------------------------------------------------------------- 1. load
def load_raw():
    files = sorted(RAW_DIR.glob("census_*.parquet"))
    if not files:
        raise SystemExit(f"No parquet files in {RAW_DIR} - run Python/census_download.py first")
    df = pd.concat((pd.read_parquet(f).astype(STR) for f in files), ignore_index=True)
    for c in df.columns:  # trim + blank -> NA
        df[c] = df[c].str.strip().replace("", pd.NA)
    log(f"[1] Loaded {len(df):,} raw census rows from {len(files)} files")
    try:
        api_rows = int(requests.get(API_COUNT, timeout=60).json()[0]["count"])
        log(f"  rows in the API right now: {api_rows:,}  -> difference {len(df) - api_rows:+,}"
            f" (non-zero if the census was updated after the download)")
    except Exception as e:  # the check is informative only
        log(f"  could not reach the API to compare row counts: {e}")
    return df


# ---------------------------------------------------------------- 2. clean / type
def clean(df, counties):
    log("\n[2] Clean + type")
    df["dot_number"] = pd.to_numeric(df["dot_number"], errors="coerce").astype("Int64")
    bad_dot = df["dot_number"].isna() | (df["dot_number"] <= 0)
    log(f"  rows with missing/invalid dot_number dropped: {bad_dot.sum():,}")
    df = df[~bad_dot]
    dupes = df.duplicated("dot_number")
    log(f"  duplicate dot_number rows dropped (first kept): {dupes.sum():,}")
    df = df[~dupes].copy()

    for c in DATE_COLS:
        raw = df[c]
        df[c] = pd.to_datetime(raw, format="%Y%m%d", errors="coerce")
        bad = raw.notna() & (df[c].isna() | (df[c] > TODAY))
        df[c] = df[c].mask(df[c] > TODAY)
        log(f"  {c:20s} blank: {raw.isna().sum():>9,}  invalid or future -> NA: {bad.sum():,}")
    top_add = df["add_date"].value_counts().head(5)
    log(f"  most common add_date values: {', '.join(f'{d.date()} ({n:,})' for d, n in top_add.items())}")
    df["add_date_is_legacy"] = df["add_date"] == LEGACY_ADD_DATE
    log(f"  add_date = {LEGACY_ADD_DATE.date()} (legacy placeholder, flagged add_date_is_legacy): "
        f"{df['add_date_is_legacy'].sum():,} ({df['add_date_is_legacy'].mean():.1%})")
    df["add_year"] = df["add_date"].dt.year.astype("Int16")
    df["add_month_start"] = df["add_date"].dt.to_period("M").dt.to_timestamp()

    for c in COUNT_COLS:
        raw = df[c]
        df[c] = to_count(raw)
        bad = raw.notna() & df[c].isna()
        if bad.any():
            log(f"  {c}: {bad.sum():,} non-numeric/negative/fractional values -> NA")
    year = pd.to_numeric(df["mcs150_mileage_year"], errors="coerce")
    valid_year = year.between(1900, TODAY.year)
    log(f"  mcs150_mileage_year 0/blank/out of range -> NA: {(~valid_year).sum():,} ({(~valid_year).mean():.1%})")
    df["mcs150_mileage_year"] = year.where(valid_year).astype("Int16")
    no_mileage = df["mcs150_mileage_year"].isna() & (df["mcs150_mileage"] == 0)
    log(f"  mcs150_mileage = 0 with no mileage year (not reported) -> NA: {no_mileage.sum():,}")
    df["mcs150_mileage"] = df["mcs150_mileage"].mask(no_mileage)

    # codes
    for col, dim in [("status_code", "dim_status"), ("carrier_operation", "dim_carrier_operation"),
                     ("safety_rating", "dim_safety_rating"), ("review_type", "dim_review_type"),
                     ("business_org_id", "dim_business_org")]:
        check_codes(df, col, TEXT_LOOKUPS[dim])
    check_codes(df, "fleetsize", FLEETSIZE)
    df["hazmat"] = df["hm_ind"].str.upper().map({"Y": True, "N": False}).astype("boolean")
    df = df.drop(columns="hm_ind")

    # fleet size: bins from power_units (same bins as analysis/mcmis_chunked.py) + consistency with FLEETSIZE
    pu = df["power_units"]
    df["fleet_bin"] = pd.cut(pu, [-1, 0, 1, 5, 20, 100, float("inf")],
                             labels=["0", "1", "2-5", "6-20", "21-100", "101+"]).astype(STR)
    lo = df["fleetsize"].map({k: v[0] for k, v in FLEETSIZE.items()}).astype("Float64")
    hi = df["fleetsize"].map({k: (v[1] if v[1] is not None else float("inf")) for k, v in FLEETSIZE.items()}).astype("Float64")
    df["power_units_matches_fleetsize"] = ((pu >= lo) & (pu <= hi)).astype("boolean")
    mismatch = df["power_units_matches_fleetsize"] == False  # noqa: E712 (nullable boolean)
    log(f"  power_units outside the FLEETSIZE code's range: {mismatch.sum():,} "
        f"(flagged power_units_matches_fleetsize = FALSE)")
    log(f"  largest power_units values: {pu.nlargest(5).tolist()}")

    # entity type flags from carship ("C;S;B")
    carship = df["carship"].str.upper().fillna("")
    for code, name in [("C", "carrier"), ("S", "shipper"), ("B", "broker"), ("R", "registrant"),
                       ("F", "freight_forwarder"), ("I", "intermodal_provider"), ("T", "cargo_tank")]:
        df[f"is_{name}"] = carship.str.contains(rf"(?:^|;){code}(?:;|$)", regex=True).astype(bool)
    df["is_active_carrier"] = (df["status_code"] == "A") & df["is_carrier"]

    # geography (physical address = principal place of business, not where trucks drive)
    for c in ["phy_state", "phy_country", "phy_city"]:
        df[c] = df[c].str.upper()
    df["phy_zip5"] = df["phy_zip"].str.extract(r"^(\d{5})", expand=False).astype(STR)
    state_fips = counties.drop_duplicates("STATE").set_index("STATE")["STATEFP"]
    us = df["phy_country"] == "US"
    df["phy_state_fips"] = df["phy_state"].map(state_fips).where(us).astype(STR)
    cnty = df["phy_cnty"].str.extract(r"^(\d{1,3})$", expand=False).str.zfill(3)
    df["phy_county_fips"] = (df["phy_state_fips"] + cnty).astype(STR)
    known = set(counties["STATEFP"] + counties["COUNTYFP"])
    df["phy_county_fips_valid"] = df["phy_county_fips"].isin(known)
    df["is_us_50_dc"] = us & df["phy_state"].isin(list(STATE_NAMES))
    log(f"  physical country: {df['phy_country'].value_counts(dropna=False).head(6).to_dict()}")
    log(f"  US records whose county FIPS doesn't match a Census county: "
        f"{(us & ~df['phy_county_fips_valid']).sum():,} -> kept, flagged phy_county_fips_valid")
    return df


# ---------------------------------------------------------------- 3. tables
CARRIER_COLS = [
    "dot_number", "status_code", "is_active_carrier", "carrier_operation", "carship",
    "is_carrier", "is_shipper", "is_broker", "is_registrant", "is_freight_forwarder", "is_intermodal_provider",
    "is_cargo_tank", "business_org_id", "hazmat",
    "add_date", "add_date_is_legacy", "add_year", "add_month_start", "mcs150_date",
    "phy_city", "phy_state", "phy_state_fips", "phy_zip5", "phy_county_fips", "phy_county_fips_valid",
    "phy_country", "is_us_50_dc",
    "power_units", "truck_units", "bus_units", "fleetsize", "fleet_bin", "power_units_matches_fleetsize",
    "owntruck", "owntract", "owntrail", "owncoach",
    "total_drivers", "total_cdl", "driver_inter_total", "total_intrastate_drivers",
    "interstate_within_100_miles", "interstate_beyond_100_miles",
    "intrastate_within_100_miles", "intrastate_beyond_100_miles",
    "mcs150_mileage", "mcs150_mileage_year",
    "safety_rating", "safety_rating_date", "review_type", "review_date",
    "docket1prefix", "docket1", "cargo_count", "crgo_cargoothr_desc",
]


def build_cargo(df):
    flags = [f"crgo_{k}" for k in CARGO]
    long = df[["dot_number"] + flags].melt(id_vars="dot_number", var_name="cargo_code", value_name="flag")
    long = long[long["flag"].notna()]
    other_values = long["flag"].str.upper().value_counts().to_dict()
    if set(other_values) - {"X"}:
        log(f"  cargo flag values other than 'X' (treated as hauls that cargo): {other_values}")
    long["cargo_code"] = long["cargo_code"].str.removeprefix("crgo_").astype(STR)
    cargo = long[["dot_number", "cargo_code"]].sort_values(["dot_number", "cargo_code"]).reset_index(drop=True)
    counts = cargo.groupby("dot_number").size()
    df["cargo_count"] = df["dot_number"].map(counts).fillna(0).astype("Int16")
    log(f"  entities with no cargo type listed: {(df['cargo_count'] == 0).sum():,}")
    return cargo


def build_classification(df):
    s = df.set_index("dot_number")["classdef"].dropna().str.upper().str.split(";").explode().str.strip()
    s = s[s != ""].str.replace("U. S. MAIL", "U.S. MAIL", regex=False)
    codes = s.map(CLASSIFICATION)
    other_variant = codes.isna() & s.str.startswith("OTHER")  # e.g. OTHER-REGISTRANT, OTHER-LEASED -> L (Other)
    log(f"  'OTHER-...' classdef variants mapped to L (Other): {other_variant.sum():,}")
    codes = codes.mask(other_variant, "L")
    unknown = s[codes.isna()]
    if len(unknown):
        log(f"  classdef values not in the dictionary (dropped): {unknown.value_counts().head(10).to_dict()}")
    out = pd.DataFrame({"dot_number": codes.dropna().index.astype("int64"),
                        "class_code": codes.dropna().astype(STR).values}).drop_duplicates()
    return out.sort_values(["dot_number", "class_code"]).reset_index(drop=True)


def build_aggs(carrier):
    us = carrier[(carrier["phy_country"] == "US") & carrier["phy_state"].notna()]
    log(f"  US records with no physical state (left out of the state rollups): "
        f"{((carrier['phy_country'] == 'US') & carrier['phy_state'].isna()).sum():,}")
    active = us["status_code"] == "A"
    ac = us["is_active_carrier"]
    g = us.assign(
        active=active, active_carriers=ac,
        active_interstate=ac & (us["carrier_operation"] == "A"),
        active_hazmat=ac & us["hazmat"].fillna(False),
        active_power_units=us["power_units"].where(ac & us["power_units_matches_fleetsize"].fillna(False)),
        active_drivers=us["total_drivers"].where(ac),
    ).groupby("phy_state")
    by_state = g.agg(entities=("dot_number", "size"), active_entities=("active", "sum"),
                     active_carriers=("active_carriers", "sum"), active_interstate_carriers=("active_interstate", "sum"),
                     active_hazmat_carriers=("active_hazmat", "sum"),
                     active_power_units=("active_power_units", "sum"),
                     active_drivers=("active_drivers", "sum")).reset_index()
    real = us[~us["add_date_is_legacy"] & us["add_month_start"].notna()]
    by_month = real.assign(still_active=real["status_code"] == "A").groupby(["phy_state", "add_month_start"]).agg(
        records_added=("dot_number", "size"), carriers_added=("is_carrier", "sum"),
        still_active=("still_active", "sum")).reset_index()
    return by_state, by_month


def build_dims(counties):
    dims = {name: pd.DataFrame({"code": list(m), "description": list(m.values())}).astype(STR)
            for name, m in TEXT_LOOKUPS.items()}
    dims["dim_fleetsize"] = pd.DataFrame({
        "code": list(FLEETSIZE), "min_power_units": [v[0] for v in FLEETSIZE.values()],
        "max_power_units": [v[1] for v in FLEETSIZE.values()]}).astype(
        {"code": STR, "min_power_units": "Int32", "max_power_units": "Int32"})
    dims["dim_classification"] = pd.DataFrame({"code": list(CLASS_DESC), "description": list(CLASS_DESC.values())}).astype(STR)
    dims["dim_cargo"] = pd.DataFrame({"code": list(CARGO), "description": list(CARGO.values())}).astype(STR)
    st = counties.drop_duplicates("STATE")[["STATE", "STATEFP"]].rename(columns={"STATE": "state", "STATEFP": "state_fips"})
    st["state_name"] = st["state"].map(STATE_NAMES)
    st["is_50_states_dc"] = st["state_name"].notna()
    st["state_name"] = st["state_name"].fillna(st["state"])
    dims["dim_state"] = st.astype({"state": STR, "state_fips": STR, "state_name": STR})
    dims["dim_county"] = pd.DataFrame({
        "county_fips": counties["STATEFP"] + counties["COUNTYFP"], "state": counties["STATE"],
        "state_fips": counties["STATEFP"], "county_code": counties["COUNTYFP"], "county_name": counties["COUNTYNAME"],
    }).astype(STR)
    return dims


# ---------------------------------------------------------------- 4. sanity checks
def validate(carrier, cargo, classification):
    log("\n[5] Sanity checks")
    checks = {  # bool() so numpy/pandas booleans print as OK/FAIL
        "dot_number unique": bool(carrier["dot_number"].is_unique),
        "no NULL dot_number": bool(carrier["dot_number"].notna().all()),
        "every cargo row has a census carrier": bool(cargo["dot_number"].isin(carrier["dot_number"]).all()),
        "every classification row has a census carrier":
            bool(classification["dot_number"].isin(carrier["dot_number"]).all()),
        "no negative counts": bool(all((carrier[c].dropna() >= 0).all() for c in COUNT_COLS)),
    }
    known = carrier[["power_units", "truck_units", "bus_units"]].notna().all(axis=1)
    over = known & (carrier["truck_units"] + carrier["bus_units"] > carrier["power_units"])
    checks["truck_units + bus_units <= power_units (where all known and consistent)"] = f"{over.sum():,} rows exceed"
    cdl = carrier["total_cdl"] > carrier["total_drivers"]
    checks["total_cdl <= total_drivers"] = f"{cdl.sum():,} rows exceed"
    for name, ok in checks.items():
        log(f"  {'OK  ' if ok is True else ('FAIL' if ok is False else 'INFO')} {name}" + ("" if isinstance(ok, bool) else f": {ok}"))
    log(f"  status mix: {carrier['status_code'].value_counts(dropna=False).to_dict()}")
    log(f"  active carriers (status A and entity type C): {carrier['is_active_carrier'].sum():,}")

    if CRASH_VEHICLE.exists():
        log("\n[6] Linkage to the crash data (crash_vehicle.dot_number -> census_carrier)")
        v = pd.read_parquet(CRASH_VEHICLE, columns=["crash_id", "dot_number"])
        v = v[v["dot_number"].notna()]
        v["in_census"] = v["dot_number"].isin(carrier["dot_number"])
        log(f"  crash vehicles with a USDOT number found in the census: {v['in_census'].mean():.2%} "
            f"({(~v['in_census']).sum():,} not found)")
        crash_dots = pd.Series(v["dot_number"].unique())
        log(f"  distinct crash carriers found in the census: {crash_dots.isin(carrier['dot_number']).mean():.2%}")
    else:
        log(f"\n[6] Skipped crash linkage check ({CRASH_VEHICLE} not found)")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counties = pd.read_csv(COUNTY_URL, sep="|", dtype=str)
    df = clean(load_raw(), counties)

    log("\n[3] Child tables")
    cargo = build_cargo(df)
    classification = build_classification(df)
    carrier = df[CARRIER_COLS].reset_index(drop=True)

    log("\n[4] Rollups")
    agg_state, agg_month = build_aggs(carrier)
    log(f"  agg_census_state: {len(agg_state):,} states | agg_census_added_month: {len(agg_month):,} state-months")

    validate(carrier, cargo, classification)

    log("\n[7] Writing parquet")
    write(carrier, "census_carrier")
    write(cargo, "census_cargo")
    write(classification, "census_classification")
    write(agg_state, "agg_census_state")
    write(agg_month, "agg_census_added_month")
    for name, d in build_dims(counties).items():
        write(d, name)

    (OUT_DIR / "_build_report.txt").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
