"""
Build a Fließtext from the 2018 Brandenburg (bb) parliamentary session (2018-06-27).

Logic:
  - Filter paragraphs_2018.csv for state='bb' and date='2018-06-27'
  - Sort by sequence_number
  - Start from the earliest row whose speaker_id begins with 'bb_'
  - Concatenate speaker_name + content for all rows from that point on
  - Save result as fliesstext_bb_20180627.txt
"""

import csv
import os
from pathlib import Path

DATA_ROOT = Path(os.environ["DATA_ROOT"])
DATA_FILE = DATA_ROOT / "paragraphs_2018.csv"
OUT_FILE  = DATA_ROOT / "fliesstext_bb_20180627.txt"

TARGET_DATE  = "2018-06-27"
TARGET_STATE = "bb"

with open(DATA_FILE, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Filter and sort
bb_rows = [
    r for r in rows
    if r["state"] == TARGET_STATE and r["date"] == TARGET_DATE
]
bb_rows.sort(key=lambda r: int(r["sequence_number"]))

# Find earliest row with a bb_ speaker_id
start_idx = next(
    (i for i, r in enumerate(bb_rows) if r["speaker_id"].startswith("bb_")),
    0,
)

print(f"Total BB rows for {TARGET_DATE}: {len(bb_rows)}")
print(f"Earliest bb_ speaker at sequence_number: {bb_rows[start_idx]['sequence_number']}")
print(f"  speaker_id : {bb_rows[start_idx]['speaker_id']}")
print(f"  speaker    : {bb_rows[start_idx]['speaker_name']}")
print(f"  protocol   : {bb_rows[start_idx]['protocol']}")

# Build Fließtext
parts = []
for r in bb_rows[start_idx:]:
    name    = r["speaker_name"].strip()
    content = r["content"].strip()
    if not content:
        continue
    affiliation = r["affiliation"].strip()
    if name and affiliation:
        parts.append(f"{name} ({affiliation}): {content}")
    elif name:
        parts.append(f"{name}: {content}")
    else:
        parts.append(content)

fliesstext = " ".join(parts)

OUT_FILE.write_text(fliesstext, encoding="utf-8")
print(f"\nFließtext saved to: {OUT_FILE}")
print(f"Characters: {len(fliesstext):,}")
print(f"Words: {len(fliesstext.split()):,}")
print(f"\nPreview (first 400 chars):\n{fliesstext[:400]}")
