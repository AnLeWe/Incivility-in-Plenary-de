# Measuring Impoliteness as Civility-as-Politeness

Impoliteness, as the violation of civility-as-politeness, is defined the following:

Civility as politeness, in Bardon et al.'s (2023) disaggregation of civility, concerns the
form and tone of political communication — how something is said — independent of whether the
content itself is commensurate with liberal democratic values [@bardonDisaggregatingCivilityPoliteness2023].
It is the dimension classically associated with everyday notions of incivility in legislative
studies: rudeness, insults, and disrespectful tone, regardless of the political position being
expressed.

Unlike moral civility (see `morality_measurement.md`), politeness civility is agnostic to the
speaker's viewpoint: a discriminatory or exclusionary claim, delivered in calm, formal language,
is not impolite in this sense — it may violate moral civility instead, but not politeness
civility, and conversely a stylistically hostile utterance can accompany an entirely
unobjectionable political position. This separation is deliberate: it is what lets the two
constructs be measured, and eventually related to one another.

For the present study, impoliteness is operationalized in the tradition of the personal-attack
literature on incivility: overt markers (insults, degrading labels, vulgar language,
mockery/derision), personal attacks that target a person's or group's character, motives, or
integrity rather than their political positions or official conduct (drawing on Jacob et al.'s
(2026, p. 3) personal-attack definition), subtler markers (unnecessarily hostile/aggressive
tone, cynicism, conspicuously negative affect), and institutional sanction (an Ordnungsruf
issued by the presiding officer, or continuing to speak after being called to order).
Interjections (Zwischenrufe) are not per se impoliteness markers — they are judged by the same
criteria as regular speech.

## Implementation Plan

- unit: paragraph-level (a single Zwischenruf/interjection or speech segment), not TOP- or
  speech-level — the model is given a ±1 paragraph context window around the target paragraph
  (empirically, 98.9% of interjection–target exchanges are exactly 1 paragraph apart, 99.9%
  within 2; see Resolved log below)
- Ordnungsruf is NOT proximity-based (can follow up to 100+ paragraphs after the actual speech,
  keyed by speaker name) — handled via a separate precomputed flag
  (`preprocessing/ordnungsruf_flags.py` → `nsc_paragraph_flags`-style side table) rather than
  stuffed into the context window
- classifier: zero-shot binary LLM classification, no supervised fine-tuning yet — LoRA
  fine-tuning + a BERT model, trained on an LLM-balanced synthetic set, considered as a later
  extension (see Checklist)
- models under comparison for interrater/robustness: gemma4:12b, gemma4:e4b,
  mistral-small3.2:24b, + others; full-corpus scoring runs on qwen3:14b-q4_K_M
- prompt versioning: `prompts.py` (named, versioned constants, never edited in place) +
  `prompt_history.jsonl` (full text + changelog per version) — should also log temperature and
  other runtime parameters per run, not just the prompt name
- interrater reliability: Cohen's κ (pairwise, two raters), Fleiss' κ and Krippendorff's α
  (multi-rater, nominal) — no random baseline yet, since there is no ground truth
- external benchmarks under consideration: an R package for linguistically-grounded impoliteness
  detection, and Anke Stoll's incivility classifier (mixes impolite and toxic language — needs
  disentangling against this project's definition before it's usable as a benchmark)

## Data & Model-Training Strategy

**Sampling frame.** Stratify by state (all 16 — fixes the earlier Bavaria-only sample), time
relative to AfD entry per state (the core treatment variable — an accidental pre/post skew would
bias everything downstream, not just the classifier), and TOP policy topic. Sample whole TOPs
(all paragraphs — speeches, interjections, procedural — in original order), not sessions or
single speeches, so real conversational context is preserved without sacrificing
representativeness. Supersedes the earlier ±1 year random sample (representative but broke
sequence) and the Bavaria-only sample (kept sequence but not representative).

**Data tiers, drawn from that one shared frame:**

- domain-adaptive pretraining pool: large, unlabeled, no sample-efficiency constraint since it
  needs no labels — used for continued/domain-adaptive pretraining of the encoder before it sees
  any task labels
- gold: the ~200 non-expert annotators, not the proprietary model. Paragraph-level micro-tasks
  (±1 context, matching the existing prompt design) pulled from the stratified TOPs, 3 annotators
  per item for redundancy, majority vote, Krippendorff's α/Fleiss' κ reported per item — slots
  into the existing `compute_interrater_agreement.py`. Full-TOP sequences stay intact for
  annotator context even though each person only labels one paragraph at a time. → dev + held-out
  test.
- silver: teacher LLM (Sonnet 5 for bulk volume, Opus 5 for a smaller high-quality pass) labels a
  much larger pool than 200 annotators can cover. → train set for the encoder.

**Model architecture.**

- encoder (ModernGBERT — `LSX-UniWue/ModernGBERT_1B` or the `134M` variant) is the primary
  trained artifact. Encoders are more sample-efficient than generative models, and this project's
  realistic gold-label volume (low hundreds even after the annotator pass, not thousands+) favors
  the encoder for supervised fine-tuning. Domain-adapt on the unlabeled pool, then fine-tune on
  gold + silver.
- generative models (Sonnet 5/Opus 5 API; gemma4:12b/e4b, mistral-small3.2:24b, qwen3:14b local)
  stay zero-shot — teacher role (silver labeling) and interrater/robustness-check role, not
  fine-tuned on the same scarce gold set. Revisit fine-tuning a generative model only once the
  gold set is large enough to support it (see Checklist).
- classification mechanism differs by where the model runs: local open-weight models (full logit
  access) use **label/likelihood scoring** — compare log-probability of the label tokens directly
  via the LM head, no sampling loop, no JSON to parse. The Anthropic API exposes no raw logprobs,
  so the proprietary teacher uses **structured outputs** (`output_config.format` with a
  JSON-schema-constrained boolean/enum) as the equivalent parsing-ambiguity fix.

**Shared vs. branch point for morality/impoliteness.** The sampling frame and domain-adapt pool
are fully shared — one stratified corpus serves both constructs. Annotation instructions,
gold/silver sets, and the encoder/generative fine-tunes branch per construct, pending the open
question of whether the two dimensions are guaranteed non-overlapping in the data (see
Checklist).

## Classification Criteria

The current prompt (`v2_context-window-ordnungsruf-flag`, see `prompts.py`) operationalizes the
definition above as a binary decision. An utterance counts as **unhöflich** (impolite) if at
least one holds:

- explicit markers: insults, degrading labels, vulgar language/swearing, derisive descriptions
  of how someone speaks, mockery/derision
- personal attack: named or clearly identifiable target, attacking character, motives, or
  integrity rather than political positions or official conduct (Jacob et al. 2026) — includes
  questioning character/honesty/patriotism, derogatory nicknames, attacks on appearance/origin/
  private life, unsubstantiated corruption/bad-faith accusations, rhetoric aimed at the person
  rather than their ideas
- subtler markers: unnecessarily hostile/aggressive tone, cynicism, conspicuously negative
  emotional language
- institutional sanction: an Ordnungsruf is issued, or the speaker continues after being told to
  yield the floor

Counts as **nicht unhöflich** (not impolite): criticism of political positions or voting
behavior; disagreement with official actions, even sharply worded; factual description of party
affiliation/record; general partisan criticism without a specific target; explicitly polite
content; neutral content with no recognizable marker; and — the explicit boundary with moral
civility — discriminatory, exclusionary, or dehumanizing content that carries no accompanying
stylistic marker (that is the separate, morality dimension; only once insults, vulgar language,
mockery etc. are *also* present does it count as impolite here).

Open questions on the criteria themselves:

- how this definition diverges from the R linguistics tool's and from Anke Stoll's classifier,
  and whether classifications actually differ only where the definitions differ
- whether to keep morality and impoliteness as two separate classifiers, or one joint classifier
  that knows the distinction — contingent on checking that the two dimensions aren't guaranteed
  non-overlapping in the data (need to re-verify)

## Checklist

- [ ] Compare against the R linguistics-grounded impoliteness tool; identify where its
      definition diverges from this project's, then check whether classifications differ only
      where the definitions differ
- [ ] Run/compare against Anke Stoll's incivility classifier; account for her conflating
      impolite and toxic language
- [ ] Decide: one joint classifier for morality + impoliteness vs. two separate classifiers —
      first re-check whether the two dimensions are guaranteed non-overlapping in the data
- [ ] Settle which interrater-reliability metric(s) to report and where: Cohen's κ (pairwise)
      vs. Fleiss' κ / Krippendorff's α (multi-rater)
- [ ] Implement a random baseline once ground truth exists
- [ ] Build the stratified TOP sampling frame (state × time-relative-to-AfD-entry × policy
      topic) that feeds the domain-adapt pool, gold annotation, and silver labeling (see Data &
      Model-Training Strategy)
- [ ] Build the annotation micro-task pipeline for the ~200 non-expert annotators: paragraph-level
      items with ±1 context pulled from stratified TOPs, 3-way redundancy, majority-vote
      aggregation feeding into `compute_interrater_agreement.py`
- [ ] Run the Sonnet 5 (bulk) / Opus 5 (high-quality pass) silver-labeling pass over the larger
      pool once the sampling frame exists; budget/cost still unknown — check before committing
- [ ] Domain-adaptively pretrain ModernGBERT on the unlabeled pool, then fine-tune on gold +
      silver once both exist
- [ ] Decide the gold-set-size threshold at which fine-tuning a generative model (not just
      zero-shot) becomes worthwhile — not yet, per the encoder sample-efficiency argument
- [ ] Evaluate ShieldGemma / toxic-bert / roberta-hate-speech-dynabench / roberta_toxicity_classifier
      as an external toxicity benchmark dimension — check German-language support
- [ ] Wire the Ordnungsruf flag (`preprocessing/ordnungsruf_flags.py`) into
      `build_classification_pool()`/the prompt itself — currently computed but not consumed
- [ ] Confirm an instruction-tuned model variant is used going forward (initial runs did not
      use one)
- [ ] Verify the decoder does likelihood scoring, not generation-plus-parsing; verify batch
      right-padding of input_ids/attention_mask/labels with `-100`-masked label positions
- [ ] Scope out the "forensics / maximum likelihood" follow-up — currently undefined
- [ ] Interpretability pass with Captum/SHAP once a fine-tuned model exists
- [ ] Assess feasibility of double machine learning (or an alternative identification strategy)
      to isolate the AfD-entry treatment effect
- [ ] Consider inductive codebook generation, as some political scientists now do, as an
      alternative/complement to the current deductive codebook

Resolved:

- [x] Context window: ±1 paragraph covers direct Zwischenruf exchanges (98.9%/99.9% empirical
      check, 2026-07-29); Ordnungsruf handled separately since it is not proximity-based (see
      Appendix log)
- [x] gemma4:e2b clarified as a small edge/on-device variant, not a smaller gemma4:12b — not
      relevant to the interrater comparison (2026-07-29)
- [x] Gemma4:e4b mini interrater run (2026-07-30): raw agreement 94.9–95.8%, Cohen's κ
      0.469–0.569 vs. the other 4 raters, in line with pairwise numbers among the frontier
      models themselves (0.464–0.571); joint Fleiss' κ = Krippendorff's α = 0.526 across all 5
      raters

## Appendix: Log & Setup Notes

**RESOLVED (2026-07-29): context window for labelling.** Checked empirically: a direct
Zwischenruf exchange is basically always ±1 paragraph (98.9% of interjection clusters are
exactly 1 paragraph long, 99.9% ≤2), so ±1 around the target paragraph covers that. Ordnungsruf
is different — NOT proximity-based. Real example, protocol bb_3_32: presiding officer explicitly
says he waited to review the Wortprotokoll before deciding, then issues the Ordnungsruf 101–115
paragraphs after Fechner's actual speech, referencing her by name ("Redebeitrag von Frau
Fechner... ich erteile Frau Fechner einen Ordnungsruf"), same for Abgeordneter Ludwig further
down in the same protocol. No fixed window would catch this. Built a separate precomputed flag
instead of stuffing more paragraphs into the prompt: `preprocessing/ordnungsruf_flags.py` →
`DATA_ROOT/processed/ordnungsruf_flags.parquet` (`paragraph_id`, `ordnungsruf_follows` bool).
Matches by surname (from `mandate_id`) against later `affiliation=="pre"` paragraphs in the same
protocol mentioning "Ordnungsruf". Validated against the Fechner/Ludwig case above — correct.
10,000/16,078,467 paragraphs flagged (0.062%). Still not wired into
`build_classification_pool()`/the prompt itself (see Checklist).

**gemma4:e2b (looked up 2026-07-29, not the model we use).** It's Gemma 4's small edge/
on-device variant, not a smaller version of gemma4:12b in the way originally assumed. "E2B" =
"Effective 2B" (2.3B effective params, 5.1B incl. embeddings), 128K context, multimodal
(text/image/audio), ~7.2GB quantized. Meant for laptops/mobile, not frontier intelligence —
benchmarks much lower than gemma4:12b (MMLU Pro 60.0% vs 85.2%). Not relevant for the interrater
comparison, that one correctly uses gemma4:12b.

**Gemma e4B mini run, 2026-07-30.** gemma4:e4b agrees quite well with the other 4 despite being
the smallest/edge model: raw agreement 94.9–95.8% and Cohen's kappa 0.469–0.569 against each of
the others, right in the same range as the pairwise numbers among the frontier models themselves
(0.464–0.571). Its highest agreement is with mistral-small3.2:24b (95.8%, κ=0.553) and
gemma4:12b (95.2%, κ=0.569) — the latter being its own larger sibling.

Joint numbers across all 5 raters: Fleiss' κ = 0.526, Krippendorff's α = 0.526 (matching to 3
decimals, as expected for complete nominal data) — down slightly from whatever the 4-model
number was, which makes sense with a 5th, somewhat-different rater added in.

**Windows Hiwi-PC setup (Schritt-für-Schritt, alles ohne Admin-Rechte machbar):**

1. rclone einrichten: portable .exe von rclone.org runterladen (kein Installer), z.B. nach
   `C:\Users\<du>\rclone\`. `rclone config` → neuer Remote → Google Drive → Browser-OAuth-Login
   mit deinem Google-Account (kein Admin nötig, ist nur ein Login).
2. Nur die 4 benötigten Dateien runterladen (nicht das ganze DATA_ROOT — das
   full-corpus-Scoring für qwen3 braucht nur diese):

   ```bash
   rclone copy "remote:my_projects/M.A. Parliament/Code and Data/data" "C:\Users\<du>\parlaw_data" ^
     --include "raw/stateparl_v3_parquet/stateparl_v3_paragraphs.parquet" ^
     --include "processed/nsc.parquet" ^
     --include "processed/afd_entry_dates.csv" ^
     --include "processed/ordnungsruf_flags.parquet"
   ```

   (behält die relative Ordnerstruktur bei, die `build_classification_pool()` erwartet)

3. Repo klonen (git ist bei dir vermutlich schon da wegen VS Code):
   `git clone https://github.com/AnLeWe/Incivility-in-Plenary-de.git`
4. Python-Umgebung: venv anlegen, `pip install -r requirements.txt`
5. `.env` setzen: `.env.example` kopieren, `DATA_ROOT=C:\Users\<du>\parlaw_data`
6. Ollama installieren: der Windows-Installer installiert nach `%LOCALAPPDATA%`, sollte also
   ohne Admin/UAC-Prompt durchlaufen — falls doch ein Prompt kommt, sag Bescheid. Dann:
   `ollama pull qwen3:14b-q4_K_M`
7. Laufen lassen:

   ```bash
   python score_with_model.py --model qwen3:14b-q4_K_M --variant window_flag --full-corpus --platform-label hiwi_pc_rtx4070ti
   ```

8. Wichtig — Ergebnis regelmäßig zurück nach Drive schieben, da DATA_ROOT dort nur eine lokale
   Kopie ist, nicht live gesynct:

   ```bash
   rclone copy "C:\Users\<du>\parlaw_data\measurement\impoliteness_full_all_qwen3-14b-q4_K_M_window_flag.csv" "remote:my_projects/M.A. Parliament/Code and Data/data/measurement/"
   ```

   Am besten vor jedem Verlassen des PCs, damit bei Neustart/anderer Nutzung nichts verloren
   geht. Sag Bescheid, wenn irgendwo ein Admin-Prompt auftaucht — dann müssen wir für den
   Schritt eine Alternative finden.

NEW:
"Similar to Culpeper’s (2011: 176) findings for the courtroom, the bulk of the with respect instances occurred in initial position, regardless of decade, and were followed by utterances that tended to be open “to impoliteness interpretation[s]” (or, at least, face threatening ones). Many of the instances of the second most frequent phrase, with great respect, also occurred in initial position. Their distribution over time demonstrates a slightly different pattern than with respect, however. The peak in usage occurs in the 1950s, in the Commons subset, and the 1940s, in the Lords subset, before showing a gradual decline over the last half-century (see Graphs 3 and 4)." So maybe as a discirminating example something like: "Mit verlaub, Herr präsdident, Sie sind ein Arschloch!" 

NEW: found this promp, looks similar to my impoliteness definition:
SYSTEM_PROMPT = (
    "You are an expert content moderation AI. Classify if the following tweet is OFFENSIVE (1) or NOT OFFENSIVE (0).\n"
    "Criteria for OFFENSIVE (1): Contains explicit insults, slurs, profanity, aggressive personal attacks, "
    "or highly demeaning language targeted at individuals or political groups.\n"
    "Criteria for NOT OFFENSIVE (0): Neutral statements, political opinions (even if highly controversial or biased), "
    "or general discussions without direct ad-hominem insults.\n"
    "Respond ONLY with the single token 1 or 0. No explanation."
)

SHAP example:
# Helper function to find indices for TP, TN, FP, FN
def find_example_indices(actual, predicted, seed=42):
    actual = np.array(actual)
    predicted = np.array(predicted)
    
    # Initialisierung des Zufallsgenerators mit festem Seed
    rng = np.random.default_rng(seed)

    # get idxs for the examples
    tn_matches = np.where((actual == 0) & (predicted == 0))[0] # Correctly classified as 0
    fp_matches = np.where((actual == 0) & (predicted == 1))[0] # Misclassified as 1
    tp_matches = np.where((actual == 1) & (predicted == 1))[0] # Correctly classified as 1
    fn_matches = np.where((actual == 1) & (predicted == 0))[0] # Misclassified as 0

    # picking random idx 
    tn_idx = rng.choice(tn_matches) if len(tn_matches) > 0 else None
    fp_idx = rng.choice(fp_matches) if len(fp_matches) > 0 else None
    tp_idx = rng.choice(tp_matches) if len(tp_matches) > 0 else None
    fn_idx = rng.choice(fn_matches) if len(fn_matches) > 0 else None

    return [tn_idx, fp_idx, tp_idx, fn_idx]


dec_indices = find_example_indices(true_labels_val, preds_decoder_val, seed=8)
dec_texts = [val_df["text"].iloc[i] for i in dec_indices]
dec_labels = ["True Negative (0)", "False Positive (1)", "True Positive (1)", "False Negative (0)"]

enc_indices = dec_indices
enc_texts = [val_df["text"].iloc[i] for i in enc_indices]
enc_labels = ["True Negative (0)", "False Positive (1)", "True Positive (1)", "False Negative (0)"]

# Setting the fine-tuned encoder model to evaluation mode
fine_tuned_encoder.eval()

# Defining a custom prediction wrapper with implicit type handling for the tokenizer
def bert_predict_proba(texts):
    # Converting input sequence arrays to native list structures if required
    if isinstance(texts, np.ndarray):
        texts = texts.tolist()
    
    # Tokenizing the incoming batch of mutated texts dynamically
    inputs = tokenizer_encoder(texts, padding=True, truncation=True, max_length=128, return_tensors="pt")
    inputs = {k: v.to(fine_tuned_encoder.device) for k, v in inputs.items()}
    
    # Executing the forward pass over the full batch simultaneously
    with torch.no_grad():
        outputs = fine_tuned_encoder(**inputs)
    
    # Returning probability distributions normalized via standard softmax
    return torch.softmax(outputs.logits, dim=-1).cpu().numpy()

# Initializing the SHAP explainer with the batch prediction function
explainer_bert = shap.Explainer(bert_predict_proba, tokenizer_encoder)

# Computing SHAP values across the selected encoder evaluation texts
shap_values_bert = explainer_bert(enc_texts)

# Iterating through evaluation instances to generate text attribution plots
for i, label_name in enumerate(enc_labels):
    print(f"\n{'-'*60}")
    print(f"BERT (Encoder) Explanation for: {label_name}")
    print(f"{'-'*60}")
    
    # Extracting tokens and raw score arrays for the targeted offensive class
    tokens = shap_values_bert[i, :, 1].data
    values = shap_values_bert[i, :, 1].values
    
    # Neutralizing structural special tokens to isolate text attribution effects
    for idx, token in enumerate(tokens):
        if token in ["[CLS]", "[SEP]", "[PAD]", ""]:
            values[idx] = 0.0
    
    # Determining peak distribution bounds for proportional color assignment
    max_val = np.max(np.abs(values)) if np.max(np.abs(values)) > 0 else 1.0
    
    # Initializing HTML paragraph container with responsive boundary wrapping rules
    html_str = "<p style='line-height: 2.5; color: black; background-color: white; padding: 15px; border-radius: 5px; font-family: sans-serif; word-break: break-word;'>"
    
    # Formatting output elements with uniform inline boundaries and space characters
    for idx, (token, val) in enumerate(zip(tokens, values)):
        clean_token = token
        if not clean_token or clean_token.isspace():
            if idx == 0: clean_token = "[CLS]"
            elif idx == len(tokens) - 1: clean_token = "[SEP]"
            else: clean_token = "[PAD]"
        
        if abs(val) < 1e-4:
            html_str += f"<span style='display: inline-block; padding: 2px 6px; margin: 2px; border: 1px solid #ddd; border-radius: 3px; background-color: #fafafa;'>{clean_token}</span> "
        else:
            alpha = 0.15 + 0.70 * (abs(val) / max_val)
            if val > 0:
                color = f"rgba(255, 0, 0, {alpha})"
                border = "1px solid rgba(255, 0, 0, 0.3)"
            else:
                color = f"rgba(0, 0, 255, {alpha})"
                border = "1px solid rgba(0, 0, 255, 0.3)"
                
            html_str += f"<span style='display: inline-block; background-color: {color}; border: {border}; padding: 2px 6px; margin: 2px; border-radius: 3px; font-weight: 500;'>{clean_token}</span> "
            
    html_str += "</p>"
    display(HTML(html_str))

    NEW:

    WHERE APPLICABLE: USE Candidate-label likelihood !!