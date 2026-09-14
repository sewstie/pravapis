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
- does: не → ня and без → бяз before a word stressed on its first syllable (stress guessed by
  a heuristic and a word list); з, без/бяз, праз, цераз take ь before a soft onset
  (з ім → зь ім, без мяне → бязь мяне)
- source: UNVERIFIED (both the conditions and the бязь-before-any-soft-onset choice are
  open questions; see gold rows marked `uncertain`)

## Known gaps (not implemented, need the codification)

- **і → й after a vowel** (мама й тата): no rule, no gold coverage.
- **Genitive plural -аў** (хвілін → хвілінаў): no rule, no gold coverage; needs a noun list.

## Lexicon

`data/lexicon/*.tsv` entries (loanwords, proper nouns, exceptions) are lexical facts, not
rules, but they are equally unverified: they were written from memory, not from a dictionary.
Toponym and country substitutions (Мінск → Менск, Германія → Нямеччына) in particular need a
source.
