import requests
from datetime import date
from pathlib import Path
from tqdm import tqdm


def download(url, out):

    with requests.get(url, stream=True, timeout=40) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)) or None

        with open(out, "wb") as f, tqdm(
            total = total, unit="B", unit_scale=True, desc=out.name
        ) as bar:
            for chunk in r.iter_content(chunk_size=1024*1024):
                f.write(chunk)
                bar.update(len(chunk))


url_crash = "https://data.transportation.gov/api/v3/views/az4n-8mr2/export.csv?accessType=DOWNLOAD"
out_crash = Path("FMCSA_data") / f"crash_{date.today()}.csv"
out.parent.mkdir(parents=True, exist_ok=True)

download(url_crash,out_crash)


#DO NOT RUN THIS ITS A WHOLE 2GB

print("Saved", out)