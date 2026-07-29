"""Cumulative cross-platform, cross-experiment runtime log.

One JSON line per run, appended to DATA_ROOT/logs/runtime_log.jsonl (JSONL rather than CSV
since the schema will keep growing as new platforms/runtimes show up -- e.g. a Colab run's
GPU-tier field doesn't exist for a local Mac run -- and JSONL tolerates that without every
row needing every column). Covers any compute run: LLM prediction/scoring, model
fine-tuning/tuning, data prep, evaluation -- across any device (this Mac, the Windows PC,
Colab, Kaggle, a cluster later).

Usage:
    from utils.runtime_log import RuntimeLogger

    with RuntimeLogger(
        platform_label="mac_m5_local",
        runtime="ollama",
        task_type="prediction",
        experiment="impoliteness interrater comparison",
        model="gemma4:12b",
        n_items=500,
        seed=20260723,
        temperature=0,
        prompt_version="v1_codebook-binary_2026-07-27",
        output_path=str(out_path),
        extra={"num_ctx": 40960},
    ):
        ... run the actual scoring/tuning here ...

Auto-captured (best-effort, never raises -- a detection failure just leaves that field None):
device specs (hostname/OS/CPU/RAM), git commit + dirty flag, Ollama version + `ollama ps`
snapshot (what else is loaded/running, so GPU contention like the 2026-07-28 benchmark
mix-up gets caught automatically instead of relying on remembering to check), start/end
time, duration, status (success/failed) and the exception message on failure.
"""
import json
import os
import platform as _platform
import socket
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _device_details() -> dict:
    details = {
        "hostname": _safe(socket.gethostname),
        "os": _safe(_platform.platform),
        "processor": _safe(_platform.processor),
    }
    if _platform.system() == "Darwin":
        details["cpu_brand"] = _safe(
            lambda: subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        )
    if psutil is not None:
        details["ram_gb"] = _safe(lambda: round(psutil.virtual_memory().total / 1e9, 1))
        details["cpu_count"] = _safe(psutil.cpu_count)
    return details


def _git_info(repo_dir: Path) -> dict:
    def _run(args):
        return subprocess.run(
            args, cwd=repo_dir, capture_output=True, text=True, check=True,
        ).stdout.strip()

    commit = _safe(lambda: _run(["git", "rev-parse", "HEAD"]))
    dirty = _safe(lambda: bool(_run(["git", "status", "--short"])))
    return {"commit": commit, "dirty": dirty}


def _ollama_snapshot() -> dict | None:
    version = _safe(
        lambda: subprocess.run(
            ["ollama", "--version"], capture_output=True, text=True, check=True,
        ).stdout.strip()
    )
    ps = _safe(
        lambda: subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, check=True,
        ).stdout.strip()
    )
    if version is None and ps is None:
        return None
    return {"version": version, "ps_snapshot": ps}


def _log_path() -> Path:
    data_root = os.environ.get("DATA_ROOT")
    if not data_root:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv())
        data_root = os.environ.get("DATA_ROOT", "")
    base = Path(data_root) / "logs" if data_root else Path(__file__).resolve().parent.parent / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base / "runtime_log.jsonl"


class RuntimeLogger:
    """Context manager: logs one JSONL record covering the wrapped block's runtime."""

    def __init__(
        self,
        platform_label: str,
        runtime: str,
        task_type: str,
        experiment: str,
        model: str | None = None,
        n_items: int | None = None,
        seed: int | None = None,
        temperature: float | None = None,
        prompt_version: str | None = None,
        output_path: str | None = None,
        extra: dict | None = None,
        log_path: str | None = None,
    ):
        self.platform_label = platform_label
        self.runtime = runtime
        self.task_type = task_type
        self.experiment = experiment
        self.model = model
        self.n_items = n_items
        self.seed = seed
        self.temperature = temperature
        self.prompt_version = prompt_version
        self.output_path = output_path
        self.extra = extra or {}
        self.log_path = Path(log_path) if log_path else _log_path()

    def __enter__(self):
        self.run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:6]}"
        self._t0 = time.time()
        self.start_time = datetime.now(timezone.utc).isoformat()
        self._repo_dir = Path(__file__).resolve().parent.parent
        self._device = _device_details()
        self._git = _git_info(self._repo_dir)
        self._ollama = _ollama_snapshot() if self.runtime == "ollama" else None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now(timezone.utc).isoformat()
        duration_sec = time.time() - self._t0
        status = "failed" if exc_type is not None else "success"
        notes = f"{exc_type.__name__}: {exc_val}" if exc_type is not None else None

        record = {
            "run_id": self.run_id,
            "platform_label": self.platform_label,
            "runtime": self.runtime,
            "task_type": self.task_type,
            "experiment": self.experiment,
            "model": self.model,
            "n_items": self.n_items,
            "seed": self.seed,
            "temperature": self.temperature,
            "prompt_version": self.prompt_version,
            "start_time": self.start_time,
            "end_time": end_time,
            "duration_sec": round(duration_sec, 1),
            "sec_per_item": round(duration_sec / self.n_items, 2) if self.n_items else None,
            "output_path": self.output_path,
            "status": status,
            "notes": notes,
            "device": self._device,
            "git": self._git,
            "ollama": self._ollama,
            "extra": self.extra,
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
        print(f"Logged run {self.run_id} ({status}, {duration_sec / 60:.1f} min) -> {self.log_path}")
        return False  # never swallow exceptions
