# Measruing Morality as public-mindedness

Morality as public-mindedness is defined the following:


Civility as public mindedness or political civility, in opposition to civility as politeness, takes on the political notion of adhering to the liberal democratic values of freedom and equality within a society, and doing so with a common good orientation [@bardonDisaggregatingCivilityPoliteness2023]. In the words of Bardon et al. (2023, p. 311): 
"It is not merely civility applied to the political sphere; instead, it is a kind of civility characterized by an attitude of giving proper weight and recognition to others as free and equal members of society."

Moral civility as the third dimension of incivility, likewise means to recognize others as free and equal, but not in one's way of argumentation, but in, fundamentally, the content and conviction of what is communicated.
It is not about how something is communicated, but about whether it is fundamentally commensurate with liberal democratic values.
It goes beyond mere tolerance or mere conveyance, but means the actual respect and commitment to liberal-democratic values such as free speech, gender equality, and non-violence, as well as their simultaneous outward communication to be received, be it via word or action. 
Bardon et al. 2023 emphasize that this is violated upon an infringement on the fundamental rights, liberties, and the equal civic standing of others.
As examples for the spoken case, they reference discrimination, exclusionism, and hateful speech against groups within society such as women or ethnic minorities.
This also implies a relational concept in which, if the recipient of a morally civic act does not know the actor, the interactionary component is amiss and the act thus not morally civil (or uncivil?),
and same holds vice versa for a disrespectful act, if it is not communicative (Bardon et al. 2023). I argue that within the public parliamentary arena, even if an addressant is not present, 
ikely some member of the addressed group will receive a speaker's communicative action, be it via TV, YouTube, a newspaper article, or another form of reporting.

The liberal democratic values underpinning public-mindedness are not merely philosophical aspirations. Habermas (2022) argues that universal reason-morality,
the Kantian demand that every individual deserves equal respect in their irreducible individuality, was given positive legal force by the constitutional revolutions of the late eighteenth century.
The constitutional orders of liberal democracies did something historically unprecedented: they institutionalized that moral content as enforceable positive right, with human rights declarations marking the moment morality migrated into the medium of constitutional law.
The result is what Habermas calls a permanently unsaturated normative gradient: the gap between constitutional promise and actual practice can never be fully closed, which is why social movements arise whenever the gap becomes too visible to ignore.
Once institutionalized, the moral content becomes a social fact, not merely a philosophical aspiration, and citizens operate under idealizing assumptions derived from it. For the present study, this argument has a direct methodological implication:
grounding moral civility in the Grundgesetz and the UDHR. This, in fact, is not an imposition of external normative standards, but rather a representation of those liberal democratic values deliberated upon, agreed upon, and inscribed in the positive legal order
to which German parliamentary actors are bound. 

NOT:
- politeness/impoliteness
- policy/issue position
- ideology


## Implementation Plan

unit: TOPs ? all speeches by parties within tops?

- in R 

- Word2vec, GloVE, GBERTlarge ? 
- PopBERT is trained on plenary debates !! morlaized in the sense of virtuous people and corrupt elite -> maybe as a benchmark? though this i sbinary
  - We utilized active learning to derive samples that maximize performance. Active learning is a common method in ML to reduce the labeling effort by selecting cases from which the supervised models profit most (Miller, Linder, and Mebane 2020).

- maybe is the annotated DQI dataset avilable?though it is historically outdated.



## Dictionary

lemmatization, or word-piece tokenization? but with word to vec lemmatization should be / should not be necessary? and with BERT i think we did the subword tokenization and then reaggregation into full words or at least sentences? 


example/idea:

there even is the moral foundations dictionary. https://moralfoundations.org/other-materials- but this is not quite the concept i think.
Moral foundations: dimensions of difference that explain human moral reasoning
(Graham, Haidt, and Nosek 2009; Haidt 2013)

Three complimentary approaches:
1. Include terms based on theory
   1. – Specify your theoretical model
    – Define the concepts in your model
    – Operationalize your concepts (making them measurable)
    – Ask other domain experts if your dictionary makes sense to ensure face validity
2. Include terms based on manual discovery
   2.1 Identify “extreme texts” with “known” positions. Examples:
     - Tweets by populist vs mainstream parties (for populism dictionary)
     - Opposition leader and Prime Minister in a no-confidence debate (for opposition vs
government dictionary)
     - Facebook comments to news about natural catastrophes vs football victories (for sentiment
dictionary)
     - Subreddits for white nationalist groups vs regular politics (for racist rhetoric)
    2.2  Search for differentially occurring words using word frequencies
    2.3 Examine these words in context to check their precision and recall
    2.4 Use regular expressions to see whether lemmatization, stemming or wildcarding (adding *
as a suffix) is required
    2.5 Include terms based on a rule (e.g., nearest neighbors in the word embedding space) nested levels.
3. Extend a Dictionary Using word embeddings
   – We can use nearest neighbors in the embedding space to extend a dictionary and increase
confidence in having included all relevant words (recall)
- See e.g., Osnabrügge, Hobolt, and Rodon (2021)
– For an innovative approach, see Hargrave and Blumenau (2022)
4. Validation a dictionary -> human validation?
   -  Paired comparisons tend to give more useful and reliable information than single ratings.
    – Paired comparisons is the strategy used by, among others, Hargrave and Blumenau (2022)
    - Checking Face Validity

{
    moral: {by topic e.g. immigration; ; housing / social system: ; political system:; External relations: ; , household/bduget: ; general: ; kinds of TOPS?: ; human rights: ;constitution: ;state specific consitution: ; }
    immoral: {equivalent just opposite poles ; hate speech: toxicity: }
}

mit kwic(), tfidf, 

NOT:
- politeness/impoliteness
- policy/issue position
- ideology
- Nicht zu viele Wörter! nicht zu seltene

moralsich:
menschenwürde / würde, gleichheit, gleichberechtigung, verfassungsrecht, verfassungswidrig, rechtsstaatlichkeit, grundrechte, minderheitenschutz, rassismus, diskriminierung, pluralismus,  chance, freiheit, respekt, toleranz, zusammenhalt, solidarität, teilhabe

immoral:
exklusion, entmenschlichung, kollektive Schuld?, 
Regenbogenideologie, cancel-culture, anti-deutsch, wokeness, schmarotzer, remigration, gleichschaltung, sexuelle-Abweichung, normal, importärzte, heimatschutz, anti-deutsch, gender-
verbot, volksverräter, überfremdung, abschottung, umerziehung, volkswille, säuberung?

Option A: Eine gerichtete LSS-Skala
Interpretation:

LiberalDemokratischeRahmung
^
𝑖
<
0
LiberalDemokratischeRahmung
​
  
i
​
 <0: stärker anti-liberal-demokratisch gerahmt.

LiberalDemokratischeRahmung
^
𝑖
≈
0
LiberalDemokratischeRahmung
​
  
i
​
 ≈0: neutral, technisch oder ohne erkennbare normative Rahmung.

LiberalDemokratischeRahmung
^
𝑖
>
0
LiberalDemokratischeRahmung
​
  
i
​
 >0: stärker liberal-demokratisch gerahmt.

Der Begriff „amoralisch“ wäre dafür weniger passend als anti-liberal-demokratisch, exkludierend-autoritär oder – abhängig von deinem Codebuch – illiberal.

Option B: Zwei getrennte LSS-Skalen
- niedrig auf beiden Skalen: neutral-technokratisch;
- hoch nur auf LDMoralisation: Rechte, Gleichheit und Würde werden moralisch verteidigt;
- hoch nur auf IlliberaleMoralisation: moralisch-exkludierende bzw. autoritäre Rahmung;
- hoch auf beiden: umkämpfte moralische Auseinandersetzung, etwa ein Konflikt zwischen Gleichheits- und Sicherheits-/Ordnungsansprüchen.

## Checklist

- [ ] Decide the unit of analysis: TOPs vs. all speeches by a party within a TOP
- [ ] Decide modeling approach: static embeddings (Word2Vec/GloVe/GBERTlarge) vs. PopBERT as a
      benchmark (trained on plenary debates, but binary and framed as virtuous-people-vs-corrupt-elite
      — not quite this concept) vs. active learning to select maximally informative labelling
      samples (cf. Miller, Linder & Mebane 2020)
- [ ] Check whether the annotated DQI dataset is available (historically outdated, but worth
      checking)
- [ ] Decide lemmatization vs. word-piece tokenization (word2vec likely needs lemmatization;
      BERT-style subword tokenization + reaggregation may not)
- [ ] Build the dictionary, theory-based pass: specify the theoretical model, define the
      concepts, operationalize them, check face validity with domain experts — ground in the
      Grundgesetz and UDHR per the Habermas argument above
- [ ] Build the dictionary, manual-discovery pass: identify "extreme texts" with known positions
      (German-parliament analogue, e.g. opposition vs. government in a no-confidence debate),
      extract differentially frequent words, check precision/recall in context, decide
      lemmatization/stemming/wildcarding via regex
- [ ] Extend the dictionary via word-embedding nearest neighbors to improve recall (cf.
      Osnabrügge, Hobolt & Rodon 2021; Hargrave & Blumenau 2022)
- [ ] Validate the dictionary: paired comparisons (preferred over single ratings, per Hargrave &
      Blumenau 2022) + face-validity check
- [ ] Finalize dictionary structure: topic buckets (immigration, housing/welfare, political
      system, external relations, budget, human rights, constitution, state-specific
      constitution, general) crossed with moral/immoral poles; immoral side also needs a
      hate-speech/toxicity sub-bucket
- [ ] Keep dictionary terms neither too numerous nor too rare (`kwic()`, tf-idf as filtering
      tools)
- [ ] Explore an idea for a morality scaling measure (not just binary classification) — timely
      since Proksch could become a second supervisor
- [ ] [Carried over from `impolitness_measurement.md` — header there said "TODO for MORALITY"
      but the text talks about an "impoliteness BERT/Gemma"; verify which construct this was
      actually meant for before acting on it.] Package and upload a trained model (BERT and/or
      Gemma adapter) to the HF Hub:

  ```python
  trainer.model.push_to_hub(f"{config.repo_user_id}/{config.model_name}_adapter", safe_serialization=True, max_shard_size='3GB')
  base_model, tokenizer = load_model_and_tokenizer(config,
                                                   quantization=quantized,
                                                   add_pad_token=add_pad_token,
                                                   peft=False,
                                                   load_model_for_sequence_classification=True)
  model = PeftModel.from_pretrained(model=base_model, model_id=f"{config.repo_user_id}/{config.model_name}_adapter")
  model = model.merge_and_unload()

  model.push_to_hub(f"{config.repo_user_id}/{config.model_name}", safe_serialization=True, max_shard_size='3GB')
  tokenizer.push_to_hub(f"{config.repo_user_id}/{config.model_name}")
  ```

  - [ ] Moralization per TOP: 
  
$$
\text{Moralisation}_{i} =\beta_0
+ \beta_1 \text{Partei}_{i}
+ \beta_2 \text{Opposition}_{i}
+ \beta_3 \text{Wahlkampf}_{i}
+ \gamma_{\text{Thema}(\text{TOP}_{i})}
+ u_{\text{TOP}_{i}}
+ u_{\text{Sitzung}_{i}}
+ \varepsilon_{i}
$$

$$
\operatorname{logit}\!\left(
\Pr(\text{MoralischeSprache}_{i} = 1)
\right)
=
\beta_0
+ \beta_1 \text{Partei}_{i}
+ \beta_2 \text{Opposition}_{i}
+ \beta_3 \text{Wahlkampf}_{i}
+ \gamma_{\text{Thema}(\text{TOP}_{i})}
+ u_{\text{TOP}_{i}}
+ u_{\text{Sitzung}_{i}}
$$

Oder

$$
\widehat{\text{Moralisation}}_{i}
=
\beta_0
+ \beta_1 \text{Partei}_{i}
+ \beta_2 \text{Opposition}_{i}
+ \beta_3 \text{Wahlkampf}_{i}
+ \sum_{k=1}^{K-1}
\gamma_k \text{Topic}_{ik}
+ u_{\text{TOP}_{i}}
+ u_{\text{Sitzung}_{i}}
+ \varepsilon_{i}
$$