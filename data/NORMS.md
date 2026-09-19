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

Optional under this policy: `loan.f_substitution` (§81 Заўвага Б) and `morph.conj_i_j` (§13).

---

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

### loan.g_distinction
- direction: narkamauka → taraskievica
- does: plosive ґ in a closed list of old borrowings: ганак → ґанак, гузік → ґузік
- source: UNVERIFIED. The rules text mentions ґ only for foreign proper names, and optionally
  (§61 "можа перадавацца"). Common words like ґанак, ґузік would be in the spelling dictionaries,
  which the electronic edition does not contain (see `data/reference/README.md`). Cannot be
  resolved from the available source.

### loan.g_remove
- direction: taraskievica → narkamauka
- does: ґ → г everywhere
- source: UNVERIFIED (Narkamaŭka norm; not covered by the 2005 Збор правілаў)

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
  in a vowel, with only whitespace between: сала і цыбулю → сала й цыбулю. After punctuation it
  stays і; a word-initial і- is never touched.
- source: Збор 2005, §13 ("Пасьля словаў, якія канчаюцца на галосны, злучнік і часьцінка і
  складовае **можа** пераходзіць у й нескладовае … Пачатковае і- … пішацца нязьменна")

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

## Known gaps (not implemented, need the codification)

- **Genitive plural -аў** (хвілін → хвілінаў): no rule, no gold coverage; needs a noun list.
  Single word added by hand on the project owner's instruction: **краін → краінаў**
  (`data/lexicon/exceptions.tsv`; "з 18 краінаў", confirmed by baltoslav.eu spot-check). Every
  other genitive plural is still unchanged.
  The Збор 2005 rules cover spelling only ("выключна артаграмы") and do not settle it.

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
