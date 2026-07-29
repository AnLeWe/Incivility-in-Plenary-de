"""Score paragraphs with a given Ollama model. Two modes:

1. Fixed-sample mode (--sample-file, default): for inter-rater comparison and the
   context-ablation study (v1 baseline vs. +-1 window vs. ordnungsruf flag vs. both).
   Usage: norm_env/bin/python score_with_model.py --model gemma4:12b --variant window_flag

2. Full-state mode (--state XX): scores every classifiable paragraph for one state's
   +-1yr-AfD-entry window (build_classification_pool()), not a fixed sample -- for an actual
   full-corpus run. Checkpointed: writes each row to disk as it's scored (not just at the
   end) and resumes from wherever it left off if the output file already has rows in it, so
   a multi-day run survives being restarted (e.g. Colab's 24h session cap).
   Usage: norm_env/bin/python score_with_model.py --model gemma4:12b --variant window_flag \\
       --state by --platform-label colab_t4

Reads DATA_ROOT/measurement/pilot_sample_n500_seed20260723.csv by default in sample-file
mode (the exact same 500 paragraphs qwen3:14b-q4_K_M already scored, see
impoliteness_pilot.ipynb) so every model's predictions are directly comparable
paragraph-for-paragraph. Saves
DATA_ROOT/measurement/impoliteness_pilot_predictions_{today}_{model-slug}_n{n}[_{variant}].csv,
same naming convention as the notebook (variant suffix omitted for the baseline, so the
existing n=2000 4-model comparison files keep their original names).

Full-state mode saves DATA_ROOT/measurement/impoliteness_full_{state}_{model-slug}_{variant}.csv
-- deliberately NOT date-stamped, since the same file is read back on every resume.

--variant controls what build_context() output actually reaches the prompt (see
impoliteness_lib.build_prompt's docstring for the format):
  baseline    - no context at all (v1 behavior -- the four already-run n=2000 files are this)
  window      - +-1 paragraph window, ordnungsruf_follows suppressed
  flag        - ordnungsruf_follows only, no window
  window_flag - both (the real build_context() output, v2 as designed)
All non-baseline variants use SYSTEM_PROMPT v2 (see PROMPT_VERSION) since the window/flag
explanation text is part of the system prompt itself, not just the per-call content.
"""
import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import ollama
import pandas as pd

from impoliteness_lib import (
    PROMPT_VERSION, build_classification_pool, build_context, build_position_index,
    build_prompt, parse_response,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.runtime_log import RuntimeLogger

SEED = 20260723
NUM_CTX = 40960
VARIANTS = ("baseline", "window", "flag", "window_flag")
V1_PROMPT_VERSION = "v1_codebook-binary_2026-07-27"


def _prompt_version_for(variant: str) -> str:
    return V1_PROMPT_VERSION if variant == "baseline" else PROMPT_VERSION


def _ablate(context: dict, variant: str) -> dict | None:
    if variant == "baseline":
        return None
    if variant == "window":
        return {"prev": context["prev"], "next": context["next"], "ordnungsruf_follows": False}
    if variant == "flag":
        return {"prev": None, "next": None, "ordnungsruf_follows": context["ordnungsruf_follows"]}
    return context  # window_flag


def _score_one(model: str, text: str, context: dict | None, prompt_version: str) -> dict:
    response = ollama.chat(
        model=model,
        messages=build_prompt(text, context, prompt_version=prompt_version),
        think=False,
        format="json",
        options={"temperature": 0, "seed": SEED, "num_ctx": NUM_CTX},
    )
    return parse_response(response["message"]["content"])


def run_sample_file(args, data_root: str) -> None:
    sample_path = Path(args.sample_file) if args.sample_file else (
        Path(data_root) / "measurement" / "pilot_sample_n500_seed20260723.csv"
    )
    sample = pd.read_csv(sample_path)
    print(f"Loaded fixed sample: {len(sample):,} rows from {sample_path}")

    position_index = None
    context_by_paragraph = {}
    if args.variant != "baseline":
        print("Building classification pool for context lookups...")
        pool = build_classification_pool(data_root, verbose=False)
        position_index = build_position_index(pool.merged)
        pool_by_id = pool.dedup.set_index("paragraph_id")
        for pid in sample["paragraph_id"]:
            if pid in pool_by_id.index:
                row = pool_by_id.loc[pid]
                row = row.iloc[0] if isinstance(row, pd.DataFrame) else row
                context_by_paragraph[pid] = build_context(row, position_index)

    run_date = date.today().isoformat()
    model_slug = args.model.replace(":", "-").replace(".", "-")
    suffix = "" if args.variant == "baseline" else f"_{args.variant}"
    out_name = f"impoliteness_pilot_predictions_{run_date}_{model_slug}_n{len(sample)}{suffix}.csv"
    out_path = Path(data_root) / "measurement" / out_name

    with RuntimeLogger(
        platform_label=args.platform_label,
        runtime="ollama",
        task_type="prediction",
        experiment=f"impoliteness context-ablation ({args.variant})",
        model=args.model,
        n_items=len(sample),
        seed=SEED,
        temperature=0,
        prompt_version=_prompt_version_for(args.variant),
        output_path=str(out_path),
        extra={"num_ctx": NUM_CTX, "sample_file": str(sample_path), "variant": args.variant},
    ):
        records = []
        start_time = time.time()
        for i, row in sample.iterrows():
            full_context = context_by_paragraph.get(row["paragraph_id"])
            context = _ablate(full_context, args.variant) if full_context else None
            parsed = _score_one(args.model, row["text_to_classify"], context, _prompt_version_for(args.variant))
            records.append({
                "paragraph_id": row["paragraph_id"],
                "state": row["state"],
                "period": row["period"],
                "date": row["date"],
                "affiliation": row["affiliation"],
                "content": row["text_to_classify"],
                "impolite": parsed["impolite"],
                "reason": parsed["reason"],
                "model_name": args.model,
                "variant": args.variant,
            })
            if (i + 1) % 25 == 0:
                elapsed = time.time() - start_time
                avg = elapsed / (i + 1)
                remaining = avg * (len(sample) - (i + 1))
                print(f"  {i + 1}/{len(sample)} scored -- {elapsed / 60:.1f} min elapsed, "
                      f"avg {avg:.1f}s/call, ~{remaining / 60:.1f} min remaining")

        total_elapsed = time.time() - start_time
        predictions = pd.DataFrame(records)
        n_unparsed = predictions["impolite"].isna().sum()
        print(f"Scored {len(predictions):,} paragraphs in {total_elapsed / 60:.1f} min "
              f"({total_elapsed / len(predictions):.1f}s/paragraph avg); "
              f"{n_unparsed} unparseable responses")

        predictions["run_date"] = run_date
        out_path.parent.mkdir(parents=True, exist_ok=True)
        predictions.to_csv(out_path, index=False)
        print(f"Saved -> {out_path}")


def run_full_state(args, data_root: str) -> None:
    scope = args.state or "all"
    print(f"Building classification pool (scope={scope})...")
    pool = build_classification_pool(data_root, verbose=False)
    position_index = build_position_index(pool.merged) if args.variant != "baseline" else None

    rows = pool.dedup if not args.state else pool.dedup[pool.dedup["state"] == args.state]
    rows = rows.copy()
    rows["segment_idx"] = rows["segment_idx"].fillna(-1)
    rows = rows.sort_values(["protocol_id", "protocol_position"])
    print(f"{len(rows):,} classifiable rows for scope={scope}")

    model_slug = args.model.replace(":", "-").replace(".", "-")
    out_name = f"impoliteness_full_{scope}_{model_slug}_{args.variant}.csv"
    out_path = Path(data_root) / "measurement" / out_name

    done_keys = set()
    if out_path.exists():
        done = pd.read_csv(out_path, usecols=["paragraph_id", "segment_idx"])
        done_keys = set(zip(done["paragraph_id"], done["segment_idx"].fillna(-1)))
        print(f"Resuming {out_path.name}: {len(done_keys):,} rows already scored")

    is_done = rows.apply(lambda r: (r["paragraph_id"], r["segment_idx"]) in done_keys, axis=1)
    todo = rows[~is_done]
    print(f"{len(todo):,} rows remaining this run")

    write_header = not out_path.exists()
    with RuntimeLogger(
        platform_label=args.platform_label,
        runtime="ollama",
        task_type="prediction",
        experiment=f"impoliteness full-corpus (scope={scope}, variant={args.variant})",
        model=args.model,
        n_items=len(todo),
        seed=SEED,
        temperature=0,
        prompt_version=_prompt_version_for(args.variant),
        output_path=str(out_path),
        extra={
            "num_ctx": NUM_CTX, "state": args.state, "variant": args.variant,
            "already_scored_at_start": len(done_keys),
        },
    ):
        start_time = time.time()
        for i, (_, row) in enumerate(todo.iterrows()):
            context = build_context(row, position_index) if position_index is not None else None
            context = _ablate(context, args.variant) if context else None
            parsed = _score_one(args.model, row["text_to_classify"], context, _prompt_version_for(args.variant))

            record = pd.DataFrame([{
                "paragraph_id": row["paragraph_id"],
                "segment_idx": row["segment_idx"],
                "state": row["state"],
                "date": row["date"],
                "affiliation": row["affiliation"],
                "content": row["text_to_classify"],
                "impolite": parsed["impolite"],
                "reason": parsed["reason"],
                "model_name": args.model,
                "variant": args.variant,
            }])
            record.to_csv(out_path, mode="a", header=write_header, index=False)
            write_header = False

            if (i + 1) % 25 == 0:
                elapsed = time.time() - start_time
                avg = elapsed / (i + 1)
                remaining = avg * (len(todo) - (i + 1))
                print(f"  {i + 1}/{len(todo)} scored this session -- {elapsed / 60:.1f} min "
                      f"elapsed, avg {avg:.1f}s/call, ~{remaining / 3600:.1f}h remaining "
                      f"this session")

        print(f"Session done: scored {len(todo):,} rows -> {out_path} "
              f"({len(done_keys) + len(todo):,}/{len(rows):,} total)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Ollama model tag, e.g. gemma4:12b")
    parser.add_argument("--variant", choices=VARIANTS, default="baseline")
    parser.add_argument(
        "--sample-file", default=None,
        help="Fixed-sample mode: defaults to DATA_ROOT/measurement/pilot_sample_n500_seed20260723.csv",
    )
    parser.add_argument(
        "--state", default=None,
        help="Restricts full-corpus mode to one state's +-1yr-AfD-entry window (e.g. 'by'). "
             "Implies --full-corpus.",
    )
    parser.add_argument(
        "--full-corpus", action="store_true",
        help="Full-corpus mode instead of sample-file mode: scores every classifiable "
             "paragraph (all states, or just --state if given), checkpointed/resumable -- "
             "for the actual full-corpus run rather than the fixed n=500/n=2000 sample.",
    )
    parser.add_argument(
        "--platform-label", default="mac_m5_local",
        help="Device tag for the runtime log, e.g. mac_m5_local / colab_t4 / hiwi_pc_rtx4070ti",
    )
    args = parser.parse_args()

    data_root = os.environ.get("DATA_ROOT")
    if not data_root:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv())
        data_root = os.environ["DATA_ROOT"]

    if args.full_corpus or args.state:
        run_full_state(args, data_root)
    else:
        run_sample_file(args, data_root)


if __name__ == "__main__":
    main()
