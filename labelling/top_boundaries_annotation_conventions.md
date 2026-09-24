# Annotation conventions for `top_boundaries_opener_labels.csv`

Working conventions established while hand-labeling TOP openers with
`top_boundaries_annotator.py`. Written down so the rules stay consistent across
sessions and can be recalled.

## Workflow note

The "Open PDF" button opens the actual protocol in the browser — use it whenever
the sampled paragraph alone isn't enough context to judge. Expect the first
stretch of labeling to be about learning what the task is actually asking, not
getting it right immediately: it's fine (expected, even) to go back and forth
across paragraphs and revise an earlier judgment once later context clarifies
it, rather than treating your first pass as final.

## `is_opener`

**Guiding principle: anchor to content, not to phrase.** `is_opener=True`
belongs to whichever single paragraph first tells you *which specific* new TOP
is starting (a number, a title, or both) — never to a paragraph just because it
contains a trigger phrase like "ich rufe auf" / "wir kommen zur". A bare
trigger with no identifying content attached is boilerplate and always False,
even when it's grammatically "the" announcement sentence. This matters beyond
consistency: anchoring to the trigger phrase teaches a future classifier to
detect a surface string (no better than the existing regex); anchoring to
identifying content teaches it the actual semantic signal ("a new topic starts
here, and here's what it is"), which is what stays stable across every state's
different surface convention. When in doubt about a new state/era's style,
find the content, not the phrase.

Default rule following from this: `is_opener=True` on the single paragraph
that actually announces a new Tagesordnungspunkt (matches the rule-based
detector's own intent: a "rufe...auf" / "komme zu" / bare-heading phrasing,
*provided* that paragraph itself carries the identifying number/title).
Everything else is False.

**(2026-09, revised) Metadata-recording and `is_opener` are two independent
decisions — don't infer one from the other.** Earlier guidance said Type/
Sponsor/Topic "live on the opener row only," implying a row could only carry
metadata if it was also `True`. That's wrong in both directions. What's
actually true:

- `is_opener` stays exactly what it always was: a deliberate judgment call
  about whether a genuinely new procedural/thematic unit starts *at this
  row*, per "anchor to content, not phrase" above. Nothing about metadata
  changes that test.
- `type`/`sponsor`/`topic` can be recorded on **any** row where that specific
  piece is actually printed in the text — whether or not that row is also
  `is_opener=True`. A Beschlussempfehlung's citation line, or a sponsor line
  that trails a title, often just adds detail to a TOP that already opened
  elsewhere; recording its type/sponsor there is about not losing recoverable
  information, not a claim that the row opens anything.
- Critically: **`type`/`sponsor` being filled on a row is not evidence that
  the row should be `is_opener=True`.** Do not reverse-infer one from the
  other. (A 2026-09 pass briefly did exactly this — flipped ~83 rows to
  `True` solely because they had `type`/`sponsor` filled — and had to revert
  all of them. The two fields answer different questions.)

Within that, when a TOP's citation genuinely spans multiple rows and more
than one of those rows independently deserves `is_opener=True` in its own
right (each is itself the anchor for a distinct title, sponsor, or
sub-document — not merely "has some metadata"), each gets its own `True` and
records only what it actually contains, rather than everything being
force-merged onto one row (e.g. `be_19_54/588`: title + topic is `True`;
`/589`, a distinct following citation "Antrag der AfD-Fraktion, Drucksache...",
is independently judged to open nothing new here and — depending on the
specific case — may or may not also be `True`; jointly-cited documents like a
Gesetzentwurf and its accompanying Bericht der Landesregierung can likewise
each be their own opener when each is independently a distinct citable
document, per your own read of the specific case).

One exception still applies:

- **True duplicate reprint.** When a row is a *word-for-word* repeat of a
  citation already fully captured on the row before it (the classic bracketed
  official-record reprint of what the presiding officer just said aloud, with
  no new piece at all) — that reprint stays `is_opener=False`. Its
  content, if any is worth keeping, can still be recorded via `type`/
  `sponsor` per the point above; the row just isn't itself an opener.

**Pitfall: "Abstimmung" and "Artikel N" calls are (usually) not openers.**
A vote-taking announcement ("Wir kommen zur Abstimmung...") or an
article-by-article call during a bill's reading ("Ich rufe auf Artikel 1...")
almost always sits *inside* an already-open TOP — the real, telling opener
came earlier ("ich rufe auf" for the TOP itself), and these are just
procedural steps through that same already-identified item, not new units.
Don't mark them `True` on the assumption that "ich rufe auf" phrasing always
signals an opener — the phrase recurs for purely mechanical sub-steps too.
This is a note for prompting/self-review, not a claim that either of us has
been getting it wrong in bulk — just a recurring trap worth naming.

**"Persönliche Bemerkung"/"persönliche Erklärung" are never openers.** A
procedural device (e.g. §89 GO in `mv_4_74/1534`, §112 in `by_18_106/1200`)
letting an MP make a brief, time-limited statement to correct how their own
words were represented by another speaker, or respond to a personal attack —
not to reopen substantive debate on the matter at hand. Explicitly framed as
happening "außerhalb der Tagesordnung" (outside the regular agenda) and never
carries actual policy content, so it gets no opener regardless of how
prominently it's announced.

**Thematic unit vs. procedural TOP — they don't have to be 1:1.** A `top_seq`
is a scheduling container (what's on the printed agenda as item N); a thematic
unit is a content unit (what's actually being talked about). Usually they
coincide — one TOP, one theme. But when one TOP bundles several genuinely
distinct thematic units, mark *each* unit's identifying row as its own
`is_opener=True` with its own Type/Sponsor/Topic, even though only one of them
is a TOP-opener in the procedural sense:

- **Fragestunde.** Opened once as a single TOP, but the individual oral
  questions inside it are not topically coherent as one bundle — each question
  can be about a completely different policy area. Each question's chair
  announcement ("Ich bitte nun den Abgeordneten X, die Frage N zu stellen")
  gets its own opener flag.
  **Anfrage vs. Zusatzfrage**: the Anfrage is the pre-submitted question that
  opens the exchange; a Zusatzfrage is a live follow-up (often from a
  *different* MP than the original asker) probing the same answer just given.
  A Zusatzfrage stays on the Anfrage's subject by parliamentary rule, so it's
  a continuation, not a new opener — same logic as a vote continuing the TOP
  it belongs to, not starting a new one.
- **Joint-TOP openers** ("Ich rufe die Punkte 7 bis 14 der Tagesordnung
  gemeinsam auf:" followed by "Punkt 7:", "Punkt 8:", ...) — same logic, each
  "Punkt N:" sub-item is its own thematic unit and gets its own opener flag,
  not just the joint announcement line.

This is a deliberate, known mismatch between annotation granularity (thematic)
and the current rule-based detector's granularity (procedural TOP only) — not
a labeling bug, and not something the detector needs to be able to reproduce.

### Sitzungseröffnung gets its own opener (2026-09)

Same broadening as Fragestunde/joint-TOP above, at the other end of the
protocol: the session-opening remark (greeting, "Ich eröffne die N. Sitzung...",
roll-call/quorum statement) is a genuine thematic unit in its own right — it
already gets `topic=Prozedural` by convention — so it now also gets
`is_opener=True`, even though `top_boundaries.py` never tried to detect it
(it only looks for Tagesordnungspunkt-announcement cues, not session-opening
cues). This is a scope broadening for a future topic-*change* classifier that
cares about "does a new unit start here" in general, not a claim that the
rule-based detector is wrong to miss it.

Applied by finding, per protocol, the first `pre` row (before the first
already-True row) matching an Eröffnung cue — not literally "row 1," since the
opening remark is sometimes split across several consecutive un-joined `pre`
rows (a bare "Guten Morgen!" greeting, then a separate row with the actual
"Ich eröffne..." declaration) and only the row that actually names/declares
the session gets the flag, per the anchor-to-content principle. Cue-matching
caught most state phrasings directly ("eröffne die X. Sitzung", "Die Sitzung
ist eröffnet") but also needed broadening to states that never say "eröffne"
at all and instead use "begrüße Sie zur X. Sitzung" or "heiße Sie willkommen
zu unserer heutigen, X. Sitzung" (NW, HE, RP, BB) — same function, different
verb.

Known exceptions, left as `is_opener=False` deliberately:

- **`sh_15_66`, `sh_19_62`**: this transcript's captured `pre` paragraphs
  start mid-debate (granting the floor for an already-in-progress
  Dringlichkeit/Geschäftsordnung item) — no Eröffnung was captured for these
  two at all. Don't force one; the absence is a real gap in what got sampled,
  not a missed cue.
- **`sh_18_16`**: same situation for the protocol's actual start, but a
  *mid-protocol* "Ich eröffne wieder die Sitzung" (resuming after a recess)
  appears later on and got flagged instead — a legitimate instance of the same
  category (a session (re-)opening), just not the transcript's first moment.
- **`th_5_2`**: never self-references its own session number or says
  "eröffne" anywhere in the preamble (pure "Guten Morgen... Willkommen"
  greeting) — a blind cue-match would have false-positived on an unrelated
  "2. Sitzung" mention (the Ältestenrat's own committee meeting, several rows
  later). Assigned to row 1 by the same greeting-is-the-opener logic as
  everywhere else, but this one needed a manual override rather than a clean
  regex hit — worth rechecking if this pattern shows up again elsewhere.
- **`bb_4_14`**: pre-existing `is_opener=True` at row 1, left untouched, but
  its content ("Wir haben gestern die 14. Sitzung unterbrochen und setzen sie
  heute mit der weiteren Behandlung fort") is a continuation of an
  *interrupted* sitting, not a fresh Eröffnung — flagged here in case it's
  worth revisiting later, not fixed now.

### Adjacent double-openers: bug vs. legitimate pattern

A 2026-09 bulk fix (clearing a backlog of topics that had a `topic` set but no
`is_opener` flag — leftover from earlier-session taxonomy work) introduced 263
cases of two *consecutive* rows both marked `is_opener=True` for what was
really one single TOP, because that fix only checked "does this row have a
topic," not "is an adjacent row already the real opener." The most common
shape: a bare trigger that happens to *also* contain the TOP number (e.g. "...
schließe ich Tagesordnungspunkt 2 und rufe Tagesordnungspunkt 3 auf.") stayed
True from earlier labeling, and the bulk fix then *also* flagged the next row
(the actual title) — double-counting one TOP. Resolved by reading full
paragraph content for every adjacent same-protocol True/True pair and applying
the anchor-to-content rule per-pair: 216 rows had the pure-title/no-own-number
row demoted to False (number-bearing row stays canonical); 11 rows had the
content-free lead-in demoted to False (title-bearing row stays canonical,
same as the pre-existing "split announcement sentence" rule above); 24 pairs
were left untouched as genuinely intentional double-openers.

The surviving legitimate double-opener patterns (do not "fix" these if they
show up again in a future audit):

- **Fragestunde questions with a named asker**: "Ich rufe die Frage 2 auf,
  gestellt von Herrn Abgeordneten X. Sie lautet:" already carries a real
  identifier (asker + ordinal) even before the question text itself, so both
  rows are True (`sl_15_28`, alongside the pre-existing Fragestunde exception
  in `mv_6_4`). Contrast with an announcement that names only the *requesting
  party*, not a per-item identifier (e.g. "Wir kommen zu der von der
  DIE-LINKE-Fraktion beantragten Aktuellen Aussprache zum Thema:") — that one
  has no standalone identifying content and IS the ordinary split-sentence
  bug (first row False).
- **Joint "Punkte X und Y der Tagesordnung" announcements**: when the trigger
  names *two or more* TOP numbers together, each subsequent sub-item title
  gets its own True (`rp_15_44`, `rp_17_10`, `sl_17_32`). A single-number
  trigger ("Wir kommen zu Punkt 16 der Tagesordnung:") followed by one title
  is NOT this pattern — that's the ordinary split-announcement bug, and the
  title-only row is demoted (the number-bearing trigger stays canonical).
- **Lettered joint sub-items** ("lfd. Nr. 22:" followed by "a) ...", "b)
  ..."): each lettered sub-item is its own thematic unit, same logic as the
  "Gemeinsame Beratung a)/b)/c)" pattern above (`be_18_21`, `sh_19_62`).
- **Bundled Unterrichtung/Wahlen readings** ("Ich rufe auf die Punkte 20a, 28,
  29 und 20b, Unterrichtung durch..." followed by a chain of bracketed
  `[...]` items): each bracketed item is a distinct thematic unit within the
  joint announcement (`hh_22_37/406-424`).
- Plus the two already-documented ambiguous cases kept as both-True by
  deliberate choice under genuine structural uncertainty: `sn_4_64/287-288`
  and `bw_17_93/1042-1043`, and the `st_8_27/229-230, 843-844` joint
  containers.

One known unresolved edge case, not yet given a general rule: a
presiding-officer-change stage direction can interrupt an opener sentence
mid-way (e.g. "Wir kommen zu der" / "(Vizepräsidentin X)" / real title several
paragraphs later, debate content interleaved in between) — too irregular to
auto-fix, needs a manual look per case (check the PDF).

### What context a future classifier would need

Not the same answer for both granularities. A TOP-level opener is usually
self-contained in the `pre` paragraph(s) themselves — the announcement carries
its own identifying content, at most needing the next `pre` paragraph (the
citation line). A thematic-sub-unit boundary (Fragestunde questions, joint-TOP
sub-points) often is *not* self-contained — the `pre` fragment can be as thin
as "Punkt 8:" with zero substance in it, so detecting that the topic actually
changed there would need the surrounding debate content (not just `pre`
paragraphs), not just the presiding officer's own text. Design question for
whenever that classifier actually gets built, not something the annotation
itself needs to resolve now.

**Hardest known case: `hh_16_74`'s Fragestunde.** All 8 question-openers are
correctly labeled (verified 2026-09), but the chair's announcement carries
*zero* subject-matter content at all — "Die erste Frage geht an den
Abgeordneten Herrn Hackbusch," "Ich rufe dann die dritte Frage von Herrn Hesse
auf." Just an asker's name and an ordinal; contrast with HB ("Die neunte
Anfrage befasst sich mit dem Thema...") or BW ("Mündliche Anfrage des Abg. X –
TITLE"), where the `pre` paragraph names the subject itself. Here the topic
was only recoverable by reading past the announcement into the MP's own
spoken question. A classifier trained only on `pre`-paragraph text has no
lexical signal to work with here at all — this protocol is the clearest
illustration of why the sub-unit-boundary problem needs surrounding-content
features, not just a better `pre`-paragraph model.

### Cross-context variation & the limits of surface-pattern detection

TOP-announcement conventions differ by debate type (a regular TOP opener looks
nothing like a Fragestunde's per-question chair announcements), by Land (BE's
split "Ich rufe auf" / "lfd. Nr. N:", BY's "Ich rufe auf" + citation line, MV's
announcement + repeated non-bracketed citation, HH's bracketed reprint, HE's
bare heading — all different conventions for the same underlying event), and
plausibly across time within the same Land too. More importantly, the presence
or absence of an explicit marker like "ich rufe auf" is neither necessary nor
sufficient evidence of an actual topic boundary: sometimes it is the genuine
marker of a new TOP, sometimes a bare TOP-number listing alone marks a real
change and sometimes it doesn't, and sometimes a TOP changes implicitly with no
explicit announcement in the presiding officer's text at all — recoverable
only from reading the surrounding debate content, not from the `pre` paragraph
in isolation. This is why a context-aware classifier (something that reads
the surrounding debate rather than pattern-matching one paragraph at a time)
is likely to outperform the current rule-based regex detector on this task.

Also note: the announced TOP numbers themselves are not enumerated in order
within a protocol — they can jump around wildly (20, 47, 21, 34, ...), since
items get reordered/rescheduled during the actual session while keeping their
original number from the printed agenda. Don't assume `top_number_raw` is
monotonically increasing, or use its ordering as a sanity check — `top_seq`
(the position-based running count assigned during detection, not the announced
number) is the only reliably sequential field.

## `type`

Document/instrument type only (Antrag, Gesetzentwurf, Bericht, Beschlussempfehlung,
Anfrage, Große Anfrage, Abstimmung, ...) — not the reading stage. First vs. second
Lesung of the same Gesetzentwurf both get `type=Gesetzentwurf`; reading stage is
not tracked as a separate field.

Multiple types on one TOP (e.g. a citation reading "Beschlussempfehlung und
Bericht des Ausschusses...", or "Beschlussempfehlung ... Antrag der Fraktion
X") are joined with "; ", **in source-text order** — same principle as
multi-party sponsors below, not a fixed schema order. So "Antrag;
Beschlussempfehlung" and "Beschlussempfehlung; Antrag" are both correct
depending on which word the citation actually names first; don't
"normalize" one into the other. (A 2026-09 pass retroactively fixed ~65 older
rows that had only captured one of several type-words actually present in
their citation — labeled before this convention was applied consistently.)

Personnel-election TOPs (Wahl der/des ..., a committee-member election, a
Präsident/Ministerpräsident election, etc.) get **`Abstimmung; Wahlvorschlag`**
on the canonical opener row, not "Wahlvorschlag" alone — both the nomination
and the vote on it are genuinely part of what that TOP is. "Wahlvorschlag"
alone is only for a bare citation *line* naming one specific nomination
document (e.g. inside a list of several competing Wahlvorschläge), not for the
TOP's own canonical row.

**Structural/format tags on container headings** work the same way as any
other non-opener row carrying metadata (see the `is_opener` section above —
recording and opener-status are independent). A bare `Fragestunde`/
`Aktuelle Stunde`/`Aktuelle Debatte` heading line stays `is_opener=False` (it
names a *format*, not a citable document), but still gets that word as its
own `type` value so the format is findable/filterable (e.g. `nw_13_149/19`:
`type=Aktuelle Stunde`, `is_opener=False`, because the actual opener with
content is a few rows later). `bb_7_63/1164` + `/1171` is the same pattern at
document level: `/1164` is the opener (`type=Gesetzentwurf; Bericht`, the real
topic), `/1171` records `type=Bericht` for its own Bericht der Landesregierung
citation while staying `is_opener=False` and topic-blank — it's the same
subject as `/1164`, just not independently an opener in its own right. Do
**not** treat a filled `type`/`sponsor` as license to flip a row to `True` —
see the explicit warning against that inference above.

`Dringlichkeitsantrag` (urgent motion — filed under expedited rules, skips
normal committee scheduling) gets its own type value, same tier as the other
procedurally-distinct motion subtypes (`Änderungsantrag`, `Entschließungsantrag`,
`Alternativantrag`) — not folded into plain `Antrag`. Watch for the phrasing
variant **"Dringlicher Antrag"** (adjective+noun, seen in HE) as well as the
compound noun "Dringlichkeitsantrag" — same instrument, both map to this type
value. (A 2026-09 pass retroactively reclassified 18 rows across
`by`/`hb`/`mv`/`he` that had one of these two phrasings in their citation text
but were typed `Antrag` before this distinction was drawn.)

`Einzelplan` — a Haushaltsgesetz's individual departmental budget chapter
("Einzelplan 05 – Inneres und Sport –"). Gets its own opener with the
department's substantive `topic` (see the Haushalt/Einzelplan note under
`topic` below) — `type=Einzelplan` records that this row's specific citable
form is a budget chapter heading, same spirit as tagging `Fragestunde`/
`Aktuelle Stunde` as a format rather than leaving `type` to imply an
Antrag/Gesetzentwurf that isn't actually there.

`Übersicht` — a compiled list/overview document cited as its own instrument
(e.g. `bb_7_63/1339`, an `Übersicht` of petitions from the Petitionsausschuss)
— distinct from `Beschlussempfehlung`/`Bericht`, which are the committee's own
recommendation/report rather than a raw compiled list.

## `sponsor`

- Multi-party sponsors are joined with "; ", in **source-text order** — not
  alphabetized or otherwise canonicalized. If a citation says "der Fraktionen
  der GRÜNEN und der SPD", the label is "GRÜNE; SPD", not "SPD; GRÜNE".
- Party abbreviations follow `preprocessing/nsc_rule_parser.py`'s canonical
  forms (e.g. "REP" not "Republikaner"; "FDP" not "FDP/DVP").
- Institutional (non-party) origins: `Ausschuss`, `Senat`, `Landesregierung`,
  `Landesbeauftragte`.
- `pre` = presiding officer / parliament president as sponsor/author (e.g. a
  Bericht des Präsidenten, or an Unterrichtung durch die Präsidentin). This is
  the standardized convention — not "Präsidentin".
- `gov` = government/Staatsregierung as a generic sponsor when no more specific
  institutional label fits.
- Historical PDS references are normalized to `LINKE`, not kept as a separate
  historical party name — matches how Die Linke's predecessor is labeled
  throughout this file regardless of era.

## Joining for final TOP-level analysis (not for annotation)

The conventions above are about how to *label* the raw, unjoined per-paragraph
data — keeping every `pre` fragment as its own row lets you inspect and verify
each one individually. This matters more than ever now that metadata is
recorded per-row rather than merged onto one canonical line (see the 2026-09
revision under `is_opener`): a single TOP can legitimately be five or six
`True` rows in a row, each with a sliver of the total citation. That's the
*annotation* granularity, deliberately kept fine so nothing gets lost or
force-merged during labeling — it is not the shape of the final dataset. For
the **final TOP-level analysis/classification**
(building the actual per-TOP dataset used downstream, as opposed to this gold
label file), the consecutive `pre` paragraphs that make up one TOP's opening —
the announcement, its bracketed/non-bracketed citation reprint, and any
split-sentence fragments — should be **joined into a single text unit** per TOP.

Why:

- They're all uttered by the same speaker (the presiding officer) back-to-back,
  with no other speaker's contribution in between — there's no real
  communicative boundary between them, only a transcription/typesetting one
  (a page break, an official-record bracket insertion, a mid-sentence
  presiding-officer-change aside).
- The paragraph split is an artifact of how the shorthand record was chunked,
  not a meaningful content boundary — exactly why deciding "which fragment
  gets is_opener/Type/Sponsor/Topic" during annotation has been an ongoing
  source of inconsistency all session (bracket reprints, "lfd. Nr." splits,
  the MV-style non-bracketed citation continuation). Joining removes the need
  for that decision downstream: one TOP, one row, one full text.
- Analyzing the fragments separately would double- or triple-count the same
  opening event in any paragraph-level statistic (e.g. counts of TOPs opened,
  text-length/style measures), and a bare fragment like "lfd. Nr. 5:" carries
  no linguistic content worth analyzing on its own — it only makes sense
  joined with the announcement and citation around it.
- It matches the metadata convention already established here: Type/Sponsor/
  Topic belong to one canonical unit per TOP, not to whichever fragment
  happened to be labeled. Joining makes that the actual data structure instead
  of a rule to remember when reading the CSV.

This does not change how `is_opener` is labeled in this file (still one row
per raw paragraph, per the rules above) — it's an instruction for whatever
script builds the final per-TOP analysis table from this labeled data plus the
raw paragraphs.

## `topic`

Classify by substantive policy lever/subject — never by legal instrument,
surface keyword, or institutional bundling (a Rechnungshof audit report, a
Rechtsausschuss report, or a Fraktion's motion are containers, not topics; the
question is always "what is this actually about").

**Pitfall: "Integration" is a false-friend word — it means two unrelated
things in Landtag content, and neither is its own topic.** A retired
`Integration` bucket (2026-09 cleanup) turned out to conflate immigrant/
migrant integration policy (→ `Migration und Asyl`; e.g. `rp_17_10/25`'s
residency-requirement-for-integration Antrag, `rp_15_44/1229`'s
Migration-und-Integration Enquete-Kommission) with disability-inclusion
content (→ `Inklusion`; e.g. `he_19_147/1131`'s Bundesteilhabegesetz
implementation, `bw_16_31/1907`'s disabled-employment report — both
surfaced by committees literally named "Ausschuss für Soziales und
Integration," where "Integration" meant disability participation, not
migration). Don't classify anything as bare "Integration" — determine which
of the two it actually is and use the specific topic. Same caution applies
to `Soziales` (also retired): it scattered across `Arbeit und Beruf`
(Mindestlohn/Tariftreue content), `Sozialleistungen` (Hartz-IV/KdU content),
and other specific buckets — it was never a real category of its own, just
an unresolved catch-all.

A `topic` can legitimately sit on a row with no `is_opener` anywhere near it
and no `pre` paragraph announcing a change — this happens when the actual
subject drifts mid-debate purely through what speakers say, with no chair
announcement marking a new TOP (e.g. `be_15_85/780`: topic shifts from
Migration und Asyl to Jugend und Familie mid-speech, several speakers into the
same formal TOP, with no `pre` boundary anywhere). Don't go looking for a
missing opener in these cases — the absence of one is correct, not a gap to
fill; see the "implicit TOP change" case already noted under Cross-context
variation above.

- **Haushalt Einzelplan (departmental budget chapter) walkthroughs each get
  their own opener, but the topic is `Haushalt` for every one of them — settled
  2026-09, after two reversals.** *Each* Einzelplan chapter still gets its own
  `is_opener=True` row (`type=Einzelplan`) — that part survives from the
  in-between version of this rule: a chapter's floor debate is a genuine,
  self-contained discussion (real speeches, real disagreement, sometimes
  hundreds of paragraphs), not a mechanical vote tally, so it isn't collapsed
  into the one overarching Haushaltsgesetz opener. What changed back is the
  `topic`: it's `Haushalt` on every Einzelplan row, not the department's
  substantive policy area (so "Einzelplan 05 – Inneres und Sport –" is
  `topic=Haushalt`, not `Innere Sicherheit`) — structurally, every Einzelplan
  chapter is still part of the same parent Haushalt TOP regardless of which
  department it covers, and department-specific topics were fragmenting what
  is analytically one recurring event (the annual budget walkthrough) across
  a dozen unrelated-looking topic labels. The overarching Haushaltsgesetz row
  itself is also `topic=Haushalt` (`type=Gesetzentwurf; Beschlussempfehlung;
  Bericht`, for the bill-framing/general-debate portion). Any genuinely
  separate motion/bill interspersed between Einzelplan chapters for scheduling
  convenience (its own Drucksache, unrelated subject — e.g. a Dringlicher
  Entschließungsantrag debated jointly with a specific Einzelplan) still gets
  its own opener with its own real topic, same as before — it's only the
  Einzelplan chapter rows themselves that are uniformly `Haushalt`.
  `he_18_26`'s 12 Einzelplan rows, `be_17_15`'s 11, and `v1`'s `bb_4_14` (6)
  and `sh_18_16` (13) were all corrected to this rule 2026-09 — the v1 pair
  had every Einzelplan chapter sitting at `is_opener=False` (a different,
  older inconsistency, since v1 predates the per-chapter-opener rule
  entirely), so those were flipped to `True` at the same time as getting
  `topic=Haushalt`.
- Merge near-duplicate categories only when the content is genuinely
  indistinguishable (e.g. Recht → Justiz, Wissenschaft → Hochschulen were pure
  naming leftovers). Keep categories separate even at low volume when they
  represent a real distinct axis relevant to the research question — e.g.
  Gleichstellung was kept separate from Menschenrechte, and
  Abgeordnetenrecht (internal parliamentary organization: MP/Fraktion status —
  renamed from "Innerparlamentarisch" once it collided with the political-
  conflict category below) was kept separate from Interparlamentarisch
  (cooperation between different countries' parliaments, e.g.
  Ostseeparlamentarierkonferenz) even though both were thin. Watch for
  "inner-" vs "inter-" as genuinely different prefixes, not a typo of each
  other — and don't reuse "Innerparlamentarisch" as a topic value again, it's
  retired.
- A full topic-list audit (2026-09) caught categories that named an
  institution, legal instrument, or surface keyword instead of a policy
  lever, which let unrelated content collide inside them:
  - **`Bauwesen` → renamed `Stadtentwicklung`.** Its content was never just
    construction law — Bebauungspläne, municipal land sales, and
    Stadtentwicklungsausschuss reports were already in there. The new name
    matches what the category actually covers, and also absorbs genuinely
    cross-sector/general physical-infrastructure content (e.g. a bundled
    Große Anfrage spanning both road resurfacing and building-condition
    reports, or a general "how large is the infrastructure investment
    backlog" question) that doesn't reduce to one specific asset type.
  - **`Landesentwicklung` (new, 2026-09) — state-wide/regional spatial
    planning, distinct from `Stadtentwicklung`'s city/municipal scale.**
    "Stadtentwicklung" literally means city development — it fits a
    Städtebauförderung (city-building funding) Große Anfrage fine
    (`ni_14_107/1076`), but not content about the *ländlicher Raum* (rural
    area/countryside) specifically, which was wrongly forced into
    `Stadtentwicklung` before this split (`ni_14_107/17` — an Aktuelle-Stunde
    theme titled "Ministerpräsident Gabriel erdrückt den ländlichen Raum";
    `ni_14_107/660` — an Antrag titled "Erfolgreiche Politik für den
    ländlichen Raum fortsetzen"). Use `Landesentwicklung` for rural/regional
    development, `Stadtentwicklung` for city/municipal-scale content — the
    axis is urban vs. rural/state-wide scale, not which specific instrument
    or committee is involved.
  - **`Infrastruktur` retired.** It was a surface-level noun duplicating
    whatever the actual asset was: pure road content moved to `Verkehr`,
    pure building content and genuinely cross-sector/general content moved
    to `Stadtentwicklung` (see above), and one row about TV cable network
    modernization moved to `Medien` — a domain that had nothing to do with
    the others, which is exactly the tell that "Infrastruktur" wasn't a
    coherent lever. Don't reuse it as a topic value.
  - **`Technologie` narrowed.** Keep it only for content where technology/
    innovation policy is itself the substantive lever (broadband rollout,
    a geodata-access law, a gene-technology project). Don't use it just
    because "digital" or "WLAN" appears in the text — "Digitalisierung im
    Verkehrssektor" is a transport-policy item, "WLAN in
    Flüchtlingsunterkünften" is a migration/accommodation item; the
    technology is the surface keyword there, not the lever. A mobile-network-
    coverage complaint framed around a specific train route was judged to
    belong with the transport-service content it was filed alongside
    (`Verkehr`), not `Technologie` — a genuinely close call, revisit if a
    clearer pattern emerges.
  - **`Soziales` narrowed; new `Sozialleistungen` split off.** `Soziales` had
    become a catch-all for anything welfare-adjacent, bleeding into tax
    policy (Solidaritätszuschlag → `Finanzen`), housing subsidy/tenant
    protection (→ `Wohnen`), labor-market/wage law (Mindestlohn,
    sozialversicherungspflichtige Beschäftigung → `Arbeit und Beruf`), and
    civil-service pension administration (Pensionsfonds → `Verwaltung`).
    `Sozialleistungen` is now the home for actual benefit/anti-poverty law
    — SGB II/XII Regelsätze, Hartz-IV/Grundsicherung reform, pension reform
    framed as anti-poverty policy. `Soziales` still exists for genuinely
    diffuse social-policy content with no narrower lever to anchor to (e.g.
    a Regierungserklärung about "holding society together" with no specific
    policy substance named).
- `Regierungskritik`: generic "the government/coalition is doing a bad job"
  political attacks with no specific policy substance to anchor them
  elsewhere — distinct from Abgeordnetenrecht (that's about MP/Fraktion
  organizational *law*, not political rhetoric). Renamed to
  **`Politikerkritik`** and broadened once a second case (a formal
  Missbilligungsantrag/censure motion against individual MPs, not the
  governing coalition) showed the original scope was too narrow: it now
  covers criticism/censure targeting *any* politician's or party's conduct
  or performance — government or opposition, a coalition's record or an
  individual MP's public behavior. Test for whether something belongs here:
  is the motion *about* a politician's/party's conduct or performance
  itself, not about a policy area they're associated with — otherwise almost
  any critical motion would qualify and the category stops meaning anything.
- `Justizvollzug`: the umbrella for the whole custody/detention-system domain
  — Strafvollzug (sentence execution), Jugendarrest, Maßregelvollzug (forensic-
  psychiatric detention), and general Justizvollzug content all go here rather
  than being split by their technically-distinct legal categories.
- `Korruption und Amtsmissbrauch`: broader than bribery-type corruption alone
  — also covers conflict-of-interest/office-abuse oversight (officials'
  company board memberships, state shareholdings in companies, anti-corruption
  registries and offices, Minister-Karenzzeit/cooling-off regulation like
  `be_17_15/1164`). Don't put a Parlamentarisches Kontrollgremium/
  Kontrollkommission law here just because it's an oversight body — those are
  intelligence-service oversight specifically and belong in Verfassungsschutz.
- `Parlamentarische Kontrolle` (new, 2026-09): the parliament *establishing or
  running an investigative/oversight body itself* — Untersuchungsausschuss
  formation and reports (`bb_7_63/445`: setting up an inquiry into the BER
  airport's cost/schedule overruns; `bb_3_100/12` and `/330`: inquiry reports
  into the LEG state-housing-company scandal and the Chipfabrik
  Frankfurt/Oder investment scandal) — regardless of whether the underlying
  subject under investigation is corruption, mismanagement, or something
  else entirely. The lever here is "parliament is exercising its oversight
  function," not the substance of what's being investigated. Contrast with
  `Korruption und Amtsmissbrauch`, which is about substantive corrupt
  conduct or conflict-of-interest policy itself — a Untersuchungsausschuss
  into a genuine bribery scandal would still be `Parlamentarische Kontrolle`
  (it's an inquiry-mechanism topic), not `Korruption und Amtsmissbrauch`,
  unless the row itself is about the anti-corruption policy substance rather
  than the inquiry mechanism. (`bb_3_100/12` and `/330` were originally typed
  `Korruption und Amtsmissbrauch` before this distinction was drawn —
  reclassified.)
- `Außenpolitik` (new, 2026-09): foreign-policy/international-relations
  content a state parliament has no formal competency over but still debates
  — solidarity resolutions, symbolic condemnations. Example: `by_18_106`'s
  three jointly-debated Dringlichkeitsanträge on the Russian invasion of
  Ukraine (`/606` SPD, `/608` FDP, `/610` FREIE WÄHLER/CSU joint) — "Solidarität
  mit der Ukraine", "Putins Aggression Einhalt gebieten", "Europäische
  Friedensordnung bewahren". Don't stretch `Verfassung` or `Katastrophenschutz`
  to cover this — neither fits (no domestic constitutional or disaster-response
  content), and it's a distinct-enough recurring category to warrant its own
  bucket rather than force-fitting.
- `??` is a deliberate self-marker for "not yet decided" — not a real topic.
  Sweep these periodically rather than leaving them.
- `Prozedural` is the catch-all for content with no policy substance at all:
  session opening/closing (Sitzungseröffnung), batch/consent votes, routine
  legislative housekeeping (e.g. a Senate's list of issued Rechtsverordnungen),
  swearing-in ceremonies. In particular, the first `pre` contribution of a
  protocol (or the first joined unit, see above) is labeled `Prozedural`
  whenever it's an Eröffnung/session-opening remark (welcoming guests,
  announcing absences, calling the house to order) — this is the default for
  that position, not a special case needing its own category. Rows here mostly
  sit at `top_seq=0`, i.e. before any
  real TOP has opened — exclude them from topic-frequency-per-TOP analysis for
  that reason, not because the label is wrong.

## Unresolved / pending review

Rows flagged during audits that need your own read (PDF or content check),
not something fixable by rule — kept here so they don't get lost:

- `be_15_85/1274-1276`: presiding-officer-change stage direction interrupts an
  opener sentence mid-way, real title several paragraphs later with debate
  content interleaved in between. Too irregular to auto-resolve.
- `hb_16_51/420` and `hb_17_82/481`: both mention "Große Anfrage" only in
  passing (describing the Senate's right to respond), not as their own
  citation — the real Type/Sponsor for these TOPs is presumably on an earlier
  paragraph in the same group, not yet located.
- `sl_17_32/31`: the motion's title mentions "den angekündigten Gesetzentwurf
  zur Altschuldenregelung" as its *subject* (a different, federal bill it's
  urging support for), not its own document type — its actual Type/Sponsor
  citation is probably a few paragraphs further in, not yet found.
