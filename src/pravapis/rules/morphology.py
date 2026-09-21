"""Context-dependent clitics (Збор правілаў 2005, §3 and §29).

Jakanne (§3): the particle *не* and the preposition *без* become *ня* / *бяз*
when they stand in the syllable right before the stress, i.e. when the next
word is stressed on its first syllable: *ня наш, ня по´йдзе, бяз кры´ўды*.
*не было́* stays *не*: the stress is on the second syllable.

Assimilative softness (§29) extends to the prepositions *з, без/бяз, праз,
цераз* before a soft onset, whether or not jakanne applied: *зь вераю, бязь
сьлёз, празь лес, церазь сетку; безь яго*. §29 Заўвага А: before an
*unstressed* initial *і* no [й] develops, so there is no softening: *з ідэяй,
без іголкі, праз імглу* — but *бязь і´х, зь І´наю* when the і is stressed.

Both need the next word, so they run in the pipeline rather than the per-word
rule engine. Stress is not written in Belarusian text; it comes from GrammarDB
stress marks (``pravapis.stress.StressTable``). Without a table only two facts
are used: a monosyllabic content word is stressed on its only syllable, and ё
is always stressed. Anything else counts as not first-stressed.
"""

from __future__ import annotations

from typing import Final

from pravapis.rules.palatalization import SOFT_TRIGGERS, SOFT_VOWELS, SOFTENERS
from pravapis.stress import StressTable
from pravapis.types import Orthography

VOWELS: Final[frozenset[str]] = frozenset("аеёіоуыэюя")

#: не/без → ня/бяз (N→T) and back (T→N).
PARTICLES_N2T: Final[dict[str, str]] = {"не": "ня", "без": "бяз"}
PARTICLES_T2N: Final[dict[str, str]] = {
    "ня": "не",
    "бяз": "без",
    "бязь": "без",
    "безь": "без",
    "зь": "з",
}

#: Prepositions that soften before a soft onset (§29): з, без/бяз, праз, цераз.
SOFTENING_PREPOSITIONS: Final[frozenset[str]] = frozenset({"з", "без", "бяз", "праз", "цераз"})

#: Unstressed function words: a monosyllable here does not attract "ня"/"бяз".
CLITICS: Final[frozenset[str]] = frozenset(
    [
        "у",
        "ў",
        "з",
        "зь",
        "на",
        "да",
        "па",
        "за",
        "аб",
        "ад",
        "пра",
        "і",
        "й",
        "ды",
        "а",
        "ці",
        "б",
        "бы",
        "ж",
        "жа",
        "не",
        "ня",
        "без",
        "бяз",
        "для",
        "пад",
        "над",
        "праз",
        "цераз",
        "к",
        "аж",
        "бо",
        "то",
        "ні",
    ]
)


#: Optional (aggressive mode only): conjunction/particle і → й after a vowel.
CONJ_RULE_ID: Final[str] = "morph.conj_i_j"
INITIAL_W_RULE_ID: Final[str] = "morph.initial_u_w"

#: Words whose initial У carries the stress, so §18 does not reach them. The stress
#: table is built from GrammarDB, which is a lexicon of Belarusian — it does not contain
#: Умбрыя or Уйпэшт, and for a word it does not know `is_first_syllable_stressed` has to
#: answer "no". These are §18's own examples of the exception, listed as stems so the
#: inflected forms are covered too: пра У́мбрыю, да У́йпэшту, выбарчая у́рна.
STRESSED_INITIAL_U: Final[tuple[str, ...]] = ("умбры", "уйпэшт", "урн")

#: Names whose Ў renders English *W*, not §18's alternation of у. After a vowel the two
#: are indistinguishable — *школу Ўайлд* could be either — and Narkamaŭka keeps the Ў in
#: this one, so reversing it would corrupt a name. Seeded from the hand-written rows of
#: `data/eval/tarask/gold_t2n.tsv`, which is where the question was first noticed.
#:
#: This list is open-ended by nature and that is a real limit of the rule, recorded in
#: data/NORMS.md rather than hidden: an unlisted W-name that follows a vowel will come
#: back from T → N with У. The forward direction is unaffected, because a name already
#: written Ў never matches a rule that looks for У.
W_NAMES: Final[tuple[str, ...]] = (
    "ўіл",
    "ўотэр",
    "ўэлт",
    "ўэйлз",
    "ўайлд",
)


def conjunction_i_to_j(word: str, previous_output: str) -> str | None:
    """Збор 2005, §13: after a word ending in a vowel, the conjunction і *may* become й.

    Optional, so the pipeline applies it only in aggressive mode. ``word`` is the
    standalone token (і / І); ``previous_output`` is the preceding word as written in
    the output. Returns й / Й, or None when the rule does not apply.
    """
    if word not in ("і", "І") or not previous_output:
        return None
    if previous_output[-1].lower() not in VOWELS:
        return None
    return "й" if word == "і" else "Й"


def syllable_count(word: str) -> int:
    return sum(1 for c in word.lower() if c in VOWELS)


def initial_u_to_w(
    word: str, previous_output: str, stress: StressTable | None = None
) -> str | None:
    """Збор 2005, §18: after a vowel, an unstressed initial У becomes Ў.

    The rule's own examples are the case this implements, capital letters and all:
    *сталіца Ўкраіны*, *ва Ўфе*, *Марыя Ўласевіч*, *ЗША ўзьнялі пытаньне*.

    **Only capitalised words.** Lowercase у after a vowel is already ў in Narkamaŭka
    too (*ва ўніверсітэце*), so there is nothing to convert; the orthographies part
    company on proper nouns, which Narkamaŭka leaves as У — *ва Украіне* against
    Taraškievica *ва Ўкраіне*. Restricting to capitals is therefore not caution, it is
    the actual boundary between the two systems.

    §18 names three exceptions, and the first is why this needs the stress table:

    * **stressed у stays у** — *але у́т*, *Са у́даўская Арабія*, *да У́йпэшту*,
      *пра У́мбрыю*. Whether Умбрыя keeps its У is not decidable from spelling.
    * **the initial "У." standing for a name** — *за У. Сыракомлю*, *пра У. Караткевіча*.
    * **initial abbreviations** — БДЭУ, РУУС, САУ.

    ``previous_output`` is the preceding word as it will be written in the output, so a
    preceding word that itself changed is read in its converted form. Returns the new
    word, or None when the rule does not apply.
    """
    if "-" in word:
        return _hyphenated_u_to_w(word, previous_output, stress)
    return _one_part_u_to_w(word, previous_output, stress)


def _one_part_u_to_w(word: str, previous: str, stress: StressTable | None) -> str | None:
    if not word.startswith("У") or not previous:
        return None
    if previous[-1].lower() not in VOWELS:
        return None
    if len(word) == 1:  # "У." — the abbreviated given name
        return None
    if word.isupper():  # an initial abbreviation, not a word beginning with у
        return None
    if word.lower().startswith(STRESSED_INITIAL_U):
        return None
    if is_first_syllable_stressed(word, stress):
        return None
    return "Ў" + word[1:]


def _hyphenated_u_to_w(word: str, previous: str, stress: StressTable | None) -> str | None:
    """§18 Заўвага: "Злучок і двукосьсе ня ёсьць знакамі прыпынку".

    So the hyphen inside *Кука-Ўітсан* is as transparent as the space in *сталіца
    Ўкраіны*, and each part is judged against the part before it — the first against the
    previous word, as the book's own *рыба-ўюн* requires. The tokenizer keeps a
    hyphenated compound as one token, so without this the rule would simply never see
    the second half.
    """
    parts = word.split("-")
    out = list(parts)
    context = previous
    changed = False
    for i, part in enumerate(parts):
        new = _one_part_u_to_w(part, context, stress)
        if new is not None:
            out[i] = new
            changed = True
        context = out[i] or context
    return "-".join(out) if changed else None


def initial_w_to_u(word: str, previous_output: str) -> str | None:
    """The reverse of §18, and **only** of §18.

    It undoes the alternation where the alternation could have happened: after a word
    ending in a vowel. A capital Ў anywhere else was never produced by §18 and must be
    left exactly as it is, because Belarusian also writes Ў at the start of a name to
    render English *W* — *Разумнік Ўіл Гантынг*, *з Ўотэрзам* — and those keep their Ў
    in Narkamaŭka too (`data/eval/tarask/gold_t2n.tsv`, hand-written rows).

    The two are indistinguishable after a vowel, where either could have produced the Ў.
    See ``W_NAMES`` for what is done about that.

    Lowercase ў is left alone throughout: both orthographies write *ва ўніверсітэце*.
    """
    if not previous_output or previous_output[-1].lower() not in VOWELS:
        return None
    parts = word.split("-")
    out = [
        "У" + part[1:]
        if part.startswith("Ў") and len(part) > 1 and not part.lower().startswith(W_NAMES)
        else part
        for part in parts
    ]
    return "-".join(out) if out != parts else None


def is_first_syllable_stressed(word: str, stress: StressTable | None = None) -> bool:
    """Is ``word`` stressed on its first syllable?

    GrammarDB stress marks when a table is given; otherwise (and for words the
    table does not know) only monosyllables and a leading ё count.
    """
    if word.lower() in CLITICS:
        return False
    if stress is not None and stress.is_first_stressed(word):
        return True
    lw = word.lower()
    if syllable_count(lw) == 1:
        return True
    # ё is always stressed, so a word whose first vowel is ё is first-stressed.
    return next((c for c in lw if c in VOWELS), "") == "ё"


def _soft_onset(word: str) -> bool:
    """Does ``word`` begin with a soft consonant or a soft vowel?"""
    if not word:
        return False
    if word[0] in SOFT_VOWELS:
        return True
    head = word[:2] if word[:2] == "дз" else word[0]
    if head not in SOFT_TRIGGERS:
        return False
    return word[len(head) : len(head) + 1] in set(SOFTENERS)


def convert_particle(
    word: str,
    next_word: str | None,
    direction: Orthography,
    stress: StressTable | None = None,
    next_target: str | None = None,
) -> str | None:
    """Rewrite a clitic given the word that follows it; None when no rule applies.

    Input is lowercase. Returns the fully converted form (including the soft
    sign on *бязь* / *зь*), so the caller can skip the per-word engine for it.

    The two conditions read *different* forms of the next word:

    - stress (jakanne) reads ``next_word``, the Narkamaŭka form, because the
      stress table is built from GrammarDB, which is Narkamaŭka;
    - soft onset reads ``next_target``, the next word already converted to
      Taraškievica, because only there is assimilative softness written:
      Narkamaŭka *слёз* shows no soft с, Taraškievica *сьлёз* does. Reading
      the Narkamaŭka form is the без слёз → *бяз сьлёз bug. Without
      ``next_target`` the Narkamaŭka form is the fallback.
    """
    if direction is Orthography.NARKAMAUKA:
        return PARTICLES_T2N.get(word)

    result: str | None = None
    if (
        word in PARTICLES_N2T
        and next_word is not None
        and is_first_syllable_stressed(next_word, stress)
    ):
        result = PARTICLES_N2T[word]
    base = result or word
    onset_form = next_target if next_target is not None else next_word
    if (
        base in SOFTENING_PREPOSITIONS
        and next_word is not None
        and onset_form is not None
        and _soft_onset(onset_form.lower())
        and not _unstressed_initial_i(next_word, stress)
    ):
        result = base + "ь"
    return result


def _unstressed_initial_i(word: str, stress: StressTable | None) -> bool:
    """§29 Заўвага А: an unstressed initial і develops no [й], so з/без/праз stay hard.

    Reads the Narkamaŭka form (stress comes from GrammarDB); the letter і is the
    same in both orthographies.
    """
    return word[:1].lower() == "і" and not is_first_syllable_stressed(word, stress)
