# Error analysis: TOP-change classifier

Interpretation of the ranked error-review tables in
`top_change_classification_v1_v2.ipynb` ("Ranked error-review table for D").
Model D is the TF-IDF word(1,3)+char(3,5) union with balanced LinearSVC and nested
C/threshold selection. Scores are out-of-fold. `distance` is the score minus that
fold's selected threshold.

Each reviewed case gets one of these verdicts:

- `model error`: the gold label is correct and the model is wrong
- `label error`: the gold label is wrong and needs fixing in
  `labelling/top_boundaries_opener_labels*.csv`
- `ambiguous`: the annotation conventions don't settle the case. Resolve it in
  `labelling/top_boundaries_annotation_conventions.md` first.

## BERT (ModernGBERT_134M + neighbouring-block context; 2026-09-26)

Same bridged blocks, frozen outer folds, pre-fix labels. Early stopping and threshold on
frozen inner fold 1, trained in a fresh process (`run_bert_cv.py`); notebook cells 85-90.

| | F1 | P | R | MCC | PR-AUC | FP | FN | question openers missed (of 226) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C | 0.886 | 0.874 | 0.908 | 0.873 | 0.924 | 123 | 90 | 54 |
| D | 0.881 | 0.879 | 0.892 | 0.867 | 0.948 | 117 | 105 | 71 |
| BERT | 0.917 | 0.932 | 0.907 | 0.907 | 0.965 | 63 | 89 | 55 |

- Best in every fold (per-fold F1 +0.01 to +0.05 over the better of C and D). FPs are halved
  at every block length. Misses stay at C's level.
- It fixes 44 FPs and 26 FNs that C and D share, and adds 14 FPs and 24 FNs of its own.
  Shared core wrong in all three: 38 FPs, 44 FNs.
- Several of its most confident "FPs" are label errors, i.e. BERT is right: hb_16_51/175,
  th_4_67/1, st_6_70/1, and newly sn_7_52/1789 ("Wir behandeln nun zwei Kleine Anfragen …
  Drucksache 7/9689: Geplante Regelung zu Mindestabständen von Windenergieanlagen …", False;
  the second Anfrage "… Drucksache 7/9690" at 1815 is False too).
- Fragestunde calls with no subject are now a conflict between states. BERT's most
  confident misses are BY/SN calls ("Nächste Frage: Herr Kollege Schieder.", by_15_52;
  "Herr Petzold, bitte; Frage Nr. 6.", sn_4_32). Its most confident FPs are NI calls with the
  same wording ("Die nächste Frage wird von Herrn Limburg … gestellt.", ni_16_37), which are
  labelled False as follow-ups in NI's Dringliche Anfragen. The same phrase means a new
  question in one state and a follow-up in another. A text model can't get both right
  without knowing the state or the sequence position, so the Fragestunde mode feature
  should include the state.
- Best epoch per fold 4, 2, 3, 2, 4. Folds 1 and 5 were still improving at epoch 4.

## Model comparison on nsc-bridged blocks (C, D, E; 2026-09-25)

Checkpoint of 2026-09-25 23:24: `BRIDGE_NSC_GAPS = True` (9,249 blocks, 7,541 in
cv_pool), frozen folds, labels as of the hh_20_34 fix. Pooled over folds:

| model | TP | FP | FN | P | R | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| C: word13 counts + balanced LogReg | 845 | 123 | 90 | 0.873 | 0.904 | 0.888 |
| D: tfidf union + balanced LinearSVC | 830 | 117 | 105 | 0.876 | 0.888 | 0.882 |
| E: tfidf union + unweighted LinearSVC | 834 | 120 | 101 | 0.874 | 0.892 | 0.883 |

These are not comparable to the unbridged numbers above, because the unit changed.

- D and E are the same model in practice: 7,530 of 7,541 predictions agree and the
  margin rank correlation is 0.984. Once the threshold is tuned, class weighting
  makes no difference. E adds nothing.
- C and D disagree a lot (margin rank correlation 0.665). A shared core of 81 FPs
  and 69 FNs is wrong in all three models. This is where the label fixes and
  structural fixes from this file apply, since changing the model does not touch
  it. The rest is model-specific: 39 FPs and 20 FNs only for C, and about 35 FPs and
  35 FNs for D (with E) but not C.
- C's own errors are long blocks with extreme margins, e.g. FP th_4_67/1457-1466
  (+7.3, "… Aussprache schließen. Wir kommen nun zur …") and FN st_3_60/941-1092
  (n=140, -1.7). With raw counts and no length normalisation, every repeated n-gram
  adds to the score, so long blocks end up far from the threshold in either
  direction. D's L2-normalised TF-IDF avoids this.
- D's own errors are in the Fragestunde, in both directions. D predicts openers for
  the Zusatzfrage calls "Frage 2.", "Frage 5.", "Frage fünf." (sl_15_28), which C
  gets right (-1.3). D misses question calls that C finds: "Die nächste Frage
  stellt der Abgeordnete Ubbelohde" (be_19_54/535), "Die nächste Frage ist die
  Frage 1113. Herr Abg. Roth." (he_19_147/261), "Wir kommen jetzt zur nächsten
  gesetzten Frage …" (be_18_21/475). Missed question openers: C 54, D 71. Word
  n-grams such as "nächste Frage" separate new questions from Zusatzfragen better
  than D's character n-grams, which blur "Frage 2" and "nächste Frage".
- By state, C has fewer errors in BE (30 vs 39), SL, SH and BB, and more in ST (20
  vs 10) and TH (21 vs 17).

Implications: the models are complementary (C handles the Fragestunde, D handles
long blocks). Worth testing: (a) C with length-normalised counts (L2 norm on word
counts), and (b) an average of the two models' rank-normalised scores. Both should
run on the same frozen folds.

### C+D rank-average ensemble (tested 2026-09-26)

Leak-free, on the frozen folds. Per outer fold, C and D were refit with that fold's
already selected C value on the frozen inner folds, to get inner out-of-fold
scores. Each model's scores were mapped to percentiles of its own inner
distribution and the two percentiles averaged. The threshold was chosen for
macro-F1 on the inner data only and applied once to the outer fold's checkpoint
scores. (Script: session scratchpad `ensemble_CD.py`, not in the notebook.)

| | F1 (mean ± sd over folds) | P | R | Macro-F1 | MCC | ROC-AUC | PR-AUC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C | 0.886 ± 0.056 | 0.874 | 0.908 | 0.935 | 0.873 | 0.983 | 0.924 |
| D | 0.881 ± 0.050 | 0.879 | 0.892 | 0.932 | 0.867 | 0.990 | 0.948 |
| C+D rank avg | 0.891 ± 0.044 | 0.875 | 0.913 | 0.938 | 0.877 | 0.989 | 0.946 |

- Small gain, within noise. Per-fold F1 (C / D / ensemble): 0.891 / 0.862 / 0.895,
  0.958 / 0.938 / 0.949, 0.881 / 0.903 / 0.896, 0.900 / 0.898 / 0.890,
  0.801 / 0.804 / 0.825. The ensemble is best in 2 of 5 folds and never worst, and
  it has the lowest spread.
- It removes about half of the model-specific errors: FPs only in C 41 → 22 still
  wrong, only in D 35 → 10; FNs only in C 20 → 5, only in D 35 → 12. It adds 8 new
  FPs. The shared core stays wrong (82 of 82 FPs, 67 of 70 FNs).
- Fewest misses overall (84 FN; 51 missed question openers vs C 54, D 71). But the
  cases where one model is confidently wrong survive. "Frage 2." / "Frage 5."
  (sl_15_28) are still FPs, and "Die nächste Frage stellt der Abgeordnete
  Ubbelohde" (be_19_54/535) is still a FN. D's top percentile outweighs C's
  middling percentile at a threshold around the 87th percentile.

Verdict: a modest, more stable improvement. It is not a solution to the
Fragestunde or long-block errors, and it does not touch the shared core.

## Effect of the first label fix (hh_20_34, 2026-09-24)

Rerun of D's nested CV on the old and on the fixed labels. The old-label rerun
reproduces the earlier per-fold C and thresholds. The fixed-label rerun matches
the notebook checkpoint rewritten on 2026-09-25.

| | F1 (tuned) | Macro-F1 | MCC | PR-AUC | TP | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old labels | 0.849 ± 0.032 | 0.915 | 0.832 | 0.912 | 906 | 160 | 158 |
| fixed labels | 0.856 ± 0.045 | 0.919 | 0.838 | 0.918 | 917 | 159 | 148 |

The fix itself changed one contribution label (hh_20_34/242-246, 0 → 1). But
`StratifiedGroupKFold` stratifies on the labels, so that single flip reassigned 28
of the 79 cv_pool protocols to different outer folds. That changed every fold's C
and threshold search, and 96 contributions changed error type (22 FN→TP, 11 TP→FN,
31 FP→TN, 31 TN→FP, 1 FP→FN). Almost all of this is fold reshuffling, not the label
fix. The metric gain (+0.007 F1) is well inside the fold-to-fold spread (± 0.03 to
0.045), so it should not be read as an improvement.

hh_20_34/242-246 itself is now labelled positive but predicted negative (FP → FN).
Its score barely moved (-0.056 → -0.059). It was an FP before only because its old
fold's threshold was -0.067. Its new fold's threshold is +0.078. So the model never
detected it well, and the earlier "FP" was threshold luck.

The error analysis above holds. 33 of the top-40 FPs and 15 of the top-20 FNs are
the same cases, and the patterns are unchanged. Borderline cases flip freely
between runs, e.g. sn_5_86/640-642 FP → TN, and by_18_106/938-943, he_19_67/1-2
and sl_15_28/869-878 FN → TP. This confirms that they are threshold noise. The
`distance` values and folds quoted in the sections below are from the old-label
run.

Consequence: before applying more label fixes, freeze the protocol → outer-fold
assignment (and the inner folds), e.g. save it once and use a predefined split.
Otherwise every relabel reshuffles the folds, and changes in the metrics or error
tables cannot be attributed to the fix.

### Status of the reviewed cases in the current run

Every high-confidence case reviewed above has the same error type in the current
run, except for three: hh_20_34/242 (FP → FN, see above), and sn_5_86/640 (FP → TN)
and borderline FNs such as by_18_106/938 (FN → TP), which flip with the new
thresholds. None of the documented problems is resolved, because apart from
hh_20_34 none of the fixes has been applied yet.

New in the current top-40 FPs / top-20 FNs, checked against the labels:

| case | error | verdict | pattern |
| --- | --- | --- | --- |
| hb_19_10/1542-1549 | FP +0.485 | label error | TOP heading "Gesetz zur Änderung des Bremischen Gesetzes über Naturschutz … (Drucksache 19/186) 1. Lesung" is False (type/topic filled). The next heading, 1551, is True. |
| mv_6_4/500-501 | FN -1.121 | label error | 501 "persönliche Bemerkung" is True. The conventions say persönliche Bemerkungen are never openers. |
| be_18_21/582 | FN -0.955 | label error (placement) | The chair reads out the rest of the asker list after the first question. The first asker is named at 580 ("Die Erste ist Frau Demirbükken-Wegner"), so the opener belongs there. |
| mv_5_100/1239-1240 | FN -1.117 | pending rule | Dringlichkeitsantrag added to the agenda, True. Same case as mv_6_4/520. |
| st_6_70/1-4 | FP +0.458 | label error | v2 Eröffnung missing (already listed). |
| sn_5_86/1020-1026 | FN -0.954 | corpus | New TOP's heading missing from the corpus. 1026 (first speaker of the Große Anfrage) is True, sharing a block with the previous TOP's article votes. Same as sn_5_86/1298. |
| he_16_95/1 | FN -0.939 | model error | Eröffnung without "eröffne" ("Ich begrüße Sie herzlich zur 95. Plenarsitzung …"). |
| ni_16_37/502 | FP +0.584 | model error | "Die nächste Frage wird von Herrn Briese gestellt." Follow-up question call. The same phrasing at 484 and 492 is False, consistently. |
| sl_14_12/1164 | FP +0.561 | model error | Speaker call naming a Drucksache ("Zur Begründung des Antrages …, Drucksache 14/254, … erteile ich … das Wort"). |
| sl_14_12/1288-1290, nw_16_76/5-9 | FP | model error | Votes, and birthday/housekeeping. |
| sn_4_32/604-617 | FP +0.568 | corpus | Speech text tagged `pre`. |

## Summary: what drives high-confidence false positives

Scope: the 40 highest-ranked of D's 160 out-of-fold FPs (distance +1.732 down to
+0.534). The ranking was rebuilt from `nested_oof_checkpoint.pkl`, since the
notebook file has no saved output for the review cell. It matched the checkpoint
row for row (9,333 cv_pool contributions). The notebook prints the top 20.

| # | cause | n | cases (rank, protocol, rows) |
| --- | --- | --- | --- |
| 1 | label error: the model is right | 6 | 6 hb_19_10/407-418 (Konsensliste), 7 th_4_67/1-21 and 17 he_18_26/1-9 (v2 Eröffnung missing), 14 hh_22_32/758-764 (HH v2 opener on bracket reprint), 23 rp_15_48/234-235 (Aussprache über Mündliche Anfrage, True in rp_15_44/280 and /439), 31 hb_16_51/175-177 (second Anfrage False, all other Anfragen in the protocol True) |
| 2 | agenda setting and housekeeping blocks that list TOP numbers and titles without treating them | 9 | 1 be_18_9/24-28, 3 hb_18_43/6-100, 11 th_5_137/123-124 (ambiguous), 21 sh_16_104/1453-1456, 22 he_19_67/9-13 (TOP 46 is actually called at row 21), 28 sl_17_8/4-7, 36 sl_17_32/4-7, 37 sh_15_66/11-13, 38 th_7_126/5-20 |
| 3 | votes and article calls inside an open TOP | 8 | 16 bw_13_100/1468-1501, 30 bw_15_84/1722-1731, 39 mv_5_100/1149-1214 (Artikel/Einzelberatung), 18 ni_18_64/546-558 (votes on TOP 5a/5b), 19 bb_7_63/591-595, 33 sl_17_32/1212-1213, 35 mv_5_100/1846-1850, 34 mv_6_4/595-600 (election results) |
| 4 | segmentation: a chair block split by a non-`pre` row, so a fragment looks like a heading | 5 | 10 hb_17_82/981-982, 12 hh_22_37/704-708, 13 hb_19_10/6-16, 20 th_7_38/916 ("Die nächste Anfrage stellt der", finished at 918, True), 32 sl_15_28/1115-1116 (title split off from "Wir kommen nun zu Punkt 3 der Tagesordnung:", 1113, True) |
| 5 | corpus and layout artifacts, chair speeches, citation blocks | 6 | 2 by_17_100/994-2037 (1,044-paragraph annex list of Beschlussempfehlungen), 26 sn_4_64/717-725 (speech text tagged `pre` with the TOP heading interleaved), 29 sn_6_1/188-195 (content of TOP 2 before its heading at 203), 40 sl_17_32/583-589 (President's own speech for the Frankofonie Antrag), 24 st_6_70/15-22 (obituary), 27 hh_16_74/297-300 (bracketed citations plus Zusatzantrag of an open TOP) |
| 6 | "rufe auf" and numbered questions that are not openers | 4 | 4 and 5 sl_15_28/903, /915 (Zusatzfrage count-through), 9 mv_6_4/1804 and 25 th_4_67/485 ("rufe … auf" with a speaker as object) |
| 7 | sitting interrupted, resumed or closed | 2 | 15 mv_5_100/1304-1308 ("wir fahren im Tagesordnungspunkt 8 fort: Beratung des Entwurfs …", TOP 8 already opened at 1301-1302), 8 hb_18_43/1396-1400 (closing the sitting) |

Reading across the causes:

- About one in six top FPs is a gold-label error (6 of 40), and three of the six
  come from gaps in the v2 annotation (Eröffnung, HH bracket placement). Measured
  precision is therefore pessimistic. Fixing the labels changes the FP count before
  any model change.
- The main model failure is function versus surface. D scores the presence of
  opener vocabulary (TOP numbers, titles, Drucksache citations, "rufe auf",
  "Ich rufe auf / Artikel N") and cannot tell whether the chair is opening an item,
  scheduling it, voting on it or citing it. Causes 2, 3, 6 and 7 (23 of 40) are all
  this.
- Long contributions add up. Four of the top 40 have 34 or more paragraphs
  (by_17_100 n=1,044, hb_18_43 n=95, mv_5_100 n=66, bw_13_100 n=34), and each
  collects dozens of title and citation n-grams. TF-IDF with L2 normalisation
  softens this, but not for blocks made almost entirely of titles.
- Segmentation (cause 4) and corpus artifacts (cause 5) account for 11 of 40. The
  narrow `nsc` join fixes most of cause 4. Cause 5 needs no label change.
- Candidate model-side fixes, in order of expected effect: context from the
  preceding and following contribution, a length feature (or scoring long
  contributions per paragraph), and negative n-gram cues for vote and scheduling
  language ("Abstimmung", "Handzeichen", "Gegenprobe", "vereinbart",
  "Tagesordnung … aufgenommen").

## Summary: what drives high-confidence false negatives

Scope: the 20 most confidently missed openers (distance -1.536 to -0.972) of D's
158 out-of-fold FNs, rebuilt from the checkpoint the same way as the FPs.

| cause | n | cases |
| --- | --- | --- |
| Fragestunde question openers with no subject-matter content | 16 | be_15_85/292, /312, /365-366, /384; be_18_9/641; be_18_21/454-455; be_19_54/397-398, /440-441; by_15_52/31, /53, /71, /232; he_19_147/60, /83-84, /180; sn_4_32/492 |
| inconsistent labels for "Wir verbinden hiermit" follow-ups (HB) | 1 | hb_15_28/659-660 |
| opener heading inside a long vote block | 1 | hb_15_28/718-726 |
| TOP heading missing from the corpus, label on the first row of the new TOP | 1 | sn_5_86/1298-1299 |
| TOP named during agenda setting, labelled True | 1 | mv_6_4/520 |

### Fragestunde questions without subject-matter content (16 of 20)

The missed rows are the chair's calls to the next asker:

- "Nun hat Kollege Doering das Wort für die Fraktion der Linkspartei.PDS. – Bitte!"
  (be_15_85/312)
- "Nächste Frage: Herr Kollege Schieder." (by_15_52/232)
- "Frage 1109, Herr Abg. Bauer." (he_19_147/180)
- "Die nächste Frage geht an die SPD-Fraktion und da an die Kollegin Aydin."
  (be_19_54/397-398)

The labels follow the conventions, since each question in a Fragestunde is its own
thematic unit. But the `pre` text names only the asker and, at most, a number. That
is the same surface form as an ordinary speaker call ("Das Wort hat …"), which
occurs thousands of times as a negative. It is also the same form as a Zusatzfrage
call ("Frage 2.", sl_15_28/903), which is negative by convention. The subject of
the question is only in the MP's following speech, which is not in the input. This
is the case the conventions describe as hardest (hh_16_74). The top 20 add BE
(spontane Fragen / Fragestunde, 8 cases), BY (4) and HE (3). A bag-of-n-grams model
on `pre` text cannot learn these from the text. The FP side has the mirror image:
Zusatzfrage calls predicted as openers (sl_15_28/903, /915). The model cannot tell
a new question from a follow-up, and gets it wrong in both directions.

Across all 158 FNs, 83 contain "Frage"/"Anfrage" or carry an Anfrage type (rough
match, not hand-checked). So the Fragestunde accounts for about half of all
misses, not only the top of the ranking.

Options:

- Report opener performance with and without Fragestunde question openers.
  TOP-level boundaries and question-level boundaries are different tasks, and the
  second is not learnable from `pre` text alone.
- Give the model context: the first sentence of the following speech carries the
  question's subject.
- Treat question-level openers as a second, separate label (as the conventions
  already hint in "What context a future classifier would need").

### Other misses

- hb_15_28/659-660 "Wir verbinden hiermit: / Bericht des Petitionsausschusses
  Nr. 21 vom 5. Dezember 2000" is True. The identical construction in
  hb_17_82/981-982 (Nr. 43) is False and appeared as an FP. Across all HB
  protocols, the row after "Wir verbinden hiermit:" is True 8 times and False 7
  times (hb_15_28: 129, 286, 660, 928 True, 856 False; hb_17_82: 820 True, 32,
  653, 982, 996, 1077 False; hb_18_43: 542, 920, 991 True; hb_16_51: 418 False).
  The model sees contradictory examples of one pattern and is penalised both ways.
  This needs one rule for HB joint items. Candidate: True when the joint item has
  its own title or subject, False when it is a report or recommendation on the
  same document.
- hb_15_28/718-726: the block starts with the previous vote result, then the real
  heading "Wahl eines Mitglieds der staatlichen Deputation für Bau" and the whole
  vote. This is a model error: one heading row among seven vote rows. It is the
  reverse of the long-block FPs.
- sn_5_86/1298-1299: TOP 5 ends at 1296, 1297 is "(Unruhe im Saal – Glocke des
  Präsidenten)", and the TOP 6 heading is not in the corpus at all. The opener sits
  on "Die Aussprache erfolgt in der Reihenfolge wie gehabt …", the first chair row
  of TOP 6, which has no identifying content. This is a reasonable placement, but
  it cannot be learned from the text. Candidate for exclusion or a note in the
  conventions.
- mv_6_4/520: "die Fraktion DIE LINKE hat beantragt, einen Dringlichkeitsantrag
  zum Thema „Vorrundengruppenspiele …" auf die Tagesordnung … zu setzen" is True.
  It is agenda setting (the item is called later, "nach dem
  Zusatztagesordnungspunkt"), the same situation as th_5_137/124 and
  he_19_67/10-11, which are False. It belongs under the pending rule for TOPs named
  only to schedule, move or drop them.

## Summary: borderline false negatives

Scope: the 20 FNs closest to the threshold (distance -0.001 to -0.101). The labels
of all 20 were checked against the rows marked True inside each contribution. None
is a label error. The checkpoint's labels differ from the current CSVs only at
hh_20_34/242-246 (fixed 2026-09-24).

| cause | n | cases (rows, True row) |
| --- | --- | --- |
| TOP opener diluted inside a mixed block (end of the previous TOP, the new call, the first speaker) | 10 | by_18_106/938-943 (941), hh_22_32/1117-1120 (1119), bb_7_34/850-859 (854), th_4_67/1472-1481 (1480), th_4_67/399-403 (402), sh_19_62/942-946 (945), hb_15_28/277-283 (280), he_16_95/1084-1087 (1085), ni_17_3/242-244 (243, sub-item b), sn_7_52/1328-1346 (1331, heading plus 15 rows of speech tagged `pre`) |
| Fragestunde question calls | 5 | bb_6_5/407 ("Frage 50 (Verlängerung der S-Bahn …)"), bb_6_5/430-431 ("Frage 52 (Zeugnisanerkennungsstelle …)"), rp_15_88/21 ("Mündliche Anfrage Nummer 3"), be_18_9/683-684 ("Der nächste Fragesteller ist …", no subject), sl_15_28/869-878 (Fragestunde heading plus Frage 1) |
| Sitzungseröffnung with housekeeping | 3 | he_19_67/1-2, he_19_147/1-3, sl_17_8/1-2 |
| Einzelplan calls inside budget votes | 1 | sh_18_16/1405-1418 (1408, 1410, 1416) |
| bare joint trigger, titles not in the contribution | 1 | sh_18_16/1552-1553 ("Ich rufe jetzt die Tagesordnungspunkte 6 und 8 auf:") |

The main finding is dilution, the mirror image of the long-block FPs. In half of
these cases the contribution contains a clear opener ("Damit schließe ich
Tagesordnungspunkt 7 und rufe Tagesordnungspunkt 8 auf. / TOP 8: Gesetz zur Umsetzung
…", bb_7_34), but it shares the unit with the previous TOP's votes ("Handzeichen",
"Gegenprobe", "abgelehnt") and the next speaker call. D scores the joined text, so
the vote vocabulary pulls the score just below the threshold. In the long-block FPs,
title vocabulary pulls vote blocks above it. Either way, the score describes the
mix of the unit, not whether an opener is in it.

The gold label is aggregated as the max over the paragraphs, but D scores the
joined text. The rule-based detector is already run per paragraph and max-aggregated
(cell 21: "running it on the joined text misses headings that sit inside a merged
contribution"). Doing the same for D (score each paragraph, take the max per
contribution) addresses both the diluted FNs here and the long-block FPs. The
alternative is to split contributions at "schließe … Tagesordnungspunkt" or
"Ich rufe … auf".

These are borderline (|distance| ≤ 0.101), so small changes to features or
threshold would flip them. The Fragestunde cases with a subject in the call (bb_6_5
"Frage 50 (…)") differ from the high-confidence FNs, which have no subject at all.
Those are learnable and just below the threshold.

Minor placement note: hh_22_32/1118 ("Wir kommen zu Punkt 31, auch das ist ein
Antrag der CDU-Fraktion: Bessere Chancen für Obdachlose …") is False and the
bracket reprint 1119 is True. This is the HH v2 placement issue again, with no effect
on the contribution label.

## Reviewed cases

| protocol | row | text | gold | error | distance | verdict | pattern |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sl_15_28 | 903 | "Frage 2." | False | FP | +1.530 | model error | Zusatzfrage count-through |
| sl_15_28 | 915 | "Frage 5." | False | FP | +1.445 | model error | Zusatzfrage count-through |
| hb_19_10 | 407-418 | "… Aktuelle Stunde … Konsensliste Mitteilung des Präsidenten …" | False | FP | +1.430 | label error (not yet fixed) | Konsensliste as its own agenda item |
| mv_6_4 | 1804 | "Ich rufe auf den Abgeordneten Herrn Suhr von der Fraktion BÜNDNIS 90/DIE GRÜNEN." | False | FP | +1.108 | model error | "rufe auf" as a speaker call |
| hb_17_82 | 981-982 | "Wir verbinden hiermit: / Bericht des Petitionsausschusses Nr. 43 vom 15. Februar 2011" | False | FP | +1.095 | model error, caused by segmentation | chair block split by nsc rows |
| th_5_137 | 123-124 | "… Damit ist der Antrag abgelehnt. / Wir kommen nun zum Tagesordnungspunkt 6. Da gab es zwei Anträge … abgesetzt haben … morgen …" | False | FP | +1.092 | ambiguous | TOP mentioned during agenda setting |
| hh_22_37 | 704-708 | "Kennzeichnungspflicht für Polizeivollzugsbedienstete" sowie: … / [Bericht des Innenausschusses …] / [Antrag der Fraktion DIE LINKE …]" | False | FP | +1.055 | model error, caused by segmentation | chair block split by nsc rows (chair change) |
| hb_19_10 | 6-16 | "Zur Abwicklung der Tagesordnung wurde interfraktionell vereinbart … Konsensliste …" | False | FP | +0.955 | model error, caused by segmentation | agenda preview split from Eröffnung |
| hh_22_32 | 758-764 | "… Wir können dann zu den Abstimmungen kommen. … / Ich rufe den Tagesordnungspunkt 28 auf, Drucksache 22/5636 …" | False | FP | +0.931 | label error (not yet fixed) | HH v2 opener on the bracket reprint |
| bw_13_100 | 1468-1501 | "… Zweiten Beratung zur Abstimmung über den Gesetzentwurf Drucksache 13/4523 … / Ich rufe auf / Artikel 1 / Gesetz zur Schaffung der Landesanstalt …" | False | FP | +0.901 | model error | "Artikel N" calls in a reading |
| sn_5_86 | 640-642 | "Meine Damen und Herren! Aufgerufen ist das Gesetz zur Fortentwicklung des Kommunalrechts, Drucksache 5/11912 … Wir stimmen auf der Grundlage der Beschlussempfehlung … ab" | False | FP (borderline) | +0.009 | model error | vote phase of an open TOP |
| hh_20_34 | 242-246 | "… dann kommen wir zum zweiten, dritten und fünften Thema, angemeldet von den Fraktionen DIE LINKE, SPD und GAL: / Hamburg steht auf gegen Nazis …" | False | FP (borderline) | +0.012 | label error (fixed 2026-09-24) | Aktuelle Stunde theme: opener on upfront list, not on the call |
| th_4_67 | 1-21 | "… ich heiße Sie herzlich willkommen zu unserer heutigen Sitzung des Thüringer Landtags, die ich hiermit eröffne. …" | False | FP | n/a | label error (not yet fixed) | Sitzungseröffnung missing in v2 |

## Patterns

### Zusatzfrage count-through in a Fragestunde (FP)

sl_15_28, Grüne Fragestunde on the Museumsneubau. The chair opens the question with
"Ich rufe nun die Frage 1 auf, gestellt von Herrn Fraktionsvorsitzendem Hubert
Ulrich. Sie lautet:" (row 875, True). The chair then allows six follow-ups
("Es sind auch hier sechs Zusatzfragen möglich", row 896) and calls them by number:
"Frage 2." (903), "Vierte Frage." (912), "Frage 5." (915), "Letzte Zusatzfrage."
(923). The second question starts at row 934 ("Ich rufe die Frage 2 auf, ebenfalls
gestellt von...", True).

The gold labels are correct. Under the conventions a Zusatzfrage stays on the
subject of the question it follows and is not an opener. The labels are consistent
across the protocol: the same count-through in the PIRATEN Fragestunde ("Frage 2
bitte…", 815; "Frage 5 bitte.", 824) and in the second Grüne question ("Frage 3,
bitte.", 958; "Frage fünf.", 968) is also False.

Why the model fails: with a single short paragraph as input, "Frage 2." shares its
main n-grams ("Frage", "Frage 2") with real question openers like "Ich rufe die
Frage 2 auf". Nothing else in the input can outweigh them. A real opener differs in:

- wording: "rufe … auf", "gestellt von", "Sie lautet:"
- length: count-through calls are one to three words
- context: they follow a "N Zusatzfragen möglich" line

Possible fixes: add the preceding paragraph as context, or add a paragraph-length
feature.

### Konsensliste as its own agenda item (FP, label error)

hb_19_10 (v2 sample), a 12-paragraph contribution between the Regierungserklärung
debate and the next Große Anfrage. It contains two candidate units:

- 410-411: bare "Aktuelle Stunde" heading, then the chair says the DIE LINKE
  Aktuelle Stunde "Länderfinanzausgleich …" "ist inzwischen von den Antragstellern
  zurückgezogen worden". 410 is correctly False: a bare format heading is never an
  opener under the conventions. 411 names a title, but the item is withdrawn and
  no unit follows. False is defensible, but the conventions don't cover withdrawn
  items yet.
- 412: "Konsensliste Mitteilung des Präsidenten der Bremischen Bürgerschaft vom
  8. Dezember 2015", followed by its own Beratung ("Die Beratung ist eröffnet. –
  Wortmeldungen liegen nicht vor.") and its own vote ("stimmt der Konsensliste
  zu"). In Bremen the Konsensliste is called as its own agenda item after the
  Aktuelle Stunde (§58a GO, announced at row 18 of the same protocol). It bundles
  the items passed without debate. The heading identifies a citable document (a
  dated Mitteilung des Präsidenten), so under the default rule
  (heading with identifying title) it should be `is_opener=True`, with
  `topic=Prozedural`.

With 412 relabelled, this contribution becomes a positive and the prediction a
true positive. The model picked up "Beratung ist eröffnet", "Abstimmung" and the
heading structure that other HB openers share.

Berlin's Konsensliste mentions ("Tagesordnungspunkt 15 steht auf der
Konsensliste") are different. They only note that an item was already handled
elsewhere, and False is correct for them.

### "rufe auf" as a speaker call (FP)

mv_6_4, row 1804: "Ich rufe auf den Abgeordneten Herrn Suhr von der Fraktion
BÜNDNIS 90/DIE GRÜNEN." This is a real one-paragraph contribution. The raw corpus
has Donig's speech ending at 1803 and Suhr's speech starting at 1805. It is a call
to the next speaker within the running debate, the MV equivalent of "Das Wort hat
jetzt der Abgeordnete …" (1782, 1826, 1843, all False). The label is correct.

The model keys on "rufe auf", the main TOP trigger phrase, whose object here is a
person, not an agenda item. The content-anchoring principle in the conventions
exists for this case: the paragraph names a speaker, not a topic or TOP number.
A bag-of-n-grams model can't tell the objects of "rufe auf" apart unless the
n-grams around the phrase ("auf den Abgeordneten", "von der Fraktion") outweigh it.

### Chair block split by nsc rows (FP, segmentation)

hb_17_82, rows 981-982: "Wir verbinden hiermit: / Bericht des
Petitionsausschusses Nr. 43 vom 15. Februar 2011". In the raw corpus the chair's
announcement is one continuous block, 978-986, split by two parenthesised citation
lines that StateParl tags as `nsc`:

| pos | affiliation | content |
| --- | --- | --- |
| 978 | pre | "Interfraktionell ist vereinbart worden, als nächstes vorab die Tagesordnungspunkte 37 und 53 … aufzurufen" |
| 979 | pre | "Bericht des Petitionsausschusses Nr. 42 vom 1. Februar 2011" (True) |
| 980 | nsc | "(Drucksache 17/1633)" |
| 981 | pre | "Wir verbinden hiermit:" |
| 982 | pre | "Bericht des Petitionsausschusses Nr. 43 vom 15. Februar 2011" |
| 983 | nsc | "(Drucksache 17/1653)" |
| 984 | pre | "Die Aussprache über die Petitionen … ist eröffnet." (True) |

The contribution builder starts a new contribution at every `start_pos` gap, so
this block becomes three units: 978-979, 981-982 and 984-986. On its own, 981-982
looks like a title heading, and the model scores it as an opener. As part of the
whole block it would sit inside a positive contribution and never be scored
separately. The label is consistent with the convention for "Wir verbinden
hiermit" follow-ups on the same subject (Petitionen, discussed jointly with Nr. 42).

Scale, across all 95 labelled protocols in the raw corpus:

- 2,199 `nsc` rows sit between two `pre` rows. Each one splits a chair block into
  two contributions.
- 29 of those are bare Drucksache citations, all in HB (15) and SL (14), led by
  hb_16_51 (6) and hb_17_82 (4). They are part of the announcement itself, not
  interjections.
- The rest are mostly reactions inside a chair utterance: "(Beifall)", "(Einstimmig)",
  "(Unruhe)", "[Gongzeichen]" …

Treating any non-`pre` row as a boundary is not always wrong, since a speech between
two chair turns is a real break. But an `nsc` row is not a change of speaker. Joining
across `nsc` rows (or only across citation-only `nsc` rows) would keep blocks like
978-986 together. This changes the unit of analysis, so all folds would need a rerun.

Two more cases of the same mechanism, both with correct labels:

- hh_22_37/704-708. The TOP 23 opener at 702 ("Und wir kommen zum nächsten
  Tagesordnungspunkt 23, Bericht des Innenausschusses: …") is True. The same
  sentence continues at 704, after a presiding-officer change "(Erste
  Vizepräsidentin Mareike Engels)" at 703 that StateParl tags `nsc`. 704-708 is
  the sentence tail, the bracketed reprint (705), the DIE LINKE Zusatzantrag to the
  same TOP (706-707) and the speaker call. Nothing new opens here. The model scores
  the dense citation text of the brackets. This is the presiding-officer-change
  case the conventions already list as unresolved, here as a segmentation problem.
- hb_19_10/6-16. The Eröffnung at row 1 is True (contribution 1-4). "(Beifall)" at
  row 5 splits off the agenda preview: the order of business for the week, the
  list of added TOPs (58-65) and the vote on handling the Konsensliste items in the
  simplified procedure. The block names a dozen TOP numbers and titles, so the
  model scores it high, but none of these items is treated here. False is correct.
  Joined with rows 1-4, it would be part of the positive Eröffnung contribution.

Options, with the effect of joining across every `nsc`-only gap (all 95
protocols, current labels):

| unit | contributions | positive contributions |
| --- | --- | --- |
| current: split at any gap | 11,463 | 1,305 |
| join across `nsc`-only gaps | 9,249 | 1,145 |

A full join merges 160 positive contributions into neighbouring positives. Two
openers that were only separated by "(Beifall)" or "(Einstimmig)" end up in one
unit, so a real boundary is lost. A narrower join, only across `nsc` rows that
belong to the chair's text (bare Drucksache citations, presiding-officer-change
lines), fixes the split announcements (hb_17_82/980-983, hh_22_32/765,
hh_22_37/703) without merging separate units. hb_19_10/5 "(Beifall)" would stay a
split. The alternative that removes the dependence on segmentation is to classify
at paragraph level, with the previous and next paragraph as context.

Presiding-officer changes are a separate source of `nsc` splits in HH:
"(Vizepräsident Deniz Celik)", "(Erste Vizepräsidentin Mareike Engels)". They can
fall mid-sentence (hh_22_37/702-704).

Side observations in hb_17_82, not yet checked:

- 817 and 820 have the same title ("Gesetz zur Änderung des
  Vergnügungssteuergesetzes"). 820, the "Wir verbinden hiermit" follow-up, is True
  and 817, the first announcement, is False. This looks inverted.
- 984 ("Die Aussprache über die Petitionen … ist eröffnet") is True, although the
  TOP was already opened at 979.

### HH v2: opener placed on the bracket reprint (FP, label error)

hh_22_32/758-764 looks like a vote block. 758-763 are the Abstimmungen closing TOP
19, and those rows are correctly False. The last row, 764, is the next TOP
announcement: "Ich rufe den Tagesordnungspunkt 28 auf, Drucksache 22/5636, Antrag
der GRÜNEN und der SPD-Fraktion: Klimaneutralität der öffentlichen Unternehmen bis
2040." It carries number and title, so under the conventions it is the opener. It
is labelled False, and `is_opener=True` sits on 766 instead, the bracketed reprint
"[Antrag der Fraktionen der GRÜNEN und der SPD: … – Drs 22/5636 –]". The
conventions keep reprints like this False. A chair change at 765 "(Vizepräsident
Deniz Celik)" splits 764 and 766 into different contributions, so the misplacement
flips the contribution label: 758-764 becomes a false negative in the gold labels
and the model's positive looks like an FP.

This is systematic in the v2 HH protocols. Rows matching "rufe/kommen …
Tagesordnungspunkt N", with how many are True:

| protocol | sample | announcement rows | True |
| --- | --- | --- | --- |
| hh_16_74 | v1 | 15 | 15 |
| hh_20_77 | v1 | 6 | 6 |
| hh_22_37 | v1 | 10 | 10 |
| hh_18_14 | v2 | 13 | 1 |
| hh_20_34 | v2 | 2 | 0 |
| hh_22_32 | v2 | 11 | 0 |

v1 puts the opener on the announcement, v2 on the bracket (e.g. hh_22_32/680 False
with 681 and 682 True). When announcement and bracket are adjacent, the
contribution label is the same either way. It only changes when an `nsc` row falls
between them, as at 764/766. The paragraph-level placement is still inconsistent
between the samples and should be fixed.

### TOP mentioned during agenda setting (ambiguous)

th_5_137/123-124, v1. At this point the chair is still handling requests to change
the agenda, before the agenda proper starts. Row 121 votes on a request to hear TOP
20 by Friday at the latest. Row 124 reads "Wir kommen nun zum Tagesordnungspunkt 6.
Da gab es zwei Anträge …": DIE LINKE wants TOP 6 dropped, the CDU wants it moved to
after tomorrow's Fragestunde. The discussion that follows (127-140) ends with TOP 6
postponed to the next day. TOP 6 is named with its number, but it is not dealt with
here.

The row names a TOP number, which argues for True. No unit on TOP 6 starts,
though. The chair opens a procedural sub-item about the agenda, not the TOP
itself. This is the same open question as the withdrawn Aktuelle Stunde in
hb_19_10/411: a TOP is identified, but only to drop or move it. The conventions
need one rule for both. Until then the label stays as is and the case is
ambiguous, not an error.

### "Artikel N" calls in a reading (FP)

bw_13_100/1468-1501 (v2), a 34-paragraph contribution: the vote in the Zweite
Beratung on Gesetzentwurf 13/4523, inside TOP 6. It runs through "Ich rufe auf /
Artikel 1 / Gesetz zur Schaffung der Landesanstalt …", then Artikel 2-7 each with a
heading line ("Änderung des Ernennungsgesetzes", "Inkrafttreten" …), Einleitung,
Überschrift, Schlussabstimmung and the votes on the Entschließungsanträge. It ends
just before "Damit ist Tagesordnungspunkt 6 erledigt." (1510). All rows are False,
which is correct. The conventions name this pitfall explicitly: "Artikel N" calls
are procedural steps through a TOP that is already open.

The model sees "Ich rufe auf" twice, followed by short title-like heading lines.
That is the same surface form as a BW TOP opener ("Ich rufe Punkt N der
Tagesordnung auf: / Title"). The same structure occurs in bw_13_100/1073-1102 (TOP
4, Schulgesetz), also False. The contribution is long, and none of its
content-bearing lines says "Tagesordnung" or carries a TOP number.

### Aktuelle Stunde themes: opener on the upfront list, not on the call (FP, label error)

hh_20_34/242-246 (v2): "Gibt es weitere Wortmeldungen zum ersten Thema? – Wenn
das nicht der Fall ist, dann kommen wir zum zweiten, dritten und fünften Thema,
angemeldet von den Fraktionen DIE LINKE, SPD und GAL:", followed by the three
titles (243-245) and the first speaker. The joint debate on the Nazi-demonstration
themes starts here. All rows are False.

Instead, the openers sit on the list of registered themes read out at the start of
the Aktuelle Stunde (rows 8, 10, 12, 14, 16, all True). At that point none of the
themes is being debated. Three problems:

- The actual start of the joint debate on themes 2, 3 and 5 (242) is False, so the
  model's positive counts as an FP.
- The fourth theme (CDU, "Ganztagsschulen", row 14) is True but never debated:
  "Uns verbleiben weniger als 15 Minuten, um das hier noch angemeldete vierte Thema
  aufzurufen …" (433), then "Damit ist die Aktuelle Stunde für heute beendet."
- The list is an agenda preview. Other agenda previews are False (hb_19_10/6-16,
  hb_18_43/6-100), so the model sees contradictory examples.

HH handles this inconsistently. hh_20_34 and hh_18_14/44 (both v2) put the opener
on the upfront list. hh_22_32/154 (v2) and hh_20_77/20 (v1) put it where the
theme's debate starts. Under "a new unit starts here" it belongs at the call (the
chair row that moves to the theme, with the titles where they are repeated), and
the upfront list is False. A theme that is never called gets no opener.

Fixed 2026-09-24 in `top_boundaries_opener_labels_v2.csv`, hh_20_34 only:

- List rows 8, 10, 12, 14 and 16 are now `is_opener=0`. type/topic stay because
  the titles are printed there. The sponsors on 10 and 12 were shifted by one and
  are corrected (10 SPD → LINKE, 12 CDU → SPD).
- Row 17 ("Ich rufe zunächst das erste Thema auf") is now True, with Aktuelle
  Stunde / FDP / Verkehr.
- Rows 243, 244 and 245 (the repeated titles of the jointly called themes 2, 3 and
  5) are now True, one per theme, following the joint-announcement rule (each
  sub-item title gets its own True), with sponsors LINKE, SPD and GAL and topic
  Ideologischer Extremismus. 242 (the call itself, ordinals only) stays False.
- Theme 4 (CDU, "Ganztagsschulen") was never debated and now has no opener.

The nested CV has not been rerun since the fix. The checkpoint still reflects the
old labels.

### Vote phase re-states the bill (borderline FP)

sn_5_86/640-642 (v2). "Aufgerufen ist das Gesetz zur Fortentwicklung des
Kommunalrechts, Drucksache 5/11912, Gesetzentwurf der CDU- und der FDP-Fraktion.
Wir stimmen auf der Grundlage der Beschlussempfehlung des Innenausschusses ab,
Drucksache 5/13107." This comes right after the general debate closes (631), inside
TOP 2, which opened at 439-443 ("Wir kommen nun zum / Tagesordnungspunkt 2 / … 2.
Lesung des Entwurfs Gesetz zur Fortentwicklung des Kommunalrechts", 443 True).
False is correct. The chair re-states title and Drucksache to start the votes on
the amendments. "Aufgerufen ist" plus title plus Drucksache is opener wording, but
it is the vote-phase restatement (cause 3 in the FP summary). At +0.009 it sits on
the threshold, so this is threshold noise rather than a confident error.

Side note: sn_5_86/441-442 and 446-450 are the CDU speaker's Einbringung text,
tagged `pre` and interleaved with the TOP heading (443-445). This is the same SN
layout artifact as sn_4_64/717-725.

### Sitzungseröffnung never labelled in the v2 sample (FP, label error)

th_4_67 (v2), row 1: "Meine Damen und Herren Abgeordneten, ich heiße Sie
herzlich willkommen zu unserer heutigen Sitzung des Thüringer Landtags, die ich
hiermit eröffne." Under the Sitzungseröffnung rule (2026-09) this row is
`is_opener=True`, `topic=Prozedural`. It is labelled False, so the model's
prediction is right.

This is not a single miss. v1 is complete (checked 2026-09-24, first True row per
protocol): 44 of 47 protocols have their Eröffnung row as the first opener. The
other three are the documented exceptions. bb_4_14 row 1 is True but
topic=Haushalt, and sh_15_66 and sh_19_62 start mid-debate. sh_18_16's first
opener is the documented mid-protocol "Ich eröffne wieder die Sitzung". In v2, 10 of
48 protocols have none. The Eröffnung pass evidently ran on v1 only. Seven of the
ten are real misses, including sn_6_38, where the plain cue "Ich eröffne die 38.
Sitzung" is right there:

| protocol | row | Eröffnung text |
| --- | --- | --- |
| he_18_26 | 1 | "Ich darf Sie herzlich begrüßen … Wir wollen pünktlich anfangen." (no "eröffne", greeting rule as in th_5_2) |
| sn_6_38 | 1 | "Ich eröffne die 38. Sitzung des 6. Sächsischen Landtags." |
| st_6_70 | 2 | "… und eröffne die 70. Sitzung des Landtages der sechsten Wahlperiode." (row 1 is only a greeting) |
| st_8_3 | 2 | "… und eröffne die 3. Sitzung der achten Wahlperiode …" (row 1 is only a greeting) |
| th_4_67 | 1 | "… zu unserer heutigen Sitzung des Thüringer Landtags, die ich hiermit eröffne." |
| th_5_84 | 1 | "… zu unserer heutigen Plenarsitzung, die ich hiermit eröffne." |
| th_7_38 | 1 | "… zu unserer heutigen Sitzung des Thüringer Landtags, die ich hiermit eröffne." |

The other three (sh_16_104, sh_18_17, sh_19_48) start mid-debate, with no
Eröffnung captured. False is correct for them, the same as the documented
sh_15_66 and sh_19_62 exceptions.

Consequence for the evaluation: these seven contributions are gold negatives with
opener content. They count against D as false positives when predicted positive,
and they teach the model contradictory signal in the folds where they are training
data. The TH "die ich hiermit eröffne" phrasing also shows that the v1 cue list
("eröffne die X. Sitzung", "begrüße Sie zur X. Sitzung", …) would not have caught
all of v2 on its own.

## Open follow-ups

- Relabel hb_19_10/412 to `is_opener=True`, `topic=Prozedural` in
  `top_boundaries_opener_labels_v2.csv` (decided 2026-09-24, not applied yet). Then
  add a rule to the conventions for Konsensliste headings and for withdrawn items
  like 411.
- Apply the Sitzungseröffnung rule to v2: set `is_opener=True`,
  `topic=Prozedural` on the seven rows in the table above in
  `top_boundaries_opener_labels_v2.csv` (not applied yet). Then rerun the nested
  CV, since the fold results include these contributions.
- Decide whether contributions should join across `nsc` rows (all of them, or only
  citation-only ones like "(Drucksache 17/1633)"). This changes the unit of
  analysis, so all folds would need a rerun.
- HH v2 (hh_18_14, hh_20_34, hh_22_32): move `is_opener=True` from the bracket
  reprint rows to the "Tagesordnungspunkt N" announcement rows, as in v1 HH (not
  applied yet).
- Add one convention for a TOP that is named only to drop, move, withdraw or add
  it (th_5_137/124, hb_19_10/411, mv_6_4/520, he_19_67/10-11).
- Aktuelle Stunde themes (HH): move openers from the upfront list of registered
  themes to where each theme (or joint group) is called. hh_20_34 is done
  (2026-09-24). hh_18_14 (list 44 → call) is still open. Themes that
  are never debated get no opener. Check other states' Aktuelle Stunden/Debatten
  for the same list-versus-call split, and add the rule to the conventions.
- Add one rule for HB "Wir verbinden hiermit:" follow-ups (8 True, 7 False today)
  and relabel accordingly.
- by_17_100/994-2037 (1,044 rows, the top FP): do not label it Prozedural or as
  an opener. It is the printed annex after the spoken part ends (the last chair row
  is 992): the list of Beschlussempfehlungen voted en bloc under TOP 4, whose
  heading refers back "(Tagesordnungspunkt 4)", followed by the roll-call lists
  (names with X, "Gesamtsumme 80 59 0", "Abstimmungsliste"). TOP 4 itself opened
  at row 277 (True, Prozedural). No unit starts in the annex. Better: exclude annex
  text from training and from unseen data with the same rule, since it is not
  plenary speech. This needs a reliable end-of-sitting / annex detector. A loose
  "Sitzung … geschlossen" pattern also matches opening and scheduling lines.
- Try paragraph-level scoring with max aggregation per contribution for D, as
  the rule-based detector does. It targets both the diluted borderline FNs and the
  long-block FPs.
- Decide how to report Fragestunde question openers: separate metric, separate
  label, or context from the following speech.
- Check sn_7_52/1789 and /1815 (Kleine Anfragen treated in the plenum, labelled False, look
  like a TOP opener and a question-level opener). Found through BERT's top FPs.
- Relabel hb_19_10/1542 to True (TOP heading, Umwelt), mv_6_4/501 to False
  (persönliche Bemerkung), and move be_18_21/582's opener to 580 (not applied
  yet).
- Relabel hb_16_51/176 ("Die zweite Anfrage bezieht sich auf die Entwicklung der
  Arzneikosten …") to True, as for the other nine Anfragen in that Fragestunde (not
  applied yet).
- Decide on rp_15_48/234 ("Ich rufe die Aussprache über die Mündliche Anfrage …
  auf"). The same construction is True in rp_15_44/280 and /439, so either relabel
  it or change both rp_15_44 rows.
- Minor, no effect on contribution labels: mv_5_100/1301 ("Ich rufe auf den
  Tagesordnungspunkt 8: Erste Lesung …") is False, while the citation line 1302
  is True. That is the same announcement-versus-citation placement question as HH
  v2.
- Check hb_17_82/817 vs 820 (inverted opener?) and 984 (opener after the TOP
  already opened at 979).

- Check whether other Fragestunde states (SL-style numbered follow-ups) produce the
  same FP pattern, or if it is specific to sl_15_28.
