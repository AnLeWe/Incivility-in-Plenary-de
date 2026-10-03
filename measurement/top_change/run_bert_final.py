"""Final (production) G0 model: ModernGBERT_134M, block only, optionally windowed (G0w), trained
in a fresh process like run_bert_cv.py.

Runs the notebook's data-preparation, split and fold cells and the definitions of the BERT cell
(52d5f001, everything before its training loop), so tokenizer, batching and settings are the
ones used in the CV. Then it trains on all of cv_pool, scores the held-out test split once and
writes bert_test_predictions_<block|windows>.pkl next to the notebook (read by its final section).
That evaluated model is the production model; the test split is never trained on.

Training uses the CV recipe with a fixed number of epochs instead of early stopping (the
early-stopping slices are part of cv_pool, so no data is left for one): N_EPOCHS = 3, the mean of G0's best epochs over the five
CV folds (2, 2, 4, 5, 2). The learning-rate schedule is planned over MAX_EPOCHS = 5 as in the
CV and training stops after epoch 3, so the model is trained the way the CV models were up to
their third epoch. Decision rule: logit margin >= 0. Weights, tokenizer and a model_card.json
(config, model revision, data fingerprint, training log) go to
DATA_ROOT/models/top_change/<g0_block|g0w_windows>_cv_pool/, which score_corpus.py reads.

With --windows, blocks longer than WINDOW_TOKENS are split into windows (window cell f1a2b3c5),
trained on as separate units and scored by their highest window margin (G0w).

Usage: norm_env/bin/python measurement/top_change/run_bert_final.py [--windows] [--smoke]
--smoke trains on a small subset for one epoch and writes nothing outside a scratch folder.
"""
import hashlib, json, os, pickle, sys, time
from datetime import datetime
from pathlib import Path
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.show = lambda *a, **k: plt.close("all")
TC = os.path.dirname(os.path.abspath(__file__))
os.chdir(TC)
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.metrics import precision_recall_fscore_support, f1_score, accuracy_score, roc_auc_score, average_precision_score, matthews_corrcoef
from sklearn.model_selection import StratifiedGroupKFold

SMOKE = "--smoke" in sys.argv
VARIANT = "windows" if "--windows" in sys.argv else False
NAME = "g0w_windows" if VARIANT else "g0_block"
N_EPOCHS = 3
TEST_PREDICTIONS_PATH = Path(f"bert_test_predictions_{'windows' if VARIANT else 'block'}.pkl")

nb = json.load(open("top_change_classification_v1_v2.ipynb"))
ids = [c.get("id") for c in nb["cells"]]
g = globals()
# data preparation, split, rule baseline, nested-CV helpers, frozen folds, windows for long blocks
for cid in ["2c7423aa", "679939eb", "b7d4c2a9", "82fa0764", "c77fcd37", "614a6873", "13fee2e5", "cd2b933d", "f1a2b3c5"]:
    print(f"--- running cell {ids.index(cid)} ({cid})", flush=True)
    exec("".join(nb["cells"][ids.index(cid)]["source"]), g)
# BERT cell: settings and helper definitions only, not its CV training loop
bert_source = "".join(nb["cells"][ids.index("52d5f001")]["source"])
print(f"--- running cell {ids.index('52d5f001')} (52d5f001) up to its training loop", flush=True)
exec(bert_source[:bert_source.index("bert_oofs = {}")], g)

from nsc_rule_parser import get_data_root

# All labelled blocks: cv_pool first (same order as in the CV), then the test split
test_pool = contributions[contributions["split"] == "test"].reset_index(drop=True)
full = pd.concat([cv_pool, test_pool], ignore_index=True)
cv_idx = np.arange(len(cv_pool))
test_idx = np.arange(len(cv_pool), len(full))
assert full["contribution_id"].is_unique
assert not set(cv_pool["protocol_id"]) & set(test_pool["protocol_id"])
assert len(full) == len(contributions)
print(f"cv_pool {len(cv_idx)} blocks ({cv_pool['protocol_id'].nunique()} protocols, {int(cv_pool['is_opener'].sum())} openers), "
      f"test {len(test_idx)} blocks ({test_pool['protocol_id'].nunique()} protocols, {int(test_pool['is_opener'].sum())} openers)")

# rebind the globals the BERT helpers read (X and cv_windows in encode, Y and the units in
# training, encodings/lengths in batching)
X = full["content"]
Y = full["is_opener"].astype(int).to_numpy()
cv_windows = block_windows(full)
encodings, lengths = encode(VARIANT)
unit_block, Y_unit = training_units(VARIANT)
print(f"{NAME}: {len(Y_unit)} training units for {len(full)} blocks; tokens per unit: median {int(np.median(lengths))}, 95th pct {int(np.percentile(lengths, 95))}, "
      f"at cap {100 * (lengths == MAX_LENGTH).mean():.1f}%")


def data_fingerprint(idx):
    """SHA-256 over the rows in idx: protocol, positions, label and block text, in order. The
    windows are derived from these, so the same blocks give the same windows."""
    h = hashlib.sha256()
    for i in idx:
        h.update(f"{full['protocol_id'].iloc[i]}\t{full['start_pos'].iloc[i]}\t{full['end_pos'].iloc[i]}\t{Y[i]}\t".encode())
        h.update(X.iloc[i].encode() + b"\x00")
    return h.hexdigest()


def train_fixed_epochs(fit_idx, n_epochs):
    """train_with_early_stopping from the BERT cell without the early-stopping slice: same
    seed, class weights, optimizer, schedule (planned over MAX_EPOCHS) and batching, stopped
    after n_epochs. The weights after the last epoch are the model."""
    torch.manual_seed(BERT_SEED)
    rng = np.random.default_rng(BERT_SEED)
    model = AutoModelForSequenceClassification.from_pretrained(BERT_NAME, num_labels=2, revision=MODEL_REVISION).to(device)
    fit_units = units_of(fit_idx)
    counts = np.bincount(Y_unit[fit_units], minlength=2)
    class_weights = torch.tensor(len(fit_units) / (2.0 * counts), dtype=torch.float32, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    n_steps = MAX_EPOCHS * len(make_batches(fit_units))
    scheduler = get_linear_schedule_with_warmup(optimizer, int(WARMUP_SHARE * n_steps), n_steps)
    for epoch in range(1, n_epochs + 1):
        start = time.time()
        model.train()
        losses = []
        for k, batch_idx in enumerate(make_batches(fit_units, rng), start=1):
            logits = model(**collate(batch_idx)).logits.float()
            labels = torch.tensor(Y_unit[batch_idx], device=device)
            loss = F.cross_entropy(logits, labels, weight=class_weights)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            losses.append(loss.item())
            if k % 10 == 0:
                free_gpu_cache()
        log(f"    epoch {epoch}: mean training loss {np.mean(losses):.4f}, lr now {scheduler.get_last_lr()[0]:.2e}, "
            f"{(time.time() - start) / 60:.1f} min")
    return model


def fit_summary(idx, margins):
    """Scores on the training rows themselves: a sanity check, not an estimate."""
    pred = (margins >= 0).astype(int)
    p, r, f, _ = precision_recall_fscore_support(Y[idx], pred, labels=[0, 1], zero_division=0)
    return f"P={p[1]:.3f} R={r[1]:.3f} F1={f[1]:.3f} macro-F1={(f[0] + f[1]) / 2:.3f}"


def config_for(fit_idx):
    windows = {"window_tokens": WINDOW_TOKENS, "window_overlap_paragraphs": WINDOW_OVERLAP_PARAGRAPHS,
               "window_overlap_tokens": WINDOW_OVERLAP_TOKENS,
               "scoring": "blocks over window_tokens are split into windows; block margin = max over windows",
               "n_train_units": int(len(units_of(fit_idx)))} if VARIANT else {}
    return {**windows, "model": BERT_NAME, "model_revision": MODEL_REVISION,
            "variant": "G0w: block only, windowed" if VARIANT else "G0: block only",
            "max_length": MAX_LENGTH, "epochs": N_EPOCHS, "schedule_planned_over_epochs": MAX_EPOCHS,
            "lr": LR, "weight_decay": WEIGHT_DECAY, "warmup_share": WARMUP_SHARE, "grad_clip": GRAD_CLIP,
            "seed": BERT_SEED, "tokens_per_batch": TOKENS_PER_BATCH, "max_batch_size": MAX_BATCH_SIZE,
            "pad_multiple": PAD_MULTIPLE, "loss": "class-weighted cross-entropy",
            "decision": "opener if logit[1] - logit[0] >= 0", "bridge_nsc_gaps": BRIDGE_NSC_GAPS,
            "n_train_blocks": int(len(fit_idx)), "n_train_openers": int(Y[fit_idx].sum()),
            "n_train_protocols": int(full["protocol_id"].iloc[fit_idx].nunique()),
            "train_sha256": data_fingerprint(fit_idx), "smoke_test": SMOKE}


def save_model(model, out_dir, config):
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    card = {**config, "trained_on": datetime.now().isoformat(timespec="seconds"), "device": str(device),
            "torch": torch.__version__, "transformers": __import__("transformers").__version__,
            "training_log": training_log}
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=1, ensure_ascii=False))
    log(f"saved model to {out_dir}")


models_root = get_data_root() / "models" / "top_change"
if SMOKE:
    models_root = Path(os.environ.get("SMOKE_DIR", "/tmp")) / "top_change_smoke"
    N_EPOCHS = 1
    rng_smoke = np.random.default_rng(20261002)
    cv_idx = np.sort(rng_smoke.choice(cv_idx, 400, replace=False))
    test_idx = np.sort(rng_smoke.choice(test_idx, 200, replace=False))
    TEST_PREDICTIONS_PATH = models_root / TEST_PREDICTIONS_PATH.name

training_log = []
fit_idx = cv_idx
config = config_for(fit_idx)
log(f"train on cv_pool ({len(fit_idx)} blocks, {int(Y[fit_idx].sum())} openers) for {N_EPOCHS} epochs, device {device}")
model = train_fixed_epochs(fit_idx, N_EPOCHS)
log(f"  on its own training rows: {fit_summary(fit_idx, predict_margins(model, fit_idx))}")
margins = predict_margins(model, test_idx)
predictions = test_pool.iloc[test_idx - len(cv_pool)][["contribution_id", "protocol_id", "state", "start_pos", "end_pos"]].copy()
predictions["y_true"] = Y[test_idx]
predictions["score"] = margins
predictions["pred"] = (margins >= 0).astype(int)
log(f"  scored the test split once: {len(test_idx)} blocks")
TEST_PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(TEST_PREDICTIONS_PATH, "wb") as f:
    pickle.dump({"predictions": predictions.reset_index(drop=True), "config": config,
                 "test_sha256": data_fingerprint(test_idx), "log": training_log}, f)
log(f"  wrote {TEST_PREDICTIONS_PATH}")
save_model(model, models_root / f"{NAME}_cv_pool", config)

print("finished", flush=True)
