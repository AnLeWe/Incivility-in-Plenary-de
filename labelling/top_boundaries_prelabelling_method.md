# Pre-labelling method for TOP-opener gold data

The gold labels are the human annotator's: every row was reviewed and, where needed, corrected
by hand. To speed up the second half of the annotation, an LLM (Claude) produced pre-labels
first, following the workflow below; "I" in this file refers to that pre-labelling pass, not
to the final labels.

This documents the *process* of pre-labelling protocols in
`top_boundaries_opener_labels_v2.csv`. For the substantive decisions
(which topic a given kind of content gets, how to handle Einzelplan,
Fragestunde, etc.), see `top_boundaries_annotation_conventions.md` — this file is about
the mechanical workflow, not the judgment calls.

## 1. Find what's unlabelled

A protocol counts as "not yet labelled" if it has ≤1 row in the gold
file — i.e. only the auto-generated Sitzungseröffnung placeholder (or,
for a handful of continuation-day protocols, genuinely zero rows — see
§6). I find the next batch with:

```python
import pandas as pd
inp = pd.read_csv('labelling/top_boundaries_annotation_input_v2.csv')
lab = pd.read_csv('labelling/top_boundaries_opener_labels_v2.csv')
counts = lab.groupby('protocol_id').size()
remaining = [p for p in inp['protocol_id'].unique() if counts.get(p, 0) <= 1]
```

## 2. Dump the full candidate row set

For each protocol I pull every candidate row from
`top_boundaries_annotation_input_v2.csv` (not the raw parquet — the
input file is already the pre-filtered candidate boundary set) and
write it to a plain two-column scratch file: `start_pos<TAB>content`,
one row per line, in position order.

```python
sub = inp[inp['protocol_id'] == pid].sort_values('start_pos')
with open(f'.../scratchpad/{pid}_dump.txt', 'w') as f:
    for _, r in sub.iterrows():
        f.write(f"{r['start_pos']}\t{r['content']}\n")
```

**Critical gotcha:** when I *view* that file with the Read tool, Read
prepends its own sequential line count (`cat -n` style), so the
displayed line looks like `LINE_NUM<TAB>START_POS<TAB>CONTENT`. The
second column is the real `start_pos` — the one that goes in the CSV.
Confusing the two has caused real errors (writing openers to
completely wrong, unrelated rows). When in doubt, `cat` or `sed` the
raw scratch file in Bash instead of Read, so there's no extra numbering
column to misread.

## 3. Read the structure, not just the titles

I read the dump top to bottom and mentally segment it into
Tagesordnungspunkte (TOPs), using the chair's "Ich rufe Punkt X auf"
announcements as scaffolding — but the announcement line itself is
almost never the opener anchor. The anchor is the actual title/citation
line(s) that follow it (bill title, Antrag heading, Drucksache
citation). When a title is split across several candidate rows (title
text / "Gesetzentwurf der X" / "Drucksache Y" each as their own row,
usually because of a page-wrap in the source PDF), I anchor on the
first row that carries the actual descriptive title — not the bare
"Ich rufe Punkt X auf" line before it, and not a mid-block line after
it.

For content I can't judge from the title alone (Fragestunde exchanges,
short debate items, ambiguous topic calls), I pull the actual paragraph
text from the raw parquet:

```python
import os, pandas as pd
paras = pd.read_parquet(os.path.join(os.environ['DATA_ROOT'],
    'raw/stateparl_v3_parquet/stateparl_v3_paragraphs.parquet'))
g = paras[(paras['protocol_id']==pid) &
          (paras['protocol_position']>=X) &
          (paras['protocol_position']<=Y)].sort_values('protocol_position')
```

## 4. Decide four independent fields per opener row

`is_opener`, `type`, `sponsor`, and `topic` are decided separately —
a row can have a type without a topic (container headings), or share a
topic with sibling rows while having a distinct sponsor. I don't infer
one from another by default.

- **`is_opener`** — 1 only on the row where a genuinely new debate item
  starts. Bare `Fragestunde` / `Aktuelle Stunde` / `Aktuelle Debatte`
  container headings get `is_opener=0` with `type` tagged and no topic.
- **`type`** — the procedural instrument (Gesetzentwurf, Antrag,
  Mündliche Anfrage, Wahlvorschlag, Bericht, Stellungnahme, etc.),
  joined with `; ` when a row is more than one thing at once (e.g. a
  combined Bericht + Beschlussempfehlung).
- **`sponsor`** — who submitted it, joined with `"; "` **in source-text
  order**, not alphabetized. `/` is reserved for a party's own compound
  name (`FDP/DVP`), never for joining separate sponsors.
- **`topic`** — the debate's substance, from the fixed topic list (see
  `top_boundaries_annotation_conventions.md` for the full taxonomy and its edge
  cases).

## 5. Recurring structural patterns

- **Fragestunde bundling** — when the chair bundles multiple numbered
  questions under one announcement ("Fragen N und M zusammen"), each
  questioner still gets their own opener, anchored at their own
  content-start row (where they start reading their question), not at
  the shared announcement.
- **Joint-TOP bundling** — when several distinct Drucksache documents
  share one debate, each gets its own `is_opener=1` row *only if it has
  its own descriptive title/citation block*. A bare citation with no
  title of its own (`Änderungsantrag der Fraktion X – Drucksache Y –`,
  named only as a line item, not debated separately) does **not** get
  a separate opener — it's folded into the main item's row. The same
  logic distinguishes titled Entschließungsanträge (own opener) from
  bare Änderungsanträge (no separate opener).
- **Wahlvorschlag exception** — competing candidate slates under one
  Wahl-TOP are the one case where bare citations *do* each get their
  own opener (established from multiple prior examples), since each
  slate is voted on individually. Established precedent: only the
  first Wahlvorschlag row in a TOP carries the `topic=Personalwahl`
  value; sibling Wahlvorschlag rows in the same TOP leave `topic`
  blank rather than repeating it.
- **Continuation-day protocols** — a protocol whose annotation-input
  candidates start well after position 1, mid-speech, with no
  Sitzungseröffnung anywhere, is not a data bug — it's a second (or
  later) day of a multi-day sitting where TOP 1 was already in
  progress from the previous day's protocol. There's genuinely no
  opener to anchor at position 1 in that case; I leave it out rather
  than fabricating one. I confirm this by checking the raw parquet at
  the low end of the position range for mid-sentence/mid-debate content
  rather than a "Sitzung eröffnet" statement.

## 6. Verification before writing

Before committing decisions to the CSV, for anything non-obvious I
cross-check precedent: has this exact kind of content (a phrase, a
Drucksache pattern, a topic-adjacent case) already been classified
somewhere else in the corpus? I search across both gold files by
joining `is_opener==1` rows back to their raw paragraph text:

```python
merged = openers.merge(paras[['protocol_id','protocol_position','content']],
    left_on=['protocol_id','start_pos'],
    right_on=['protocol_id','protocol_position'], how='left')
hits = merged[merged['content'].str.contains(PATTERN, case=False, na=False)]
```

This is what settles calls like "is a tender-irregularity Anfrage
`Finanzen` or `Korruption und Amtsmissbrauch`" or "does `Jugendkriminalität`
go under `Jugend und Familie` or `Innere Sicherheit`" — by precedent,
not by re-deriving the rule from scratch each time.

## 7. Writing to the gold file

**The gold file always contains every candidate row for a completed
protocol, not just the decided openers.** Non-decision rows get
`is_opener=0` and blank `type`/`sponsor`/`topic`. I verified this by
checking that finished protocols' row counts exactly match their
candidate counts in the input file (e.g. `nw_16_76`: 267 candidates,
267 gold rows). Writing only the opener rows (skipping the rest) is a
mistake I've made and had to rebuild from — always expand to the full
candidate set before writing.

```python
sub = inp[inp['protocol_id'] == pid].sort_values('start_pos')
rows = []
for _, r in sub.iterrows():
    decision = decisions.get((pid, int(r['start_pos'])))
    is_op, typ, sponsor, topic = decision if decision else (0, None, None, None)
    rows.append({...})
```

## 8. Known failure modes (and how I catch them)

- **Row-index vs. start_pos confusion** (§2) — always verify anchor
  positions against a plain `cat`/`sed` view, never the Read tool's
  numbered view, before writing.
- **Sparse-only writes** (§7) — always check the candidate count
  matches the gold row count for a "finished" protocol.
- **Anchoring on the announcement line instead of the title line** —
  when a title block spans multiple candidate rows, double-check which
  one actually carries the descriptive content vs. which one is just
  "Ich rufe Punkt X auf:".
- **External editing collisions** — if the labelling GUI is left open
  on a protocol I've just written to, its next save can silently
  overwrite my changes with its own (possibly stale or partial) state.
  When something looks off after a write, re-read the file from disk
  and diff against what I intended before assuming either side is
  wrong.
