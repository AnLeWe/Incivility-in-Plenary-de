#!/usr/bin/env python3
"""Regenerate requirements.txt from actual imports in src/, labelling/, measurement/.

Requires pipreqs on PATH (e.g. `uv tool install pipreqs`). Scans only the Python
source dirs (not analysis/, paper/, etc., which are R) via a temp dir of symlinks,
since pipreqs takes a single path.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["src", "labelling", "measurement"]
REQUIREMENTS = REPO_ROOT / "requirements.txt"

# Packages pandas needs as I/O engines (pd.read_excel, etc.) without any file ever
# writing `import openpyxl`. Import-scanning can't see these, so pipreqs would
# silently drop them; keep them pinned here regardless of what pipreqs finds.
ALWAYS_INCLUDE = {"openpyxl"}


def main() -> int:
    if shutil.which("pipreqs") is None:
        print("pipreqs not found on PATH — install with `uv tool install pipreqs`", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for scan_dir in SCAN_DIRS:
            src_dir = REPO_ROOT / scan_dir
            if not src_dir.is_dir():
                continue
            dst_dir = tmp_path / scan_dir
            dst_dir.mkdir(parents=True, exist_ok=True)
            for f in list(src_dir.glob("*.py")) + list(src_dir.glob("*.ipynb")):
                if f.stat().st_size > 0:  # skip empty stub notebooks (invalid JSON)
                    (dst_dir / f.name).symlink_to(f)

        result = subprocess.run(
            [
                "pipreqs",
                str(tmp_path),
                "--scan-notebooks",
                "--mode",
                "no-pin",
                "--force",
                "--savepath",
                str(REQUIREMENTS),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, file=sys.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode

    found = {line.strip().lower() for line in REQUIREMENTS.read_text().splitlines() if line.strip()}
    packages = sorted(found | ALWAYS_INCLUDE)
    REQUIREMENTS.write_text("\n".join(packages) + "\n")

    print(f"Updated {REQUIREMENTS.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
