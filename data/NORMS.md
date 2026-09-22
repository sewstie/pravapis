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

## Policy: optional forms (project-wide)

**Where the codification permits more than one form, the converter does not change the input.**
Converting a form the norm already allows is a false positive, not an improvement.

- Rules that rewrite an already-valid form are marked `optional: true` in `data/rules/*.yaml`
  (or run only in aggressive mode, for pipeline-level rules) and are **off by default**.
- They are applied only on request: `pravapis convert --aggressive`, `pravapis explain
  --aggressive`, `"aggressive": true` in the HTTP API, `Converter(..., aggressive=True)` or
  `converter.convert(text, direction, aggressive=True)` in the library.
- Lexicon entries follow the same policy: no entry may replace a form the codification lists
  as valid.
- Not the same as *unresolved* (sources disagree, see below): unresolved words are left
  unchanged in every mode; optional rewrites are known-valid and available on request.

Optional under this policy: `loan.f_substitution` (§81 Заўвага Б), `morph.conj_i_j` (§13).
The ґ letter is optional in the same sense, and the project declines it outright — see
"Project decision: no ґ".

---

Format per rule: `id`, `direction`, what it does, `source`. When a citation is added, replace
`UNVERIFIED` with e.g. `Збор правілаў 2005, §18, с. 42`. If the text contradicts the rule, note
it here and fix the rule in the same change.

---

## Resolved: the adjective suffix -ейск-

**эўрапейскі, never эўрапэйскі.** §52 gives еў → эў and §11б gives е → э after a hard
consonant, and applying both would produce эўрапэйскі — which is what be-tarask writes.
It is wrong: the suffix **-ейск- keeps its е** whatever the root does, as in армейскі and
асамблейскі. `e_to_eh` exempts it explicitly, so the rule stays right when the stem
inventory grows to cover such words.

## Resolved: the three leads from the baltoslav comparison

Ruled on by the project owner; two of the three were the other implementation's error.

### універсітэта → унівэрсытэту — correct, §71
Taraškievica gives masculine loanwords naming institutions, abstractions and structural
concepts the genitive singular **-у/-ю** where Narkamaŭka writes -а. The vowel shift of the
stem is ordinary §11б + §67 (універсітэт- → унівэрсытэт-); the ending is §71.

Held as a **whitelist** in `data/lexicon/exceptions.tsv`, on the same reasoning as the
genitive plural in -аў: nothing in the spelling says whether a masculine noun is an
abstraction or a countable thing, and -а is also the ending of concrete nouns that keep it.

It is **forward-only**, and the asymmetry is the point. Narkamaŭka -а is unambiguously the
genitive, so N → T is safe. Taraškievica -у is genitive *or* dative and Narkamaŭka spells
the dative -у as well, so T → N cannot tell them apart from the form alone. Mapping it back
would turn *дзякуючы інстытуту* into *дзякуючы інстытута*. The ending is left alone in that
direction. `lex.case_context` could guess from a preceding dative preposition, but it would
still corrupt a bare dative after a verb (*дапамагаць унівэрсытэту*), so it is not used
here. The measured cost is one word of T → N gold — under-converting an ambiguous form
beats corrupting an unambiguous one.

### цюркскага — already correct; no change
§46 limits the т/д/ц/ч → цк/дзк merger to dental and sibilant stem endings. A velar к or г
before -ск- does not mutate to цк; it either drops (цюрскі) or the root is kept whole
(цюркскі). *цюрцкага* would imply a stem in т or ч, as in турэцкі, which a direct loan does
not have. The converter already leaves цюркскі alone — baltoslav is the side that changes it.

### лідар → лідэр — already correct; no change
The foreign suffix -ер after a hard consonant keeps its э in Taraškievica — лідэр,
кампутэр, прынтэр — rather than Narkamaŭka's -ар. The lexicon entry stands.

## Resolved: §47–§49, the prosthetic в and г — no rules, by measurement

Both orthographies write the prosthetic consonant identically, so **this section describes
the language, not a difference between the two spellings**, and a converter has nothing to
do. Checked form by form and locked in by test:

- §47 в before a stressed о — вока, вожык, восем, вобраз — same on both sides.
- §47 Заўвага А, the alternating path (во́зера → азё́ры, в drops with the stress) and the
  fixed path (во́ка → вачні́цы, в stays) — both already written that way in Narkamaŭka too.
- §47's negatives — оптыка, опцыён, опера, ордэн, ого, ой — untouched in both directions.
- §48–§49, в before у (вуха, вучань, вуліца) and the г of гэты/гэны — likewise.
- §47 Заўвага Б's doublets — араць/гараць, арэх/гарэх, востры/гостры — are **permitted
  variants**, so the optional-forms policy above forbids rewriting either way. The converter
  passes all of them through.

The value here is the regression test, not a rule:
`test_47_49_prosthetic_consonants_are_not_an_orthography_difference`. The risk this guards
against is a future rule reaching one of these forms by accident.

## Resolved: §68 — word-final -сія / -зія keeps its і soft

§67 hardens і to ы after с and з inside a loan root — сыстэма, сытуацыя, клясычны, фізык,
візыт. §68 stops that at the **word-final nominal suffix -сія / -зія**, where the consonant
is soft and і is written: пэнсія, агрэсія, рэцэнзія, прэтэнзія, дывізія, гімназія, Азія.

Two things were wrong and both are fixed.

**The suffix was hardening.** Three stems — `дывізі`, `гімназі`, `азіяц` — turned the
suffix's і into ы. All three were provenance `reviewed`, a generalisation from §67 rather
than anything §67 cites, and `-агрэсі` did the same to агрэсія and прагрэсія. The held-out
corpus settles it: `data/eval/tarask/corpus.tsv` is 7,378 words of genuine
be-tarask.wikipedia.org text and writes **дывізія, дывізіяў, гімназія, Азіі, Азіяцкай,
неагрэсіі — 13 soft forms and not one ы**. The four stems are gone. §67's own cited
examples (`класі`, `фізі`) stay: клясычны and фізык are not -сія nouns.

**The paradigm fell through.** пенсія and пенсіянер were single rows in `loanwords.tsv`,
so only the nominative converted — пенсіі, пенсію, пенсіямі, пенсіянеры were left
untouched. They are stems now (`пенс`, `пенсіянер`, `інданез`, alternation `e`), which
hardens the stem's е to э across every case while leaving the suffix's і alone.

The same fall-through still affects the `-ер`/`-ар` suffix: `лідар → лідэр` converts but
`лідары → лідары` does not, and `інжынер`, `мільянер` are untouched entirely. Unruled.

## Resolved: the independent gold had been run through the converter

`data/eval/tarask/gold_t2n.tsv` promises in its own header that the Taraškievica column is
genuine be-tarask.wikipedia.org text, "not derived from any Narkamaŭka source". The entire
independent T → N figure rests on that. 28 of its 150 rows had drifted from `corpus.tsv`
by 50 character edits, all of them changes this converter makes: 11 × `і → й` (the
**optional** §13 rule), 10 × `і → ы`, inserted and deleted `ь`, one `ґ → г` — the project's
own ґ policy — and 7 vocabulary swaps. The gold's *input* had been converted.

All 28 were restored from the corpus; the hand-written Narkamaŭka column was untouched.
The reported figure went 94.7% → 99.6%, and the rise is an artefact: the repair removed 26
change-opportunities that should never have existed (264 → 238), the vocabulary swaps among
them. `test_independent_gold_taraskievica_column_is_the_untouched_corpus` now asserts every
Taraškievica column appears verbatim in `corpus.tsv`.

The one remaining error on that set is `еўрапйскім` — a typo in the gold's Narkamaŭka
column, not a converter error. Left alone: the Narkamaŭka column is hand-written and is
not mine to edit. The set is saturated and no longer discriminates; it needs to grow.

## Resolved: paradigm-wide stems replace single-form lexicon rows

`scripts/check_paradigms.py` converts every form of every GrammarDB paradigm and asks what
the forms' shared stem became. All must answer the same: пенсія → пэнсі- while пенсіі →
пенсі- is a contradiction visible without any gold. With `--lexicon-only` it found **365**
paradigms where a lexicon row covered the citation form and nothing else — расійскі
converted, расійскага did not. Stems now carry them, and the count is **261**.

Adjectives went 107 → 24 on six stems: `-расійск`→расейск, `-лагічн` (l), `-метад` (e),
`-медыцын` (e), `-іспанск`→гішпанск, `філа` (l). Two compounds need their own entry
because **only the longest single stem matches a word** — філалагічны and метадалагічны
each carry two changes.

Also added: the §68 abstract matrices (`дыферэнц`, `канферэнц`), the agentive -ер/-ор
group (лідэр, мэнэджэр, прынтэр, рэжысэр, трыгэр), and toponyms (`лондан`, `сідней`,
`сілез`, `сіцылі`, `сімон`, `тыбет`, `гамбургск`→гамбурск, `эдынбургск`→эдынбурск).

Three details that cost a test each:

- **`сілез`, not `сілезі`.** The stem must end before the suffix's own і, or і → ы reaches
  it and gives Сылезыя. §68 keeps that і soft.
- **`сімон` is `i:n2t`.** Сымон is also a Belarusian given name Narkamaŭka spells that way
  — Сымон Будны, «Касьцёл Сьвятых Сымона і Алены» — so the reverse must never fire. It did,
  and it was the project's first false positive in either direction.
- **`крызіс` → `крызыс` after all.** §67 hardens after з; the earlier reading of §68 was
  wrong and has been reversed by the project owner. The old lexicon row was still a
  defect — it converted крызіс and left крызісу and крызісны — so it is a stem now, and
  `gold.tsv` is back to `Крызыс мінуў.`, which the hand review had right.

### §71 checked against GrammarDB rather than assumed
Of thirteen nouns proposed for the genitive -у whitelist, GrammarDB shows **бюджэт, візіт,
транзіт, дэпазіт, крэдыт, дэфіцыт, дызайн and аналіз already take -у in Narkamaŭka** —
there is nothing to convert, and the -а forms proposed for them are not Narkamaŭka words.
Five were added: аргумэнту, інструмэнту, сэгмэнту, сындыкату, сыноніму. **паразіт was
refused**: §71 covers abstractions and institutions, and a parasite is a concrete animate
noun whose genitive -а is obligatory.

### Two gold corrections this produced
The new reverse mappings exposed six rows of `gold_t2n.tsv` whose *Narkamaŭka* column still
held Taraškievica spellings — геалягічным, рэжысэра/рэжысэрам, філязофіі, расейскай,
археалягічны. `check_gold_t2n.py` flagged them the moment the converter could see them;
the Narkamaŭka column now reads геалагічным, рэжысёра, філазофіі, расійскай, археалагічны.
Row 39's Narkamaŭka side still carries мэдычным, Цюбінгэнскага and ўнівэрсытэту, which no
rule reaches yet, so that column is not fully converted even now.

`gold.tsv` had `Крызіс мінуў. / Крызыс мінуў.` marked `hand_written`. §68 says крызіс does
not change, so the Taraškievica column was corrected — a newer ruling overriding an older
hand review, recorded here because that is not something to do silently.

## Refused: a blanket genitive -у for "masculine abstract" nouns

§71 moves the genitive singular of masculine **abstract** loanwords to -у. There is no
mechanical test for "abstract", and the evidence is direct rather than theoretical:

- GrammarDB marks gender and animacy but not abstractness. Masculine + inanimate +
  genitive -а gives **25,475** lemmas, `горад` and `стол` among them.
- Narrowing to lemmas our loan stem inventory matches gives **281** — still `бераг`,
  `балкон`, `бланк`, `блок`, `атлас`: concrete objects whose -а is correct. Applying -у
  to them yields *берагу*, *балкону*, *бланку*.
- Narrowing again by abstract derivational suffix (-ізм, -мент, -цыя, -ура, -аж, -ітэт …)
  leaves **7**, two of which are already whitelisted, and the rest are -ізм nouns whose
  genitive is contested in Narkamaŭka itself.

So the whitelist is close to complete for the abstractions this inventory covers, and a
blanket rule buys ~5 words at the cost of corrupting ordinary text — the same trade the
genitive plural in -аў was already refused for. Whitelisted: унівэрсытэту, інстытуту,
парлямэнту, аргумэнту, інструмэнту, сэгмэнту, сындыкату, сыноніму. Extending it is one
line per word.

`крытэрый → крытэр` is in `exceptions.tsv` form by form rather than as a stem: it is a
lemma change, and Narkamaŭka's -ый noun has a -ыя/-ыю/-ыем declension where Taraškievica's
is a plain hard-stem masculine. `аналіз` stays masculine by default — the feminine аналіза
is the historical variant — and its genitive is already -у in Narkamaŭka, so nothing moves.

### §53 кампутар
кампутар is the preferred form, the direct borrowing without the iotated vowel. The
recognised variant камп’ютэр is carried as **t2n** rows: it is a Taraškievica spelling, not
a Narkamaŭka one, so it is read on the way back and never produced on the way out. It
cannot be a second stem — `reverse_collisions` forbids two stems deriving one reverse key,
and correctly so, since кампутар must come back as one spelling.

## Assimilative softness — `data/rules/palatalization.yaml`

### palat.apostrophe
- direction: narkamauka → taraskievica
- does: з/с + apostrophe + iotated vowel is written with ь: з’ява → зьява
- source: Збор 2005, §29 ("у т. л. перад [й]: зьезд, … зьява") and §43 (the separating ь
  after soft з, с before е, ё, ю, я)

### palat.geminate.dz
- direction: narkamauka → taraskievica
- does: soft long дз: суддзя → судзьдзя, стагоддзе → стагодзьдзе; not at a prefix boundary:
  аддзел, аддзячыць, паддзець stay unchanged
- source: Збор 2005, §40 (судзьдзя, стагодзьдзе); §32 and §41 Заўвага А ("Прыстаўкі на -д перад
  наступным коранем, які пачынаецца на дз-, пішуцца нязьменна: аддзел, аддзячыць, паддзець,
  Наддзьвіньне"). The prefix boundary is detected from a word-initial list (ад-, пад-, над-,
  перад-, optionally after па-, за-, на-, вы-, пера-, раз-, ус-, у-, з-).

### palat.geminate
- direction: narkamauka → taraskievica
- does: soft long н, л, з, с, ц, дз are written with ь: насенне → насеньне, жыццё → жыцьцё, вяселле → вясельле
- source: Збор 2005, §40 (жалезьзе, калосьсе, асяродзьдзе, жыцьцё, вясельле, гуканьне)

### palat.assim
- direction: narkamauka → taraskievica
- does: з, с take ь before a soft в, м, п, б, л, н, с, з, ц, дз: снег → сьнег, свет → сьвет
- source: Збор 2005, §29 ("Памякчэньне с, з перад наступнымі мяккімі зычнымі (апроч г (ґ), к, х)
  перадаецца на пісьме ў межах слова": сьвет, сьнег, радасьць, зьвер, зьдзек)

### palat.assim.ts_dz
- direction: narkamauka → taraskievica
- does: ц, дз take ь only before a soft в: дзверы → дзьверы, цвёрды → цьвёрды; before any other
  consonant they stay hard: мацнець, пэндзлік, Цнянка
- source: Збор 2005, §30 ("Зычныя ц, дз перад наступным мяккім в у межах кораня – таксама мяккія:
  цьвёрды, цьвік, … дзьве, дзьверы") and §30 Заўвага А ("Перад зычнымі (апрача в) … зычныя т, ц,
  д, дз застаюцца цьвёрдыя: … мацнець, … пэндзлік, … Цнянка"). Before this was split out, the
  converter wrote мацьнець, пэндзьлік, Цьнянка.

### palat.ungeminate.dz
- direction: taraskievica → narkamauka
- does: reverse of palat.geminate.dz: судзьдзя → суддзя
- source: inverse of palat.geminate.dz — Збор 2005, §40

### palat.ungeminate
- direction: taraskievica → narkamauka
- does: reverse of palat.geminate: насеньне → насенне
- source: inverse of palat.geminate — Збор 2005, §40

### palat.unassim
- direction: taraskievica → narkamauka
- does: reverse of palat.assim for з, с; keeps a lexical ь (пісьмо)
- source: inverse of palat.assim — Збор 2005, §29 (§29 Заўвага Б: etymological ь in пісьмо,
  просьба, дзьме is not assimilative and stays)

### palat.unassim.ts_dz
- direction: taraskievica → narkamauka
- does: reverse of palat.assim.ts_dz: дзьверы → дзверы; дзьме keeps its etymological ь
- source: inverse of palat.assim.ts_dz — Збор 2005, §30

### palat.unapostrophe
- direction: taraskievica → narkamauka
- does: reverse of palat.apostrophe: зьява → з’ява
- source: inverse of palat.apostrophe — Збор 2005, §29, §43

## Loanwords — `data/rules/loanwords.yaml`

### loan.eu
- direction: narkamauka → taraskievica
- does: word-initial еў → эў in loanwords and classical/foreign names (Еўропа → Эўропа,
  Еўклід → Эўклід, Еўфрат → Эўфрат); not in traditional Christian given names (Еўдакія,
  Еўфрасіння stay)
- source: Збор 2005, §52 (Greek ευ / Latin eu → эў: эўгеніка, эўфарыя, Эўклід, Эўропа, Эўрыпід,
  Эўфрат).
- scope boundary, from the book: §52 excludes "даўно асвоеныя імёны … варыянты адаптацыі", and §72
  Заўвага А says traditional Christian names are fixed in two forms, with initial [й] and without
  (Еўдакія – Аўдоцьця; Е(ў)фрасіньня – Эўфрасіньня й Апраска); footnote 68: the Е-/Я- forms come
  through Church Slavonic mediation. The Е- form is valid, so it stays (optional-forms policy).
  The boundary is a **lexical class** (traditional Christian given names vs loanwords and classical
  names), not a spelling pattern: Эўклід and Еўдакія are both capitalised Greek names.
- implementation — **workaround**: the rule excludes the stems of the class members the book
  names (`^еў(?!дакі|фрасін)`). Other traditional names starting with Еў- are not covered until a
  cited source puts them in the class.

### loan.l_palatalization
- direction: narkamauka → taraskievica
- does: soft л in a curated list of Western stems: план → плян, біялогія → біялёгія
- source: principle — Збор 2005, §55.1 (L soft in Western European loans other than
  anglicisms: плян, кляса, лямпа, блёк, глёбус, лёзунг, ляўрэат, плятформа, салён, лёгіка) with
  the hard exceptions of §56.2 (лава, ладан, ланцуг, блазан, салдат, матацыкл …).
- stem list, checked word by word against the rules text (spelling dictionaries are absent):
  - in the book: плян, кляс(а), лямп(а), блёк, глёб(ус), лябарат (§55.1 лябараторыя), блянк,
    лёзунг, ляўрэат, дыплём, плятформ(а), салён, лёгік(а), -лёгія; клюб (§55.2); лягер (§62
    example ляг ер); парлямэнт (§11 example парлям энт)
  - not in the book: лякальны, ляндшафт, балькон, атляс, рэкляма, кілямэтар, кіляграм, калёнія,
    калёніяльны. Kept (they follow the §55.1 principle for Western loans) but unverified as words.

### loan.i_to_y
- direction: narkamauka → taraskievica
- does: ы after з/с in a curated list of Greco-Latin stems: сістэма → сыстэма, класічны → класычны
- source: Збор 2005, §67 (сыстэма, сытуацыя, сынонім, сыгнал, клясычны, фізык, візыт, дэпазыт);
  §66 marks where і stays (расізм, марксізм)
- **§67 Заўвага А** overrides both, in both directions, through `data/lexicon/stems/stems.tsv`:
  - *fixed hard* — loans settled here long enough that ы is written whatever the usual
    conditions say: кармазын, кузына, магазын, разынкі, экзыль. Carried as `loan` stems with
    the `i` alternation, so the inflected forms follow (магазіна → магазына).
  - *fixed soft* — кракадзіл, лаціна, and the homonym pairs і is what keeps apart:
    Дзіна ≠ дына, сіці ≠ сыты ≠ сыці, цік ≠ тык. Carried as `native` stems. Nothing converts
    them today; the entries are there so that no stem added later can, since і → ы would
    collapse each of those pairs into one word.
  - `native` here means only "the loanword alternations do not apply". кракадзіл is a
    borrowing; its і is simply permanent.
- **§67 Заўвага Б** needs no entries: the ы of a Slavic root is already written in Narkamaŭka
  (гусіт stays, хвасцізм → хвасьцізм), so the alternation never has cause to fire.

### loan.stem_target
- direction: narkamauka → taraskievica
- does: replaces a matched stem with the explicit target in the 6th column of
  `data/lexicon/stems/stems.tsv`, for stems no regular alternation can derive.
  Only entry so far: каланіял → калёніял.
- source: Збор 2005, §55.1 (soft л in Western stems) for the alternation itself. The stem
  needs an explicit target because Narkamaŭka akanne wrote the etymological *о* of колон- as
  *а*: no rule conditioned on the Narkamaŭka spelling can recover калёніял from каланіял.

### loan.e_to_eh
- direction: narkamauka → taraskievica
- does: е → э inside a stem classed `loan`, after any consonant except л and the velars
  г, ґ, к, х: сезон → сэзон, версія → вэрсія, аперацыя → апэрацыя, дакумент → дакумэнт
- source: Збор 2005, §11б ("У пазычаньнях і вытворных ад іх словах правапіс э звычайна не
  залежыць ад націску. Літара э пішацца: … б) пасьля зычных, акрамя л і заднеязычных
  (г (ґ), к, х): … бізнэс, губэрня, дэкан, мэбля, мэтро, рэкорд, сэзон, сэмэстар, сэсія;
  Армэнія, Бэрлін, Вэрсаль, Жэнэва"), with the finals -эль, -эн, -энт, -эр, -эт listed in
  the same section.
- exceptions: Збор 2005, §12 Заўвага Б ("У наступных асвоеных пазычаньнях канцавыя фарманты
  -el, -er пішуцца празь е: блюзьнер, жаўнер, касінер, каўнер, кушнер, манер, манера,
  шынель"), listed as rule exceptions.
- note on §12: unstressed [э] in assimilated borrowings is written а (адрас, літаратура,
  майстар, момант, кампутар). Narkamaŭka already writes а in those, so they are no-ops here;
  the ones that are not are held as `native` stems.
- scope: the etymology comes from `data/lexicon/stems/stems.tsv`, never from the spelling —
  see "Etymology is data" below.

### loan.f_substitution
- direction: narkamauka → taraskievica
- does: **optional** (aggressive mode only): Фёдар → Хведар, Фядос → Хвядос, endings kept
- source: Збор 2005, §81 Заўвага Б ("Шэраг хрысьціянскіх імёнаў мае некалькі формаў: … Тодар,
  Фёдар, Хведар, Ходар; … Фядос, Хвядос, Ходас"). Фёдар is a valid form, so the default leaves
  it. Філіп → Піліп and Фама → Хама were removed: neither is in the book.


### loan.g_remove
- direction: taraskievica → narkamauka
- does: ґ → г, always
- source: Збор 2005, альфабэт, зноска * — "пры разьмеркаваньні словаў у альфабэтным
  парадку літара ґ роўная г", and the letter itself is факультатыўна. Since г is always
  acceptable and Narkamaŭka's alphabet has no ґ, the mapping loses nothing. It is also the
  only ґ rule left: see "Project decision: no ґ".


### loan.stem_reverse
- direction: taraskievica → narkamauka
- does: replaces a matched Taraškievica loan stem with its Narkamaŭka form — плян → план,
  сыстэма → сістэма, сэзон → сезон, калёніяльны → каланіяльны — in one substitution
- source: inverse of loan.l_palatalization, loan.i_to_y, loan.e_to_eh and loan.stem_target
  on the same stems (Збор 2005 §55.1, §56.2, §67, §11б)
- why a substitution and not an inverse transducer: the Taraškievica string does not say
  which ь was added by the rule and which was already in the Narkamaŭka stem — балькон →
  балкон must drop one, лякальна → лакальна must keep one. The stem entry knows both
  spellings, so the reverse index is derived from the forward one and carries the
  Narkamaŭka stem as its target. See "Etymology is data".
- stems whose Taraškievica form is ambiguous get no reverse entry at all (marked `l:n2t`
  in stems.tsv): салон → салён is safe, салёны → салоны is not, because Taraškievica
  салён- is also the native adjective "salty".

### loan.eu_reverse
- direction: taraskievica → narkamauka
- does: word-initial эўр → еўр, except эўрыстыка
- source: inverse of loan.eu — Збор 2005, §52

## Morphology — `data/rules/morphology.yaml`

### morph.final_tr
- direction: narkamauka → taraskievica
- does: epenthetic а in word-final -тр/-др: тэатр → тэатар, цэнтр → цэнтар; not in non-traditional
  proper names (Сартр, Нотр-Дам)
- source: Збор 2005, §26 (аркестар, літар, мэтар, тэатар, цэнтар, Аляксандар) and §26 Заўвага А
  ("У нетрадыцыйных уласных назовах tr, dr на пісьме перадаюцца без устаўнога галоснага: Нотр-Дам,
  Сартр"). Which proper names are non-traditional is not decidable from spelling: they are listed
  as rule exceptions (сартр, нотр) and the list is open.

### morph.particle.nya
- direction: taraskievica → narkamauka
- does: standalone ня → не
- source: inverse of morph.particle — Збор 2005, §3

### morph.particle.byaz
- direction: taraskievica → narkamauka
- does: standalone бяз / бязь → без
- source: inverse of morph.particle — Збор 2005, §3, §29

### morph.conj_j_i
- direction: taraskievica → narkamauka
- does: a standalone й → і (сала й цыбуля → сала і цыбуля); й inside a word is untouched
- source: inverse of morph.conj_i_j — Збор 2005, §13. The forward direction is optional
  ("**можа** пераходзіць у й"), so і is left alone by default; the reverse is not
  optional, because Narkamaŭka has no syllabic й standing as a word.

### loan.ment_suffix
- direction: both
- does: N → T writes the suffix -мент as **-мэнт**: дакумент → дакумэнт, парламент →
  парлямэнт, дакументацыя → дакумэнтацыя, манументальны → манумэнтальны.
  T → N writes it back: мэнт → мент, unconditionally.
- source: project owner's instruction, against Збор 2005 §11б (э after a hard consonant
  in borrowings). The suffix takes э when the base noun carries the stress on it —
  дакумэ́нт, аргумэ́нт, парлямэ́нт, інструмэ́нт, мэдыкамэ́нт, сэгмэ́нт — and **the э is
  inherited by everything derived from that base, even after the stress moves**:
  манумэ́нт → манумэнта́льны, дакумэ́нт → дакумэнта́цыя, інструмэ́нт → інструмэнта́льны.
  The stem is preserved, not the stress of the word in hand.
- data: the 116 GrammarDB noun lemmas ending in -мент (`data/morphology/`, CC BY-SA 4.0).
  A word matches if one of them is a suffix of its text up to the first мент, so
  абцэментаваны → абцэмент → цэмент. The bare colloquial noun *мент* is excluded, or any
  word starting мент- would match and drag in ментальны, which is not derived from a
  -мент noun.
- what was tried first and was wrong: per-form stress, taken from GrammarDB's marks. It
  got дакументацыя and манументальны wrong — precisely the derived words where the stress
  has moved but the stem has not. GrammarDB also marks *парламент* as stressed on -ла́-,
  while Taraškievica writes парлямэ́нт, so its stress is not the discriminator here.
- T → N needs no table: GrammarDB holds **no** Narkamaŭka form containing мэнт.

### morph.dsk_to_dzk
- direction: narkamauka → taraskievica
- does: д + ск → дзк before the adjective suffix: мадрыдскі → мадрыдзкі, гарадскі →
  гарадзкі, людскі → людзкі
- source: Збор 2005, §46. Taraškievica writes the phonetic result of the merger where
  Narkamaŭka keeps the root consonant intact (the morphological principle).
- scope: it applies by the **stem's final consonant**, not by whether the word is
  foreign. Stems in н, к, л, с keep their cluster: бэрлінскі, лёнданскі, нью-ёркскі.
  (т + ск → цк and ч + ск → цк are not implemented: Narkamaŭka writes цк there too —
  дэпутацкі, ткацкі — so there is nothing to convert.)

### morph.dzk_to_dsk
- direction: taraskievica → narkamauka
- does: reverse of morph.dsk_to_dzk — мадрыдзкі → мадрыдскі
- source: inverse of morph.dsk_to_dzk — Збор 2005, §46

### morph.ejsk_normalise
- direction: taraskievica → narkamauka
- does: -эйск- → -ейск-, so эўрапэйскі → еўрапейскі
- source: Збор 2005 §11б, заўвага — the adjective suffix -ейск- keeps its е after a hard
  consonant. эўрапэйскі is therefore an error, not a variant: be-tarask produces it by
  applying §11б where the заўвага exempts the suffix.
- the forward direction can never produce -эйск- (`e_to_eh` exempts the suffix), so this
  only normalises input that arrives wrong.

### morph.preposition.z
- direction: taraskievica → narkamauka
- does: зь / безь / празь / церазь → з / без / праз / цераз
- source: inverse of morph.particle — Збор 2005, §29

## Pipeline-level rules — `src/pravapis/rules/morphology.py`

These need the neighbouring word, so they run in the pipeline rather than the YAML engine.

### lex.case_context
- direction: narkamauka → taraskievica
- does: lexical substitutions whose Taraškievica target depends on case, where one Narkamaŭka form
  covers several cases (`data/lexicon/case/*.tsv`). The preposition before the word decides:
  у, ў, ва, на, аб, пры, па, к, ка, дзякуючы, насустрач, насуперак → dative/locative target;
  anything else → genitive. Only entry so far: Германіі → Нямеччыны (сталіца Нямеччыны,
  да Нямеччыны) / Нямеччыне (у Нямеччыне, па Нямеччыне).
- source: the forms — GrammarDB RELEASE-202601 paradigm Германія (GS = DS = LS Германіі); the
  lemma — Збор 2005, §37 (нямецкі – Нямеччына); the declension of Нямеччына is the regular
  feminine -а one. The preposition → case mapping is ordinary Belarusian grammar, not a rule of the
  codification.
- known limitation: a dative governed by a verb, with no preposition, gets the genitive
  (дапамагаць Германіі → дапамагаць Нямеччыны; should be Нямеччыне). baltoslav.eu makes the same
  choice there, and also for па.

### morph.conj_i_j
- direction: narkamauka → taraskievica
- does: **optional** (aggressive mode only): the conjunction/particle і → й after a word ending
  in a vowel: сала і цыбулю → сала й цыбулю. After punctuation it stays і; a word-initial
  і- is never touched.
- **hyphens and quotation marks do not count as punctuation here.** §13's Заўвага takes them
  out of the way — "злучок і двукоссе не з'яўляюцца знакамі прыпынку і на правапіс й не
  ўплываюць" — so the vowel still reaches the conjunction across them:
  адна- і шматмоўныя → адна- й шматмоўныя, «Паўлінка» і «Тутэйшыя» → «Паўлінка» й «Тутэйшыя».
  A dash (працяжнік) is a punctuation mark and does block it. The two are the same character
  on an ASCII keyboard, so `bridges_words` in `tokenize.py` separates them by position: a
  hyphen written against a word is a злучок, a hyphen with space on both sides is a dash.
- source: Збор 2005, §13 ("Пасьля словаў, якія канчаюцца на галосны, злучнік і часьцінка і
  складовае **можа** пераходзіць у й нескладовае … Пачатковае і- … пішацца нязьменна"),
  and its Заўвага for the hyphen and quotation-mark carve-out.

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

Two further cases of this bug class were found and fixed in phase D0:

| Place | Read | Verdict |
|---|---|---|
| `palat.assim` before the loanword vowel rules | the `е` that `loan.e_to_eh` was about to turn into `э` | **bug, fixed**: спектаклі → сьпэктаклі, because с·п·е looked like a softness context while the е was still an е. Every etymology-gated rule now runs *above* palatalization (priority 185–200): softness is a consequence of the vowel, so the vowel is settled first. |
| `palatalize_l` at the stem boundary | the end of the *stem*, as though it were the end of the word | **bug, fixed**: алкагольны → алькаголььны, because a stem-final л took a ь that the word already had. The transducer now receives the character following the stem; the stem boundary is an artefact of the inventory, not a fact about the word. |

A third consequence: the stem span is resolved once, from the word as it arrived, so a
higher-priority rule that changes the word's *length* would leave it pointing at the wrong
letters. `StemMatch.spans()` refuses that case. A change at the same length is fine and
expected — класі → клясі → клясы is one alternation feeding the next.

Measured on the 100,000 most frequent Wikipedia words plus the gold set, the round-trip corpus
and every lexicon entry: after the fix, no Belarusian N → T output word contains a softness
context the rules would still mark, and the only T → N outputs keeping an assimilative-looking ь
are the пісьменнік family above.

## Etymology is data, not a pattern

The loanword alternations (soft л §55.1/§56.2, і → ы §67, е → э §11б) are each stated by the
codification as a plain phonological condition. What the codification assumes, and the
spelling never shows, is that the word is a borrowing: native *лапа* and borrowed *лямпа* are
indistinguishable to any rule that reads only letters. That is the fact the classifier tried
and failed to learn (see README, "Why the classifier was removed").

So the rules are general transducers and the etymology is a data file:
`data/lexicon/stems/stems.tsv`, one row per stem, carrying its class (`loan` / `native`),
the alternations it licenses, a citation, and a provenance tier.

Consequences worth knowing:

- **Longest match wins.** A false friend is a native stem one character longer than the loan
  stem it must beat: `класц` (класці) over `клас`, `падлог` (падлогі) over `-логі`. No rule
  carries a lookahead any more.
- **Rewrites are bounded by the matched stem.** This is what keeps §66 honest at no cost: in
  *марксізм* the stem is *маркс*, so the *-ізм* suffix is outside the span and і → ы never
  reaches it.
- **The reverse index is derived, not written.** Taraškievica keys come from applying the
  forward alternations to each Narkamaŭka stem, so the two directions cannot disagree about
  what a stem licenses. An alternation written `l:n2t` is forward-only, for stems whose
  Taraškievica form is ambiguous (салён- is both the loan *salon* and the native *salty*).
- **Provenance gates application.** `cited` / `reviewed` / `derived` are applied; `uncertain`
  rows are parsed and counted but never fire. The ґ stems are all `uncertain`, which is why
  `loan.g_distinction` currently changes nothing while remaining ready for a citation.

## Measured: native guards, and why there is no runtime lemma layer

Longest-match means a loan stem silently claims every word beginning with it, and a
native guard one character longer takes it back (`класц` beats `клас` on класці). The
worry was that guards would grow with the inventory and become the bottleneck — 51 guards
against 78 loan stems looked like a ratio of 0.65.

Measured instead of assumed: of the 51 guards, **3 change any answer** — `класц`,
`падлог`, `клубок`. The other 48 are inert, written defensively when the character n-gram
classifier was still in the cascade and would attack any native word sharing a letter
pattern. Anchored loan stems do not reach them. The real ratio is closer to 0.03.

So the planned runtime layer — confirm each match is an attested form of the intended
lexeme, from a GrammarDB form table — was **not built**. It would have added a data file,
a lookup and a deployment payload to solve a problem worth three rows, and the evidence
for it did not exist.

What GrammarDB is used for instead is the question that *is* live as the inventory grows:
**which other words would this stem match?** `scripts/check_stem_collisions.py` asks its
224,669 lemmas exactly that, per loan stem, and reports the ones no guard covers. Run
against the current inventory it found false positives the 4,843-word gold vocabulary
never surfaced:

- `клуб` also claims the native root клубень ("tuber"), клубасты, клубануць →
  клюбень, клюбасты, клюбануць. Guarded, with stems short enough to spare клубе and
  клубам (locative and dative of the club).
- `салон` also claims салонец, a soil type → салёнец. Guarded.

Most of what it reports is *not* a collision — план-графік, рэклама and дакументаабарот
are the same lexeme and should convert — which is why the output is a review queue and
not a patch. Re-run it after every batch of mined stems.

## Known gaps (not implemented, need the codification)

*(The genitive plural -аў was logged here for a long time. It is not a gap and not a rule.
**Correction:** this paragraph, `src/pravapis/morphology.py` and the comment in
`data/lexicon/exceptions.tsv` all used to cite "§80" for it. That is wrong — Збор 2005 §80
is the German *ei* rule (Ляйпцыг, Айнштайн), which this file cites correctly elsewhere.
There is no § to cite, because **Збор 2005 is a spelling code (§1–92) and does not legislate
declension at all**; its preface calls it "даведнік цяжкасьцяў беларускага правапісу". The
-аў genitive plural is a morphological feature of Taraškievica, sourced here to the project
owner's instruction and not to the codification. For many words **both** forms
are permissible — хвілін and хвілінаў are equally valid — so a rule that fires on all of
them corrupts ordinary text. Six nouns where -аў is strongly preferred are whitelisted in
`data/lexicon/exceptions.tsv`; everything else is left alone. A table-driven version was
built from every GrammarDB noun first and cost 10 false positives against 3 words gained.)*


## Ў after a vowel (Збор 2005, §18; §20)

`morph.initial_u_w`. Implemented, cited, and the citation is **§18** — an earlier note in
this file guessed §15 and was wrong. §15 is і → ы after a prefix ending in a consonant
(`безыдэйны`, `дэзынфэкцыя`). The guess was never shipped, because a rule that cannot be
cited is not written here; the book settled it.

§18 reads: "Пасьля галосных літараў на месцы у пішацца ў, калі на яго не прыпадае
націск", and its own examples carry the case the recall harness kept reporting:

> ва Ўфе , сталіца Ўкраіны , Марыя Ўласевіч , едзе ў Вільню , ЗША ўзьнялі пытаньне

So a **capitalised** proper noun after a vowel does take Ў, and that is where the two
orthographies part: Narkamaŭka writes *ва Украіне*, Taraškievica *ва Ўкраіне*. Only
capitals are converted — lowercase у after a vowel is already ў in Narkamaŭka too
(*ва ўніверсітэце*), so there is nothing there to change.

§18 names three exceptions, all implemented:

| Exception | §18's examples | How |
|---|---|---|
| stressed у | але у́т, Са у́даўская Арабія, да У́йпэшту, пра У́мбрыю | `StressTable`, plus `STRESSED_INITIAL_U` |
| initial "У." for a name | за У. Сыракомлю, пра У. Караткевіча | single-letter token |
| initial abbreviations | БДЭУ, РУУС, САУ | `word.isupper()` |

`STRESSED_INITIAL_U` exists because the stress table is GrammarDB, a lexicon of
Belarusian: it does not contain *Умбрыя* or *Уйпэшт*, and for a word it does not know
`is_first_syllable_stressed` has to answer "no". The three stems listed are §18's own
examples of the exception.

§18 Заўвага — "Злучок і двукосьсе ня ёсьць знакамі прыпынку й на правапіс ў не
ўплываюць" — is the same note the §13 conjunction rule already relied on, so a hyphen or
a quotation mark is transparent here too: *рыба-ўюн*, *Кука-Ўітсан*.

### The reverse direction: a different code, and a different shape

T → N here answers to **Правілы беларускай арфаграфіі і пунктуацыі (2008)**, the rules
attached to Закон № 420-З — the Narkamaŭka side's own codification, the counterpart of
Збор правілаў 2005 on the Taraškievica side. Cited as `Правілы 2008, §N`; obtained and
hash-pinned by `scripts/fetch_reference.py` (see data/reference/README.md).

> **Правілы 2008, §15 п.4** — «Гук [у] на пачатку ўласных імён і назваў **заўсёды**
> перадаецца вялікай літарай У складовае **без надрадковага значка**: ва Узбекістан
> (для ўзбекаў), на Уральскіх гарах, на Украіне (за ўкраінцаў), за Уладзіміра, каля
> Уладзіслава, да Усяслава.»

**The two directions are not mirror images.** §18 makes У → Ў conditional: after a
vowel, unstressed, capitalised. §15 п.4 makes the reverse unconditional — a proper name
never begins with Ў in Narkamaŭka, whatever precedes it. So the forward rule needs the
previous word and the stress table; the reverse rule needs neither.

#### What this corrected

This project previously kept Ў in Narkamaŭka for names that render English *W* —
*Разумнік Ўіл Гантынг*, *з Ўотэрзам* — on the strength of six hand-written rows in
`data/eval/tarask/gold_t2n.tsv`, and carried a `W_NAMES` exception list so T → N would
leave them alone. Checked against the N-side authority, that was wrong:

* §15 п.4 is categorical, and says the opposite.
* The 2008 rules contain **no word-initial Ў anywhere** — the only capital Ў in the
  whole text is inside ЗНАКАЎ and ПАСЛЯДОЎНАСЦЬ.
* §14 lists *Уэльс* among proper names taking no prosthetic в — a W-name, written У.
* Usage agrees by a wide margin: on be.wikipedia, Уіл 115 hits to Ўіл 1, Уэльс 756 to
  Ўэльс 2, Уотэр 10 to Ўотэр 0.

The six gold rows were corrected to У складовае and the exception was removed. The
inventory itself survives as `data/names/w_names.tsv` — it is real evidence about which
names these are, mined from Wikidata (see `scripts/mine_w_names.py`) — but **nothing in
the converter reads it**, and `pravapis conformance --coverage` lists it as a deliberate
exemption rather than letting it look live. Its natural use is the *forward* direction,
where N → T might write Уіл as Ўіл in positions §18 alone does not reach; that is an
open question, not implemented.

### What it bought

The `other` alternation class, which was **0 of 35** on dev, is now 42.9% (15/35); the
rest of that class is the two wikis disagreeing about у/ў in the other direction, which
is not the converter's to reconcile. Dev N → T recall 74.2% → 75.1%, test 73.5% → 74.5%,
precision unchanged.

## Project decision: no ґ

Збор 2005 зноска 55 licenses the plosive letter in a list of borrowings — "[ґ]анак,
[ґ]арсэт, [ґ]валт, [ґ]зымс, [ґ]онта, [ґ]узік, а[ґ]рэст, цу[ґ]лі, шва[ґ']ер ды інш." — and
the alphabet's own footnote marks it **факультатыўна**, optional, adding that "пры
разьмеркаваньні словаў у альфабэтным парадку літара ґ роўная г".

Because the letter is optional, both spellings are correct and the choice is the project's
to make. **This project writes г everywhere and never produces ґ.** The forward rule
(`loan.g_distinction`) and its stems are removed, not merely disabled; `loan.g_remove`
stays, so ґ arriving in input is normalised to г rather than passed through.

The citation is recorded here rather than in a commit message so the decision can be
reversed by adding stems back, without anyone having to find зноска 55 again.

## Not a gap: optional forms

- **і → й after a vowel** (мама й тата): Збор 2005, §13 — *may*, not *must*. Follows the optional
  forms policy: left as і by default, applied by `morph.conj_i_j` in aggressive mode.

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

- **ґ beyond зноска 55**: ганк, гузак, гузы, грунт, гатунак, гільдыя, гляйс carry ґ in
  common usage but are not among the words the footnote names, and its list ends with "ды
  інш." without saying which others. Held as `uncertain` — they are parsed and counted,
  and never applied, in either mode.

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
- **Country names in every case form** (`data/lexicon/proper_nouns.tsv`, forms from GrammarDB
  RELEASE-202601; same paradigm on both sides, so only the stem changes):
  Аргенціна → Аргентына (Збор 2005 §66), Арменія → Армэнія (§11), Бельгія → Бэльгія,
  Іспанія → Гішпанія (§33, §64), Кыргызстан → Кыргыстан, Мексіка → Мэксыка (Мексіцы → Мэксыцы),
  Расія → Расея (§33), Швейцарыя → Швайцарыя (§80). Германія → Нямеччына (§37) has different
  endings per case: see `lex.case_context`. Бэльгія, Мэксыка and Кыргыстан are not in the rules
  text; their source is the project owner's reference list (a 2014 zviazda.by sentence in
  Taraškievica), spot-checked with baltoslav.eu (comparison only, not a data source).
  **Кыргыстан** was previously unresolved (Кыргыстан vs Кіргізія); resolved on that basis.
- **Расія → Расея, расійскі → расейскі**: Збор 2005, §33 з) "расейскі (ад Расе[й|а])"; the book
  writes расейскі throughout and never Расія/расійскі.
- **Personal names** (checked against the rules text, Збор 2005):
  - removed, contradicted: леанід → лявон (§48: "Лявон … Але: Леанід").
  - removed, optional forms (policy): дзмітрый → зьміцер (§17 lists Дзьмітры – Зьміцер),
    валерый → валер (§17 Валеры – Валер), павел → павал (§55.1 Заўвага А: Павал, Павел).
  - replaced by the §17 base form: дзмітрый → дзьмітры, валерый → валеры (юрый → юры already).
  - removed, not in the book: кірыл → кірыла, афанасій → апанас, іосіф → язэп, фама → хама
    (§81 Заўвага Б has Тамаш, Хама, but not Фама).


`data/lexicon/*.tsv` entries (loanwords, proper nouns, exceptions) are lexical facts, not
rules, but they are equally unverified: they were written from memory, not from a dictionary.
Toponym and country substitutions (Мінск → Менск, Германія → Нямеччына) in particular need a
source.
