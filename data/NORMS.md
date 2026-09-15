# Norm sources for conversion rules

Every rule the converter applies must trace to the codification:

> **Беларускі клясычны правапіс: Збор правілаў.** Вільня–Менск, 2005.

The rules below were first written from memory of the norm and checked only against a gold
set written by the same author. Agreement between them proves nothing about the norm, so a rule
is **UNVERIFIED** until a section of the Збор правілаў is cited in its `source` field.

Local copy of the rules text: `data/reference/` (git-ignored; see its README for the source
URLs and checksums). The electronic edition has rules §1–91 and endnotes, not the dictionaries.
Citations below are `Збор 2005, §N`.

**Policy:** no new rule is added without a citation (section/§ and page) in this file.
`tests/test_norms.py` fails if a rule id in `data/rules/*.yaml` or a pipeline-level rule has
no entry here, or an entry has no `source` field.

Format per rule: `id`, `direction`, what it does, `source`. When a citation is added, replace
`UNVERIFIED` with e.g. `Збор правілаў 2005, §18, с. 42`. If the text contradicts the rule, note
it here and fix the rule in the same change.

---

## Assimilative softness — `data/rules/palatalization.yaml`

### palat.apostrophe
- direction: narkamauka → taraskievica
- does: з/с + apostrophe + iotated vowel is written with ь: з’ява → зьява
- source: Збор 2005, §29 ("у т. л. перад [й]: зьезд, … зьява") and §43 (the separating ь
  after soft з, с before е, ё, ю, я)

### palat.geminate.dz
- direction: narkamauka → taraskievica
- does: soft long дз: суддзя → судзьдзя
- source: UNVERIFIED

### palat.geminate
- direction: narkamauka → taraskievica
- does: soft long н, л, з, с, ц, дз are written with ь: насенне → насеньне, жыццё → жыцьцё, вяселле → вясельле
- source: UNVERIFIED

### palat.assim
- direction: narkamauka → taraskievica
- does: з, с, ц, дз take ь before a soft в, м, п, б, л, н, с, з, ц, дз: снег → сьнег, свет → сьвет, дзверы → дзьверы
- source: Збор 2005, §29 for **з, с** ("Памякчэньне с, з перад наступнымі мяккімі зычнымі
  (апроч г (ґ), к, х) перадаецца на пісьме ў межах слова": сьвет, сьнег, радасьць, зьвер,
  зьдзек). The **ц, дз** part is still UNVERIFIED: it falls under §30, audited separately.

### palat.ungeminate.dz
- direction: taraskievica → narkamauka
- does: reverse of palat.geminate.dz: судзьдзя → суддзя
- source: UNVERIFIED (mechanical inverse; valid only if palat.geminate.dz is)

### palat.ungeminate
- direction: taraskievica → narkamauka
- does: reverse of palat.geminate: насеньне → насенне
- source: UNVERIFIED (mechanical inverse)

### palat.unassim
- direction: taraskievica → narkamauka
- does: reverse of palat.assim; keeps a lexical ь (пісьмо)
- source: inverse of palat.assim — Збор 2005, §29 for з, с (§29 Заўвага Б: etymological ь in
  пісьмо, просьба is not assimilative and stays); ц, дз part UNVERIFIED

### palat.unapostrophe
- direction: taraskievica → narkamauka
- does: reverse of palat.apostrophe: зьява → з’ява
- source: inverse of palat.apostrophe — Збор 2005, §29, §43

## Loanwords — `data/rules/loanwords.yaml`

### loan.eu
- direction: narkamauka → taraskievica
- does: word-initial еў → эў: Еўропа → Эўропа
- source: UNVERIFIED

### loan.l_palatalization
- direction: narkamauka → taraskievica
- does: soft л in a curated list of Western stems: план → плян, біялогія → біялёгія
- source: principle — Збор 2005, §55.1 (L soft in Western European loans other than
  anglicisms: плян, кляса, лямпа, блёк, глёбус, лёзунг, ляўрэат, плятформа, салён, лёгіка) with
  the hard exceptions of §56.2 (лава, ладан, ланцуг, блазан, салдат, матацыкл …). The stem list
  itself is only partly checked against those examples.

### loan.i_to_y
- direction: narkamauka → taraskievica
- does: ы after з/с in a curated list of Greco-Latin stems: сістэма → сыстэма, класічны → класычны
- source: UNVERIFIED (stem list unverified)

### loan.f_substitution
- direction: narkamauka → taraskievica
- does: х/хв/п for ф in traditional given names: Фёдар → Хведар, Філіп → Піліп
- source: UNVERIFIED

### loan.g_distinction
- direction: narkamauka → taraskievica
- does: plosive ґ in a closed list of old borrowings: ганак → ґанак, гузік → ґузік
- source: UNVERIFIED (stem list unverified)

### loan.g_remove
- direction: taraskievica → narkamauka
- does: ґ → г everywhere
- source: UNVERIFIED (Narkamaŭka norm; not covered by the 2005 Збор правілаў)

### loan.l_unpalatalization
- direction: taraskievica → narkamauka
- does: reverse of loan.l_palatalization on the same stems
- source: UNVERIFIED (mechanical inverse)

### loan.y_to_i
- direction: taraskievica → narkamauka
- does: reverse of loan.i_to_y on the same stems
- source: UNVERIFIED (mechanical inverse)

### loan.eu_reverse
- direction: taraskievica → narkamauka
- does: word-initial эўр → еўр, except эўрыстыка
- source: UNVERIFIED (mechanical inverse)

## Morphology — `data/rules/morphology.yaml`

### morph.final_tr
- direction: narkamauka → taraskievica
- does: epenthetic а in word-final -тр/-др: тэатр → тэатар, цэнтр → цэнтар
- source: UNVERIFIED

### morph.particle.nya
- direction: taraskievica → narkamauka
- does: standalone ня → не
- source: inverse of morph.particle — Збор 2005, §3

### morph.particle.byaz
- direction: taraskievica → narkamauka
- does: standalone бяз / бязь → без
- source: inverse of morph.particle — Збор 2005, §3, §29

### morph.preposition.z
- direction: taraskievica → narkamauka
- does: зь / безь / празь / церазь → з / без / праз / цераз
- source: inverse of morph.particle — Збор 2005, §29

## Pipeline-level rules — `src/belnorm/rules/morphology.py`

These need the next word, so they run in the pipeline rather than the YAML engine.

### morph.particle
- direction: narkamauka → taraskievica
- does: не → ня and без → бяз when the next word is stressed on its first syllable; then з,
  без/бяз, праз, цераз take ь before a soft onset (з ім → зь ім, без ліку → бязь ліку, без мяне →
  безь мяне), except before an unstressed initial і (з ідэяй, без іголкі). A next word GrammarDB
  does not know, or knows as a homograph with stress in different places (ма+е / мае+), counts
  as not first-stressed.
- source: Збор 2005, §3, §29, §29 Заўвага А; stress position from GrammarDB
  - Збор 2005, §3: jakanne "у першым складзе перад націскам … Паводле гэтага правіла пішуцца
    таксама часьцінка не й прыназоўнік без: ня наш, ня по´йдзе, бяз кры´ўды, бязь зьме´наў".
  - Збор 2005, §29: "Асыміляцыйнае памякчэньне пашыраецца й на прыназоўнікі з, без/бяз, праз,
    цераз: зь вераю, бязь сьлёз, празь лес, церазь сетку; зь юнаком, бязь і´х …"; the book's own
    prose writes "безь яго", "безь пераносаў".
  - Збор 2005, §29 Заўвага А: before an unstressed initial і no [й] develops, so no softening:
    з ідэяй, без іголкі, праз імглу, цераз ільды.
  - Where the stress falls: GrammarDB stress marks (RELEASE-202601, `data/stress/`).
- resolved by the codification (were open questions):
  - не было → **не было**: было´ is stressed on the second syllable, so не is not in the first
    syllable before the stress. The attested *ня было* is Tarashkievich's older rule, which also
    changed the second syllable before the stress ("ня бы-лá"); the 2005 rules dropped it
    (Збор 2005, endnote xxxi).
  - не пойдзем → **ня пойдзем** (§3 "ня по´йдзе").
  - без мяне → **безь мяне**: мяне´ is end-stressed, so no jakanne, but §29 softness applies.
  - без слёз → **бязь сьлёз** (§29, quoted).
- representation: stress is read from the next word's *Narkamaŭka* form (GrammarDB is
  Narkamaŭka); the soft onset is read from the next word *already converted to
  Taraškievica*, where assimilative softness is written. Fixed bug: reading the Narkamaŭka
  form gave без слёз → бяз сьлёз and з снегам → з сьнегам; now бязь сьлёз, зь сьнегам.

### Palatalization audit (same bug class: a softness condition read on a form where softness is not written)

| Place | Reads | Verdict |
|---|---|---|
| morph.particle soft onset (з, бяз, праз, цераз) | next word, Narkamaŭka | **bug, fixed**: now reads the converted Taraškievica form |
| palat.assim / palat.geminate (N → T) | the word being rewritten, repeated to a fixpoint, so later rewrites see earlier ь | ok (property tests; зллю fixed earlier) |
| loanword rules after palatalization | engine re-runs the repeat rules after every pass | ok: no loanword output left with an unmarked softness context |
| lexicon targets | written by hand | ok except the intended lexical ь in пісьменнік, пісьменства, пісьме |
| palat.unassim / ungeminate / unapostrophe (T → N) | the Taraškievica form, where softness is written | ok |
| stress for jakanne | Narkamaŭka form | ok by design (GrammarDB) |
| hyphenated words | each part separately | no softness context across a hyphen in the 100k most frequent words; whether Taraškievica marks one is a codification question |
| `is_palatalizing_context` | — | reference helper, not used at runtime |

Measured on the 100,000 most frequent Wikipedia words plus the gold set, the round-trip corpus
and every lexicon entry: after the fix, no Belarusian N → T output word contains a softness
context the rules would still mark, and the only T → N outputs keeping an assimilative-looking ь
are the пісьменнік family above.

## Known gaps (not implemented, need the codification)

- **Genitive plural -аў** (хвілін → хвілінаў): no rule, no gold coverage; needs a noun list.
  The Збор 2005 rules cover spelling only ("выключна артаграмы") and do not settle it.

## Not a gap: optional forms

- **і → й after a vowel** (мама й тата): Збор 2005, §13 — after a word ending in a vowel the
  conjunction and particle і "можа пераходзіць у й" (*may* become й); an initial і- of a word is
  always written і. Leaving і is compliant, so the converter leaves it.

## Architectural gap: no morphological layer

Lexicon entries are exact word forms. A substitution listed for one form does nothing for the
other forms of the same lexeme, and nothing checks whether a word that looks like a listed stem
is actually that lexeme. These are one missing layer — lemmatize, substitute, re-inflect — not
missing lexicon entries. Do not file them as entries.

Two tiers, because they need different amounts of morphology:

**Tier 1 — same paradigm, only the stem differs.** Lemmatize to confirm the lexeme, swap the
stem, keep the ending. No re-inflection.

| Text form | Expected | Lexicon has |
|---|---|---|
| Аргенціны | Аргентыны | аргенціна → аргентына |
| Бельгіі | Бэльгіі | бельгія → бэльгія |
| Арменіі, Мексікі | Армэніі, Мэксыкі | (not listed) |
| філасофіі | філязофіі | філасофія → філязофія |
| серыяла, сезонная, дэсертаў, алкагольны, метровым, спецыяльнай | сэрыяла, сэзонная, дэсэртаў, алькагольны, мэтровым, спэцыяльнай | серыя, сезон, дэсерт, алкаголь, метры, спецыяльны |

The lemma check is what makes this safe: a bare prefix match on the stem would also rewrite
native words that happen to share it (серыя → сэрыя must not turn серада into сэрада).

**Tier 2 — different paradigm or gender.** Lemmatize, substitute the lemma, re-inflect the new
lemma to the original tag, and change agreeing words.

| Text | Expected | Why the ending changes |
|---|---|---|
| Германіі | Нямеччыны | Германія (fem. -ія) → Нямеччына (fem. -а): gen. -іі vs -ы |
| Іспаніі, Расіі | Гішпаніі, Расеі | lemma substitution; paradigm of the target to be confirmed |
| новы клас | новая кляса | клас (masc.) → кляса (fem.): the adjective, pronouns and past-tense verbs agreeing with it change too |
| Брэста | Берасьця | Брэст (masc.) → Берасьце (neut.) |
| Мінска | Менску | Мінск gen. -а → Менск gen. -у |

Both tiers need GrammarDB morphology (lemmas and full tags); tier 2 also needs a Taraškievica
paradigm for the target lemma, which GrammarDB does not have. Not started.

## Unresolved — deliberately left unconverted

Policy: when sources disagree or the annotator is unsure, the word is **not** added to the
lexicon or the rules and passes through unchanged. A missing conversion is better than a
guessed one. Each item needs the codification (or another cited dictionary) to resolve.

- **Кыргызстан**: Taraškievica sources disagree between *Кыргыстан* and *Кіргізія*. Not in
  the lexicon; Кыргызстан and its forms pass through unchanged. Not in the Збор 2005 rules.
- **Softness across a hyphen**: Збор 2005 §29 limits assimilative softness to "у межах слова"
  plus the four prepositions, and endnote xxxviii leaves hyphenation and compound spelling
  outside the rules. Parts of a hyphenated word are converted separately.

Resolved from this list: **цыкль** does not arise — Збор 2005, §56.2 lists final -л as hard in
матацыкл, so цыкл keeps a hard л; no rule or entry was ever added.

## Lexicon

- **Швейцарыя → Швайцарыя** and **швейцарскі → швайцарскі**: all forms listed in
  `data/lexicon/proper_nouns.tsv`, taken from GrammarDB RELEASE-202601 (paradigms Швейцарыя
  NPIINF2 and швейцарскі ARP) with only the stem changed. Source for the Taraškievica stem:
  Збор 2005, §80 — German ei is written ай (яй) in German loans: Ляйпцыг, Айнштайн, Райх.


`data/lexicon/*.tsv` entries (loanwords, proper nouns, exceptions) are lexical facts, not
rules, but they are equally unverified: they were written from memory, not from a dictionary.
Toponym and country substitutions (Мінск → Менск, Германія → Нямеччына) in particular need a
source.
