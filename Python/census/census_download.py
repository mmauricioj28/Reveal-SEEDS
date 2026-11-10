"""Step 1 of the Census pipeline: pull the FMCSA Company Census File (MCMIS) from data.transportation.gov
straight into Parquet (no CSV is ever written to disk).

The census is one row per USDOT number (~4.5M entities). It is split by DOT number range into
FMCSA_data_raw/census_parquet/census_<start>.parquet (about 250k rows each) so a failed chunk can be
re-run alone; chunks that already exist are skipped. Every column is kept as text here - typing and
cleaning happen in census_build_parquet.py.
Run from the repo root:  python Python/census_download.py
"""
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
import requests

URL_CENSUS = "https://data.transportation.gov/resource/az4n-8mr2.csv"
OUT_DIR = Path("FMCSA_data_raw") / "census_parquet"

WORKERS = 6        # chunks downloaded at once
CHUNK = 250_000    # DOT numbers per chunk; numbers are dense below ~4.6M
DENSE_END = 5_000_000
RANGES = [(start, start + CHUNK) for start in range(0, DENSE_END, CHUNK)] + [(DENSE_END, 100_000_000)]

# Columns follow docs/variable_selection.md plus fields useful for the dashboard / COVID questions.
# Left out: phone, fax, cell, email, street addresses, company officers (personal contact details),
# legal/DBA names (often a person's name for owner-operators), mailing address, legacy/unused fields.
COLUMNS = [
    "dot_number", "add_date", "mcs150_date", "status_code", "carrier_operation", "carship", "classdef",
    "business_org_id", "phy_city", "phy_state", "phy_zip", "phy_cnty", "phy_country",
    "power_units", "truck_units", "bus_units", "fleetsize",
    "owntruck", "owntract", "owntrail", "owncoach",
    "total_drivers", "total_cdl", "driver_inter_total", "total_intrastate_drivers",
    "interstate_within_100_miles", "interstate_beyond_100_miles",
    "intrastate_within_100_miles", "intrastate_beyond_100_miles",
    "mcs150_mileage", "mcs150_mileage_year", "hm_ind",
    "safety_rating", "safety_rating_date", "review_type", "review_date",
    "docket1prefix", "docket1",
    "crgo_genfreight", "crgo_household", "crgo_metalsheet", "crgo_motoveh", "crgo_drivetow", "crgo_logpole",
    "crgo_bldgmat", "crgo_mobilehome", "crgo_machlrg", "crgo_produce", "crgo_liqgas", "crgo_intermodal",
    "crgo_passengers", "crgo_oilfield", "crgo_livestock", "crgo_grainfeed", "crgo_coalcoke", "crgo_meat",
    "crgo_garbage", "crgo_usmail", "crgo_chem", "crgo_drybulk", "crgo_coldfood", "crgo_beverages",
    "crgo_paperprod", "crgo_utility", "crgo_farmsupp", "crgo_construct", "crgo_waterwell", "crgo_cargoothr",
    "crgo_cargoothr_desc",
]


def download_range(start, end):
    out = OUT_DIR / f"census_{start:08d}.parquet"
    if out.exists():
        return f"skip {out} (already exists)"
    params = {"$query": f"""
        SELECT {", ".join(COLUMNS)}
        WHERE dot_number >= {start} AND dot_number < {end}
        LIMIT 10000000000
    """}  # LIMIT defaults at 1000 so force LIMIT over
    buf = io.BytesIO()  # the CSV response only lives in memory
    with requests.get(URL_CENSUS, params=params, stream=True, timeout=600) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            buf.write(chunk)
    buf.seek(0)
    table = pv.read_csv(buf, convert_options=pv.ConvertOptions(
        column_types={c: pa.string() for c in COLUMNS}, strings_can_be_null=True))
    tmp = out.with_suffix(".parquet.tmp")  # rename at the end so a killed run never leaves a half file
    pq.write_table(table, tmp, compression="zstd")
    tmp.replace(out)
    return f"Saved {out}  ({table.num_rows:,} rows, {out.stat().st_size / 1e6:.1f} MB)"


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(download_range, s, e): (s, e) for s, e in RANGES}
        for f in as_completed(futures):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # keep the other chunks going; re-run to retry just the failures
                print(f"FAILED {futures[f]}: {e}", flush=True)
