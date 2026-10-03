"""Apply the final TOP-opener model to the StateParl v3 corpus.

Builds chair blocks the way top_change_classification_v1_v2.ipynb does for training: all `pre`
paragraphs, in protocol order, joined into one block while consecutive, also across gaps made
up only of `nsc` rows; paragraphs joined with "\\n". If the model card has window settings (G0w),
blocks longer than window_tokens are split into windows at paragraph boundaries and a block gets
its highest window score. Decision: opener if the logit margin is >= 0.

Output (DATA_ROOT/measurement/top_change/):
  top_openers_<model>_since_<date>.parquet  one row per block: protocol_id, state, period, date,
      start_pos, end_pos, n_paragraphs, paragraph_ids, n_windows, content, score, is_opener_pred
  top_openers_<model>_since_<date>.json     model card, input counts, run date
Scores are written in chunks to a _chunks/ folder first, so an interrupted run resumes.

Usage:
  norm_env/bin/python measurement/top_change/score_corpus.py --model g0_block_cv_pool --since 2009-09-29
  norm_env/bin/python measurement/top_change/score_corpus.py --model g0_block_cv_pool --check
(run from the repo root; g0_block_cv_pool is the production model)
--check rebuilds blocks and windows for the 95 labelled protocols and compares them with the
notebook's, then scores the test split with the given cv_pool model and compares with the stored
test predictions. Nothing is written.
"""
import argparse, json, os, pickle, sys, time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

TC = Path(__file__).resolve().parent
sys.path.insert(0, str(TC.parents[1] / "preprocessing"))
from nsc_rule_parser import get_data_root

CHUNK_UNITS = 50_000
PARAGRAPHS = get_data_root() / "raw" / "stateparl_v3_parquet" / "stateparl_v3_paragraphs.parquet"


def load_paragraphs(since=None, protocols=None):
    """pre and nsc paragraphs, optionally from `since` on or for some protocols only."""
    filters = [("affiliation", "in", ["pre", "nsc"])]
    if protocols is not None:
        filters.append(("protocol_id", "in", sorted(protocols)))
    rows = pd.read_parquet(PARAGRAPHS, filters=filters, columns=[
        "paragraph_id", "protocol_id", "state", "period", "date", "protocol_position", "affiliation", "content"])
    if since is not None:
        rows = rows[pd.to_datetime(rows["date"]) >= pd.Timestamp(since)]
    return rows.sort_values(["protocol_id", "protocol_position"]).reset_index(drop=True)


def build_blocks(rows):
    """Chair blocks: a pre paragraph joins the previous one if they are in the same protocol and
    every position strictly between them is an nsc row (none for adjacent positions). Same rule
    as the notebook's nsc bridging. Returns (blocks, pre paragraphs with their block number)."""
    protocol_code = pd.factorize(rows["protocol_id"])[0].astype(np.int64)
    key = protocol_code * 10_000_000 + rows["protocol_position"].to_numpy()
    is_pre = (rows["affiliation"] == "pre").to_numpy()
    nsc_keys = np.sort(key[~is_pre])
    pre = rows[is_pre].reset_index(drop=True)
    pre_key, pre_code, pre_pos = key[is_pre], protocol_code[is_pre], pre["protocol_position"].to_numpy()
    nsc_before = np.searchsorted(nsc_keys, pre_key)  # nsc rows before each pre row (keys sort by protocol, position)
    same_protocol = np.r_[False, pre_code[1:] == pre_code[:-1]]
    gap = np.r_[0, pre_pos[1:] - pre_pos[:-1] - 1]
    nsc_between = np.r_[0, nsc_before[1:] - nsc_before[:-1]]
    joins = same_protocol & (gap == nsc_between)
    pre["block"] = np.cumsum(~joins) - 1
    blocks = pre.groupby("block", sort=True).agg(
        protocol_id=("protocol_id", "first"), state=("state", "first"), period=("period", "first"),
        date=("date", "first"), start_pos=("protocol_position", "min"), end_pos=("protocol_position", "max"),
        n_paragraphs=("protocol_position", "size"), paragraph_ids=("paragraph_id", list),
        content=("content", "\n".join)).reset_index(drop=True)
    return blocks, pre


def build_units(blocks, pre, tokenizer, card):
    """One unit per block, or per window for blocks over window_tokens (G0w). Same packing as
    block_windows() in the notebook: fill paragraph by paragraph, repeat up to
    window_overlap_paragraphs trailing paragraphs (at most window_overlap_tokens) in the next."""
    if "window_tokens" not in card:
        return pd.DataFrame({"block": np.arange(len(blocks)), "text": blocks["content"].to_numpy()})
    limit, overlap_n, overlap_tokens = card["window_tokens"], card["window_overlap_paragraphs"], card["window_overlap_tokens"]
    n_tokens = np.array([len(ids) for ids in tokenizer(pre["content"].tolist(), add_special_tokens=False)["input_ids"]]) + 1
    block_tokens = np.bincount(pre["block"].to_numpy(), weights=n_tokens) - 1
    content = pre["content"].to_numpy()
    starts = np.r_[0, np.flatnonzero(np.diff(pre["block"].to_numpy())) + 1]
    units_block, units_text = [], []
    for block, text in enumerate(blocks["content"].to_numpy()):
        if block_tokens[block] <= limit:
            units_block.append(block); units_text.append(text)
            continue
        first = starts[block]
        tokens = n_tokens[first:first + blocks["n_paragraphs"].iat[block]]
        start = 0
        while True:
            end = start + 1
            while end < len(tokens) and tokens[start:end + 1].sum() - 1 <= limit:
                end += 1
            units_block.append(block); units_text.append("\n".join(content[first + start:first + end]))
            if end == len(tokens):
                break
            k = overlap_n
            while k > 0 and (end - k <= start or tokens[end - k:end].sum() > overlap_tokens):
                k -= 1
            start = end - k
    return pd.DataFrame({"block": units_block, "text": units_text})


class Scorer:
    """Logit margins with the training cell's batching: length-sorted batches under a token
    budget, padded to a multiple of pad_multiple, MPS cache released every 10 batches."""

    def __init__(self, model_dir, card):
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(self.device).eval()
        self.card = card

    def free(self):
        if self.device.type == "mps":
            torch.mps.empty_cache()

    @torch.no_grad()
    def margins(self, texts):
        enc = self.tokenizer(list(texts), truncation=True, max_length=self.card["max_length"])
        lengths = np.array([len(ids) for ids in enc["input_ids"]])
        order = np.argsort(lengths, kind="stable")
        batches, current = [], []
        for i in order:
            if current and ((len(current) + 1) * lengths[i] > self.card["tokens_per_batch"]
                            or len(current) == self.card["max_batch_size"]):
                batches.append(current); current = []
            current.append(i)
        if current:
            batches.append(current)
        out = np.empty(len(lengths))
        for k, batch in enumerate(batches, start=1):
            features = [{"input_ids": enc["input_ids"][i], "attention_mask": enc["attention_mask"][i]} for i in batch]
            inputs = self.tokenizer.pad(features, pad_to_multiple_of=self.card["pad_multiple"], return_tensors="pt").to(self.device)
            logits = self.model(**inputs).logits.float()
            out[batch] = (logits[:, 1] - logits[:, 0]).cpu().numpy()
            if k % 10 == 0:
                self.free()
        self.free()
        return out


def block_scores(units, unit_margins, n_blocks):
    scores = pd.Series(unit_margins).groupby(units["block"].to_numpy()).max()
    assert len(scores) == n_blocks
    return scores.to_numpy()


def check(model_dir, card, scorer):
    """Compare blocks, windows and scores with the notebook's on the labelled protocols."""
    nb = json.load(open(TC / "top_change_classification_v1_v2.ipynb"))
    ids = [c.get("id") for c in nb["cells"]]
    g = {}
    exec("from sklearn.metrics import precision_recall_fscore_support, f1_score, accuracy_score, roc_auc_score, "
         "average_precision_score, matthews_corrcoef", g)  # imported in an earlier notebook cell
    cwd = os.getcwd(); os.chdir(TC)
    for cid in ["2c7423aa", "679939eb", "b7d4c2a9", "82fa0764", "c77fcd37", "614a6873", "f1a2b3c5"]:
        exec("".join(nb["cells"][ids.index(cid)]["source"]), g)
    os.chdir(cwd)
    contributions = g["contributions"]
    rows = load_paragraphs(protocols=set(contributions["protocol_id"]))
    blocks, pre = build_blocks(rows)
    print(f"labelled protocols: {len(blocks)} blocks here, {len(contributions)} in the notebook")
    nb_blocks = contributions.sort_values(["protocol_id", "start_pos"]).reset_index(drop=True)
    assert len(blocks) == len(nb_blocks)
    for column in ["protocol_id", "start_pos", "end_pos", "n_paragraphs", "content"]:
        assert (blocks[column].to_numpy() == nb_blocks[column].to_numpy()).all(), column
    print("blocks: protocol, positions, paragraph counts and text identical to the notebook's")

    if "window_tokens" in card:
        for column, nb_name in [("window_tokens", "WINDOW_TOKENS"), ("window_overlap_paragraphs", "WINDOW_OVERLAP_PARAGRAPHS"),
                                ("window_overlap_tokens", "WINDOW_OVERLAP_TOKENS")]:
            assert card[column] == g[nb_name], column
        units = build_units(blocks, pre, scorer.tokenizer, card)
        nb_units = g["block_windows"](nb_blocks)
        assert len(units) == len(nb_units)
        assert (units["block"].to_numpy() == nb_units["block"].to_numpy()).all()
        assert (units["text"].to_numpy() == nb_units["text"].to_numpy()).all()
        print(f"windows: {len(units)} units, identical to the notebook's block_windows()")
    else:
        units = build_units(blocks, pre, scorer.tokenizer, card)

    variant = "windows" if "window_tokens" in card else "block"
    stored = pickle.load(open(TC / f"bert_test_predictions_{variant}.pkl", "rb"))
    assert stored["config"]["train_sha256"] == card["train_sha256"], "stored test predictions come from another model"
    pred = stored["predictions"]
    key = blocks["protocol_id"] + "_" + blocks["start_pos"].astype(str) + "-" + blocks["end_pos"].astype(str)
    test_blocks = np.flatnonzero(key.isin(pred["contribution_id"]).to_numpy())
    test_units = units[units["block"].isin(test_blocks)]
    margins = scorer.margins(test_units["text"])
    scores = pd.Series(margins).groupby(test_units["block"].to_numpy()).max()
    scores.index = key.to_numpy()[scores.index]
    diff = np.abs(scores.loc[pred["contribution_id"]].to_numpy() - pred["score"].to_numpy())
    agree = ((scores.loc[pred["contribution_id"]].to_numpy() >= 0).astype(int) == pred["pred"].to_numpy()).mean()
    print(f"test split ({len(pred)} blocks): max |score difference| {diff.max():.2e}, decisions agree {agree:.4f}")
    assert diff.max() < 1e-3 and agree == 1.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="folder name under DATA_ROOT/models/top_change/")
    parser.add_argument("--since", default="2009-09-29")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    model_dir = get_data_root() / "models" / "top_change" / args.model
    card = json.loads((model_dir / "model_card.json").read_text())
    assert not card.get("smoke_test"), "smoke-test model"
    scorer = Scorer(model_dir, card)
    print(f"model {args.model}: {card['variant']}, trained {card['trained_on']} on {card['n_train_blocks']} blocks, device {scorer.device}")
    if args.check:
        check(model_dir, card, scorer)
        return

    out_dir = get_data_root() / "measurement" / "top_change"
    stem = f"top_openers_{args.model}_since_{args.since}"
    chunk_dir = out_dir / f"{stem}_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows = load_paragraphs(since=args.since)
    blocks, pre = build_blocks(rows)
    units = build_units(blocks, pre, scorer.tokenizer, card)
    n_windowed = int((units["block"].value_counts() > 1).sum())
    print(f"{len(pre):,} pre paragraphs in {blocks['protocol_id'].nunique():,} protocols -> {len(blocks):,} blocks, "
          f"{len(units):,} units ({n_windowed:,} blocks windowed), {time.time() - t0:.0f}s")

    n_chunks = -(-len(units) // CHUNK_UNITS)
    margins = np.empty(len(units))
    for c in range(n_chunks):
        lo, hi = c * CHUNK_UNITS, min((c + 1) * CHUNK_UNITS, len(units))
        path = chunk_dir / f"chunk_{c:04d}_{lo}_{hi}.npy"
        if path.exists():
            margins[lo:hi] = np.load(path)
            continue
        t = time.time()
        margins[lo:hi] = scorer.margins(units["text"].iloc[lo:hi])
        np.save(path, margins[lo:hi])
        done = hi / len(units)
        print(f"chunk {c + 1}/{n_chunks}: {hi - lo} units in {(time.time() - t) / 60:.1f} min ({100 * done:.0f}% done)", flush=True)

    blocks["n_windows"] = units.groupby("block").size().to_numpy()
    blocks["score"] = block_scores(units, margins, len(blocks))
    blocks["is_opener_pred"] = (blocks["score"] >= 0).astype(int)
    blocks.insert(0, "block_id", blocks["protocol_id"] + "_" + blocks["start_pos"].astype(str) + "-" + blocks["end_pos"].astype(str))
    assert blocks["block_id"].is_unique
    blocks.to_parquet(out_dir / f"{stem}.parquet", index=False)
    meta = {"model": args.model, "model_card": {k: v for k, v in card.items() if k != "training_log"},
            "since": args.since, "input": str(PARAGRAPHS), "n_pre_paragraphs": int(len(pre)),
            "n_protocols": int(blocks["protocol_id"].nunique()), "n_blocks": int(len(blocks)),
            "n_units": int(len(units)), "n_blocks_windowed": n_windowed,
            "n_predicted_openers": int(blocks["is_opener_pred"].sum()), "scored_on": datetime.now().isoformat(timespec="seconds"),
            "device": str(scorer.device), "decision": "opener if score (max logit margin over a block's units) >= 0"}
    (out_dir / f"{stem}.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"wrote {out_dir / (stem + '.parquet')}: {len(blocks):,} blocks, {meta['n_predicted_openers']:,} predicted openers, "
          f"{(time.time() - t0) / 60:.0f} min")


if __name__ == "__main__":
    main()
