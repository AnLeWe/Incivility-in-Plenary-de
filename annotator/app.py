import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys
import uuid
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from annotator.config import LABELS, DEFINITIONS, DATASETS, OUTPUT_FILE

st.set_page_config(page_title="Zivilität Annotator", layout="wide")

st.markdown("""
<style>
li:first-child [data-testid="stTooltipHoverTarget"] .e1bi6yfx1 { font-size: 0 !important; }
li:first-child [data-testid="stTooltipHoverTarget"] .e1bi6yfx1::after { content: "Alle auswählen"; font-size: 0.875rem; }
</style>
""", unsafe_allow_html=True)

ANNOTATOR_DIR = os.path.dirname(os.path.abspath(__file__))
ID_FILE  = os.path.join(ANNOTATOR_DIR, ".annotator_id")
POS_FILE = os.path.join(ANNOTATOR_DIR, ".annotator_positions.json")

# ── annotator identity ─────────────────────────────────────────────────────────

def get_annotator_id():
    if os.path.exists(ID_FILE):
        return open(ID_FILE).read().strip()
    new_id = str(uuid.uuid4())[:8]
    open(ID_FILE, "w").write(new_id)
    return new_id

ANNOTATOR_ID = get_annotator_id()

# ── position persistence ───────────────────────────────────────────────────────

def load_positions() -> dict:
    if os.path.exists(POS_FILE):
        try:
            return json.loads(open(POS_FILE).read())
        except Exception:
            return {}
    return {}

def save_position(scope_key: str, idx: int):
    positions = load_positions()
    positions[f"{ANNOTATOR_ID}_{scope_key}"] = idx
    open(POS_FILE, "w").write(json.dumps(positions))

# ── data loading ───────────────────────────────────────────────────────────────

@st.cache_data
def load_input(dataset_key):
    path = DATASETS[dataset_key]["input_file"]
    df = pd.read_csv(path, low_memory=False)
    if "para_id" not in df.columns and "id" in df.columns:
        df = df.rename(columns={"id": "para_id"})
    df["para_id"] = df["para_id"].astype(str)
    return df.reset_index(drop=True)

def load_output():
    if os.path.exists(OUTPUT_FILE):
        return pd.read_csv(OUTPUT_FILE, dtype={"para_id": str, "dataset": str})
    cols = ["para_id", "dataset", "state", "politeness", "moral",
            "justificatory", "interjection", "notes",
            "annotator_id", "annotator_name", "timestamp"]
    return pd.DataFrame(columns=cols)

def save_annotation(para_id, dataset, state, politeness, moral,
                    justificatory, interjection, notes, annotator_name):
    out = load_output()
    row = {
        "para_id": str(para_id),
        "dataset": dataset,
        "state": state,
        "politeness": politeness,
        "moral": moral,
        "justificatory": justificatory,
        "interjection": "|".join(interjection) if isinstance(interjection, list) and interjection else "neither",
        "notes": notes,
        "annotator_id": ANNOTATOR_ID,
        "annotator_name": annotator_name.strip() or None,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    # append — never delete old rows so revision history is preserved
    out = pd.concat([out, pd.DataFrame([row])], ignore_index=True)
    out.to_csv(OUTPUT_FILE, index=False)

# ── sidebar: identity + dataset + state ───────────────────────────────────────

with st.sidebar:
    st.subheader("Annotator:in")
    st.caption(f"Ihre ID: `{ANNOTATOR_ID}`")
    annotator_name = st.text_input("Ihr Name (optional)")

    st.divider()
    def dataset_label(k):
        note = DATASETS[k].get("note", "")
        return f"{DATASETS[k]['label']}  —  {note}" if note else DATASETS[k]["label"]

    dataset_key = st.radio("Datensatz", list(DATASETS.keys()), format_func=dataset_label)

    df_full = load_input(dataset_key)
    states = sorted(df_full["state"].unique())
    selected_state = st.selectbox("Bundesland", states)

    st.divider()
    st.subheader("Konzeptdefinitionen")
    st.caption("Die Dimensionen schließen sich nicht gegenseitig aus und können in Kombination auftreten. z.B. kann eine Äußerung höflich *und* moralisch inzivil sein.")
    for dim, info in LABELS.items():
        with st.expander(info["label"]):
            st.caption(DEFINITIONS[dim])

# ── filter to selected state ───────────────────────────────────────────────────

df = df_full[df_full["state"] == selected_state].reset_index(drop=True)
out = load_output()

# most recent annotation per para_id for this annotator + dataset + state
_mask = (
    (out["annotator_id"] == ANNOTATOR_ID) &
    (out["dataset"] == dataset_key) &
    (out["state"] == selected_state)
)
out_here = out[_mask].copy()
# keep only the latest entry per para_id for coded_ids / pre-fill
out_latest = (
    out_here.sort_values("timestamp")
            .drop_duplicates(subset="para_id", keep="last")
    if len(out_here) > 0
    else out_here
)
coded_ids: set[str] = set(out_latest["para_id"].tolist())

total   = len(df)
n_coded = len(coded_ids)

# ── resume position ────────────────────────────────────────────────────────────

scope_key = f"idx_{dataset_key}_{selected_state}"
if scope_key not in st.session_state:
    saved_positions = load_positions()
    saved_idx = saved_positions.get(f"{ANNOTATOR_ID}_{scope_key}")
    if saved_idx is not None:
        st.session_state[scope_key] = min(int(saved_idx), max(total - 1, 0))
    else:
        # first time: jump to first uncoded row
        uncoded = df[~df["para_id"].isin(coded_ids)]
        st.session_state[scope_key] = int(uncoded.index[0]) if len(uncoded) > 0 else 0

if "saved_msg" not in st.session_state:
    st.session_state.saved_msg = ""

# ── sidebar continued: progress + jump ────────────────────────────────────────

with st.sidebar:
    st.divider()
    st.metric("Kodiert", f"{n_coded} / {total}")
    st.progress(n_coded / total if total > 0 else 0)

    st.divider()
    jump = st.number_input("Springe zu Zeile", min_value=0,
                           max_value=max(total - 1, 0),
                           value=st.session_state[scope_key], step=1)
    if st.button("Los"):
        st.session_state[scope_key] = int(jump)
        save_position(scope_key, int(jump))
        st.session_state.saved_msg = ""
        st.rerun()

# ── navigation helpers ─────────────────────────────────────────────────────────

def go_to(i):
    new_idx = max(0, min(i, total - 1))
    st.session_state[scope_key] = new_idx
    save_position(scope_key, new_idx)
    st.session_state.saved_msg = ""

def context_para(offset):
    i = st.session_state[scope_key] + offset
    if i < 0 or i >= total:
        return None
    row     = df.iloc[i]
    current = df.iloc[st.session_state[scope_key]]
    return row if row["protocol"] == current["protocol"] else None

# ── main display ───────────────────────────────────────────────────────────────

idx     = st.session_state[scope_key]
current = df.iloc[idx]
prev_row = context_para(-1)
next_row = context_para(+1)

# pre-fill from most recent saved annotation for this paragraph
existing_rows = out_latest[out_latest["para_id"] == str(current["para_id"])]
has_existing  = len(existing_rows) > 0

def get_existing(col):
    if not has_existing or col not in existing_rows.columns:
        return None
    val = existing_rows.iloc[0][col]
    return None if pd.isna(val) else val

# how many times has this paragraph been annotated (revision count)
revision_count = len(out_here[out_here["para_id"] == str(current["para_id"])])

# header
col_left, col_right = st.columns([3, 1])
with col_left:
    rev_label = f"  ·  überarbeitet {revision_count}×" if revision_count > 1 else ""
    st.markdown(f"### Row {idx} / {total - 1}  —  {selected_state.upper()} · {dataset_key}{rev_label}")
with col_right:
    aff = str(current.get("affiliation", "")).upper()
    spk = current.get("speaker_name", "")
    st.markdown(f"**{aff}** · {spk} · {current['date']} · `{current['protocol']}` Folge {current['sequence_number']}")

# three-column layout: prev | current | next
col_prev, col_curr, col_next = st.columns([1, 2, 1])

with col_prev:
    if prev_row is not None:
        with st.container(border=True, height=260):
            st.caption(f"◀ {str(prev_row.get('affiliation','')).upper()} · {prev_row.get('speaker_name','')}")
            st.markdown(f"<p style='color:#888;font-size:0.85em'>{prev_row['content']}</p>",
                        unsafe_allow_html=True)
    else:
        st.caption("◀ Kein vorheriger Absatz")

with col_curr:
    if has_existing:
        saved = existing_rows.iloc[0]
        label_summary = "  ·  ".join(
            f"**{LABELS[d]['label']}**: {saved.get(d, '—')}"
            for d in LABELS if d in existing_rows.columns
        )
        st.success(f"Bereits annotiert  —  {label_summary}")
    with st.container(border=True, height=260):
        st.markdown(f"{current['content']}")
        display_cols = [c for c in DATASETS[dataset_key]["display_cols"] if c in df.columns]
        if display_cols:
            parts = []
            for c in display_cols:
                val = current.get(c)
                if pd.notna(val):
                    fmt = f"{val:.3f}" if isinstance(val, float) else str(val)
                    parts.append(f"**{c}**: {fmt}")
            if parts:
                st.caption("Modell-Labels — " + "  ·  ".join(parts))

with col_next:
    if next_row is not None:
        with st.container(border=True, height=260):
            st.caption(f"▶ {str(next_row.get('affiliation','')).upper()} · {next_row.get('speaker_name','')}")
            st.markdown(f"<p style='color:#888;font-size:0.85em'>{next_row['content']}</p>",
                        unsafe_allow_html=True)
    else:
        st.caption("▶ Kein folgender Absatz")

st.markdown("---")

# ── annotation form ───────────────────────────────────────────────────────────

with st.form("annotation_form", clear_on_submit=False):
    form_cols = st.columns(4)
    selections = {}
    for i, (dim, info) in enumerate(LABELS.items()):
        with form_cols[i]:
            existing_val = get_existing(dim)
            if info.get("multi"):
                empty_label = info.get("empty_label", "neither")
                # empty selection or saved "neither" → default to []
                if isinstance(existing_val, str) and existing_val and existing_val != empty_label:
                    default_multi = [v for v in existing_val.split("|") if v in info["options"]]
                else:
                    default_multi = []
                selections[dim] = st.multiselect(
                    info["label"], options=info["options"],
                    default=default_multi,
                    placeholder=empty_label,
                    key=f"multi_{dim}_{scope_key}_{idx}",
                )
            else:
                default_idx = (info["options"].index(existing_val)
                               if existing_val in info["options"] else 0)
                selections[dim] = st.radio(
                    info["label"], options=info["options"],
                    index=default_idx, key=f"radio_{dim}_{scope_key}_{idx}",
                )

    notes_default = get_existing("notes") or ""
    notes = st.text_area("Notizen (optional)", value=str(notes_default), height=50,
                         key=f"notes_{scope_key}_{idx}")

    nav1, nav2, nav3, nav4 = st.columns([1, 1, 1, 2])
    with nav1:
        prev_btn = st.form_submit_button("← Zurück", use_container_width=True)
    with nav2:
        save_btn = st.form_submit_button("💾 Speichern & weiter", use_container_width=True, type="primary")
    with nav3:
        save_stay = st.form_submit_button("💾 Speichern (bleiben)", use_container_width=True)
    with nav4:
        if st.session_state.saved_msg:
            st.success(st.session_state.saved_msg)

if save_btn:
    save_annotation(current["para_id"], dataset_key, selected_state,
                    selections["politeness"], selections["moral"],
                    selections["justificatory"], selections["interjection"],
                    notes, annotator_name)
    st.session_state.saved_msg = f"Zeile {idx} gespeichert"
    go_to(idx + 1)
    st.rerun()

if save_stay:
    save_annotation(current["para_id"], dataset_key, selected_state,
                    selections["politeness"], selections["moral"],
                    selections["justificatory"], selections["interjection"],
                    notes, annotator_name)
    st.session_state.saved_msg = f"Zeile {idx} gespeichert"
    st.rerun()

if prev_btn:
    go_to(idx - 1)
    st.rerun()
