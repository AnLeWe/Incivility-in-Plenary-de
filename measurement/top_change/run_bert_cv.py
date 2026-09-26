"""Train the notebook's BERT cell (52d5f001) in a fresh process: executes the notebook's own
data-preparation and fold cells, then the BERT cell source unchanged. Writes
bert_oof_checkpoint.pkl next to the notebook, which the notebook's BERT cell then loads."""
import json, os, pickle, sys
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
nb = json.load(open("top_change_classification_v1_v2.ipynb"))
ids = [c.get("id") for c in nb["cells"]]
g = globals()
for cid in ["2c7423aa", "679939eb", "b7d4c2a9", "82fa0764", "c77fcd37", "614a6873", "13fee2e5", "cd2b933d", "52d5f001"]:
    print(f"--- running cell {ids.index(cid)} ({cid})", flush=True)
    exec("".join(nb["cells"][ids.index(cid)]["source"]), g)
print("BERT CV finished", flush=True)
