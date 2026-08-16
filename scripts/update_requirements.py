#!/usr/bin/env python3
"""Regenerate the project's requirements files from actual imports.

Two virtualenvs, two requirements files:

- `requirements.txt` — the project's main `norm_env` (Python 3.14). Built from imports in
  src/, labelling/, preprocessing/, utils/ and measurement/ *except* the topic-modeling
  files listed in TOPIC_MODELING_FILES.
- `requirements-topic-modeling.txt` — the dedicated `topic_modeling_env` (Python 3.11),
  which exists only because `gensim` cannot be installed on Python 3.14. Built from
  imports in TOPIC_MODELING_FILES only.

Requires pipreqs on PATH (e.g. `uv tool install pipreqs`). Scans only the Python source
dirs (not analysis/, paper/, etc., which are R) via a temp dir of symlinks, since pipreqs
takes a single path.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Keep in sync with .githooks/pre-commit's trigger pattern.
SCAN_DIRS = ["src", "labelling", "measurement", "preprocessing", "utils"]

# The only files that run on topic_modeling_env rather than norm_env. They live in
# measurement/ alongside norm_env code, so this is a file-level, not directory-level, split.
TOPIC_MODELING_FILES = [
    "measurement/topic_modeling_lib.py",
    "measurement/topic_modeling.ipynb",
    "measurement/test_topic_modeling_lib.py",
]

REQUIREMENTS = REPO_ROOT / "requirements.txt"
TOPIC_MODELING_REQUIREMENTS = REPO_ROOT / "requirements-topic-modeling.txt"

# Packages pandas needs as I/O engines (pd.read_excel, pd.read_parquet) without any file
# ever writing `import openpyxl`/`import pyarrow`. Import-scanning can't see these, so
# pipreqs would silently drop them; keep them pinned here regardless of what pipreqs finds.
ALWAYS_INCLUDE = {"openpyxl", "pyarrow"}
# Same idea for the topic-modeling venv: topic_modeling_lib.load_corpus reads the shared
# Parquet corpus, so that venv needs pyarrow too (it has no pd.read_excel caller).
TOPIC_MODELING_ALWAYS_INCLUDE = {"pyarrow"}


def _source_files(scan_dir: Path) -> list[Path]:
    """Python sources in a directory, skipping empty stub notebooks (invalid JSON)."""
    files = list(scan_dir.glob("*.py")) + list(scan_dir.glob("*.ipynb"))
    return sorted(f for f in files if f.stat().st_size > 0)


def _run_pipreqs(rel_paths: list[str], out_path: Path, always_include: set[str]) -> int:
    """Symlinks the given repo-relative files into a temp tree, runs pipreqs over it once,
    and writes the (sorted, allowlist-augmented) result to out_path."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for rel in rel_paths:
            src = REPO_ROOT / rel
            dst = tmp_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to(src)

        result = subprocess.run(
            [
                "pipreqs",
                str(tmp_path),
                "--scan-notebooks",
                "--mode",
                "no-pin",
                "--force",
                "--savepath",
                str(out_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, file=sys.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode

    found = {line.strip().lower() for line in out_path.read_text().splitlines() if line.strip()}
    packages = sorted(found | always_include)
    out_path.write_text("\n".join(packages) + "\n")

    print(f"Updated {out_path.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    if shutil.which("pipreqs") is None:
        print("pipreqs not found on PATH — install with `uv tool install pipreqs`", file=sys.stderr)
        return 1

    norm_env_files = []
    for scan_dir in SCAN_DIRS:
        src_dir = REPO_ROOT / scan_dir
        if not src_dir.is_dir():
            continue
        for f in _source_files(src_dir):
            rel = f"{scan_dir}/{f.name}"
            if rel not in TOPIC_MODELING_FILES:
                norm_env_files.append(rel)

    topic_modeling_files = [rel for rel in TOPIC_MODELING_FILES if (REPO_ROOT / rel).is_file()]

    returncode = _run_pipreqs(norm_env_files, REQUIREMENTS, ALWAYS_INCLUDE)
    if returncode != 0:
        return returncode

    return _run_pipreqs(
        topic_modeling_files, TOPIC_MODELING_REQUIREMENTS, TOPIC_MODELING_ALWAYS_INCLUDE
    )


if __name__ == "__main__":
    raise SystemExit(main())
