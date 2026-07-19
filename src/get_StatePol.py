import os
from pathlib import Path

import requests
import pandas as pd

# fetch current version
version_url = "https://raw.githubusercontent.com/StatePol/Database/main/VERSION"
database_version = requests.get(version_url).text.strip().splitlines()[0]

# construct base URL
base_url = "https://raw.githubusercontent.com/StatePol/Database/main/_data/database"

# resolve DATA_ROOT
data_root = os.environ.get("DATA_ROOT")
if not data_root:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
    data_root = os.environ.get("DATA_ROOT")
if not data_root:
    raise SystemExit("DATA_ROOT not set. Copy .env.example to .env and set DATA_ROOT.")

output_dir = Path(data_root) / "raw" / "statepol"
output_dir.mkdir(parents=True, exist_ok=True)

# download function
def download_csv(file_name):
    csv_url = f"{base_url}/{file_name}_{database_version}.csv"
    df = pd.read_csv(csv_url)
    out_path = output_dir / f"{file_name}_{database_version}.csv"
    df.to_csv(out_path, index=False)
    print(f"saved {out_path.name}  ({len(df):,} rows)")
    return df

# download data
politician = download_csv("politician")
mandate = download_csv("mandate")
ppg = download_csv("ppg")
ppg_leadership = download_csv("ppgleadership")
presidency = download_csv("presidency")
committee = download_csv("committee")
cabinet = download_csv("cabinet")

print(f"\nDone. Saved 7 files to {output_dir}")