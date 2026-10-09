#ALL THIS HAS BEEN MOVED TO FMCSA_DOWNLOAD_DATE.ipynb


import requests
from datetime import date
from pathlib import Path
from tqdm import tqdm


def download(url, out, params=None): #Download function with a SQL function
    with requests.get(url, params=params, stream=True, timeout=40) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)) or None

        with open(out, "wb") as f, tqdm(
            total = total, unit="B", unit_scale=True, desc=out.name
        ) as bar:
            for chunk in r.iter_content(chunk_size=1024*1024):
                f.write(chunk)
                bar.update(len(chunk))


url_crash = "https://data.transportation.gov/resource/aayw-vxb3.csv"
out_crash = Path("FMCSA_data_raw") / f"crash_{date.today()}.csv"
out_crash.parent.mkdir(parents=True, exist_ok=True)

params = {"$query" : """
    SELECT crash_id,
    report_date,
    change_date,
    upload_date,
    add_date,
    transaction_date
    
    WHERE report_date > '20091231' AND
    report_date < '20200101'
    LIMIT 10000000000
    """
    #All dates after 2009-12-31, LIMIT defaults at 1000 so force LIMIT over
}
download(url_crash,out_crash,params)


print("Saved", out_crash)