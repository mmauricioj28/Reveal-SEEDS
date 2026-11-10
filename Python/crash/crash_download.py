"""Step 1 of the Crash pipeline: pull the FMCSA Crash File (2015+) from data.transportation.gov
straight into Parquet (no CSV is ever written to disk).

One raw Parquet per crash year is written to FMCSA_data_raw/crash_parquet/ so a failed year can be
re-run alone; years that already exist are skipped. Every column is kept as text here - typing and
cleaning happen in crash_build_parquet.py.
Run from the repo root:  python Python/crash_download.py  [first_year] [last_year]
"""
import io
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
import requests

URL_CRASH = "https://data.transportation.gov/resource/aayw-vxb3.csv"
OUT_DIR = Path("FMCSA_data_raw") / "crash_parquet"

FIRST_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2015
LAST_YEAR = int(sys.argv[2]) if len(sys.argv) > 2 else date.today().year
WORKERS = 6  # years downloaded at once; the API serves each request at roughly 10 MB/min

# Every column except: VIN + license plate (vehicle identifiers we don't need for state-level
# analysis), carrier street (address PII), and fields that are empty or pure system bookkeeping
# (crash_carrier_city_code, crash_colonia, upload_first_byte, snet_version_number, snet_sequence_id).
COLUMNS = [
    "crash_id", "report_state", "report_number", "report_date", "report_time", "report_seq_no",
    "dot_number", "ci_status_code", "final_status_date", "location", "city_code", "city", "state",
    "county_code", "truck_bus_ind", "trafficway_id", "access_control_id", "road_surface_condition_id",
    "cargo_body_type_id", "gvw_rating_id", "vehicle_lic_state", "vehicle_hazmat_placard",
    "weather_condition_id", "vehicle_configuration_id", "light_condition_id", "hazmat_released",
    "agency", "vehicles_in_accident", "fatalities", "injuries", "tow_away", "federal_recordable",
    "state_recordable", "transaction_code", "transaction_date", "upload_dot_number",
    "upload_search_indicator", "upload_date", "add_date", "change_date", "crash_carrier_id",
    "crash_carrier_name", "crash_carrier_city", "crash_carrier_state", "crash_carrier_zip_code",
    "docket_number", "crash_carrier_interstate", "no_id_flag", "state_number",
    "state_issuing_number", "crash_event_seq_id_desc",
]


def download_year(year):
    out = OUT_DIR / f"crash_{year}.parquet"
    if out.exists():
        return f"skip {out} (already exists)"
    params = {"$query": f"""
        SELECT {", ".join(COLUMNS)}
        WHERE report_date >= '{year}0101' AND report_date <= '{year}1231'
        LIMIT 10000000000
    """}  # LIMIT defaults at 1000 so force LIMIT over
    buf = io.BytesIO()  # the CSV response only lives in memory
    with requests.get(URL_CRASH, params=params, stream=True, timeout=300) as r:
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
    years = range(FIRST_YEAR, LAST_YEAR + 1)
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(download_year, y): y for y in years}
        for f in as_completed(futures):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # keep the other years going; re-run to retry just the failures
                print(f"FAILED {futures[f]}: {e}", flush=True)
