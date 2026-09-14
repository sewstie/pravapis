# Norm sources for conversion rules

Every rule the converter applies must trace to the codification:

> **Беларускі клясычны правапіс: Збор правілаў.** Вільня–Менск, 2005.

The rules below were written from memory of the norm and checked only against a gold set
written by the same author. Agreement between them proves nothing about the norm, so every
rule is **UNVERIFIED** until a section of the Збор правілаў is cited in its `source` field.

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
- source: UNVERIFIED

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
- source: UNVERIFIED

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
- source: UNVERIFIED (mechanical inverse)

### palat.unapostrophe
- direction: taraskievica → narkamauka
- does: reverse of palat.apostrophe: зьява → з’ява
- source: UNVERIFIED (mechanical inverse)

## Loanwords — `data/rules/loanwords.yaml`

### loan.eu
- direction: narkamauka → taraskievica
- does: word-initial еў → эў: Еўропа → Эўропа
- source: UNVERIFIED

### loan.l_palatalization
- direction: narkamauka → taraskievica
- does: soft л in a curated list of Western stems: план → плян, біялогія → біялёгія
- source: UNVERIFIED (the stem list itself is also unverified)

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
- source: UNVERIFIED (inverse of morph.particle)

### morph.particle.byaz
- direction: taraskievica → narkamauka
- does: standalone бяз / бязь → без
- source: UNVERIFIED (inverse of morph.particle)

### morph.preposition.z
- direction: taraskievica → narkamauka
- does: зь / празь / церазь → з / праз / цераз
- source: UNVERIFIED (inverse of morph.particle)

## Pipeline-level rules — `src/belnorm/rules/morphology.py`

These need the next word, so they run in the pipeline rather than the YAML engine.

### morph.particle
- direction: narkamauka → taraskievica
- does: не → ня and без → бяз when the next word is stressed on its first syllable; з, бяз,
  праз, цераз then take ь before a soft onset (з ім → зь ім, без ліку → бязь ліку). Unstressed
  без stays без. A next word GrammarDB does not know, or knows as a homograph with stress in
  different places (ма+е / мае+), leaves the particle unchanged.
- source: GrammarDB-stress (RELEASE-202601, `data/stress/`) for *where the stress falls*.
  The phonological conditioning itself — jakanne of не/без before a stressed first syllable,
  and the ь on з/бяз/праз/цераз before a soft onset — is still UNVERIFIED and wants a
  citation from the Збор правілаў (2005).
- open questions the stress data exposed (gold disagrees, codification needed):
  - не было (было+): stress data says не; gold has ня. Stress may retract onto the particle.
  - не пойдзем (по+йдзем): stress data says ня; the v0 gold row has не.
  - без мяне (мяне+): stress data says без; the v0 gold row has бязь.
  - без слёз: converter gives бяз, gold бязь сьлёз — the soft-onset test looks at the
    Narkamaŭka form слёз, where the assimilative softness of с is not written.

## Known gaps (not implemented, need the codification)

- **і → й after a vowel** (мама й тата): no rule, no gold coverage.
- **Genitive plural -аў** (хвілін → хвілінаў): no rule, no gold coverage; needs a noun list.

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
  the lexicon; Кыргызстан and its forms pass through unchanged.

## Lexicon

- **Швейцарыя → Швайцарыя** and **швейцарскі → швайцарскі**: all forms listed in
  `data/lexicon/proper_nouns.tsv`, taken from GrammarDB RELEASE-202601 (paradigms Швейцарыя
  NPIINF2 and швейцарскі ARP) with only the stem changed. Source for the Taraškievica stem:
  UNVERIFIED like the rest of the lexicon.


`data/lexicon/*.tsv` entries (loanwords, proper nouns, exceptions) are lexical facts, not
rules, but they are equally unverified: they were written from memory, not from a dictionary.
Toponym and country substitutions (Мінск → Менск, Германія → Нямеччына) in particular need a
source.
