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

from pravapis.rules.function_words import FunctionWords, default_function_words
from pravapis.rules.palatalization import SOFT_TRIGGERS, SOFT_VOWELS, SOFTENERS
from pravapis.stress import StressTable
from pravapis.types import Orthography

VOWELS: Final[frozenset[str]] = frozenset("аеёіоуыэюя")

#: The particle, clitic and preposition inventories now live in
#: ``data/morphology/function_words.tsv`` and are read by
#: :mod:`pravapis.rules.function_words`. They are closed lists of particular words that
#: decide what the converter outputs, so a port has to have them; a constant here would
#: be invisible to every implementation but this one.
#:
#: Each function below takes them as an argument, the way it already takes the stress
#: table, and **defaults to the shipped inventory**. Defaulting to an empty one would
#: make every caller that forgets the argument silently stop converting — the failure
#: shape this module is least able to detect. Pass ``FunctionWords.empty()`` explicitly
#: to get a converter that knows no function words.

#: Optional (aggressive mode only): conjunction/particle і → й after a vowel.
CONJ_RULE_ID: Final[str] = "morph.conj_i_j"
INITIAL_W_RULE_ID: Final[str] = "morph.initial_u_w"

#: Words whose initial У carries the stress, so §18 does not reach them, are the
#: ``stressed_initial_u`` rows of ``data/morphology/function_words.tsv``. The stress
#: table is built from GrammarDB, which is a lexicon of Belarusian — it does not contain
#: Умбрыя or Уйпэшт, and for a word it does not know `is_first_syllable_stressed` has to
#: answer "no". They are §18's own examples of the exception, listed as stems so the
#: inflected forms are covered too: пра У́мбрыю, да У́йпэшту, выбарчая у́рна.


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
    word: str,
    previous_output: str,
    stress: StressTable | None = None,
    words: FunctionWords | None = None,
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
    inventory = words if words is not None else default_function_words()
    if "-" in word:
        return _hyphenated_u_to_w(word, previous_output, stress, inventory)
    return _one_part_u_to_w(word, previous_output, stress, inventory)


def _one_part_u_to_w(
    word: str, previous: str, stress: StressTable | None, words: FunctionWords
) -> str | None:
    if not word.startswith("У") or not previous:
        return None
    if previous[-1].lower() not in VOWELS:
        return None
    if len(word) == 1:  # "У." — the abbreviated given name
        return None
    if word.isupper():  # an initial abbreviation, not a word beginning with у
        return None
    if words.stressed_initial_u and word.lower().startswith(words.stressed_initial_u):
        return None
    if is_first_syllable_stressed(word, stress, words):
        return None
    return "Ў" + word[1:]


def _hyphenated_u_to_w(
    word: str, previous: str, stress: StressTable | None, words: FunctionWords
) -> str | None:
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
        new = _one_part_u_to_w(part, context, stress, words)
        if new is not None:
            out[i] = new
            changed = True
        context = out[i] or context
    return "-".join(out) if changed else None


def initial_w_to_u(word: str) -> str | None:
    """Правілы 2008, §15 п.4: a proper name never starts with Ў in Narkamaŭka.

    "Гук [у] на пачатку ўласных імён і назваў **заўсёды** перадаецца вялікай літарай У
    складовае **без надрадковага значка**: ва Узбекістан, на Украіне, за Уладзіміра."

    This is the Narkamaŭka side's own authority, and it is categorical, so the reversal
    needs no context: a capital word-initial Ў is written У whatever precedes it. The
    2008 rules contain no word-initial Ў anywhere, and §14 lists *Уэльс* among the
    proper names — the English *W* names included.

    That is why this does **not** consult a list of W-names. The list existed to keep
    *Ўіл*, *Ўотэрз*, *Ўэйлз* spelled with Ў in Narkamaŭka, on the strength of six
    hand-written gold rows; §15 п.4 says the opposite, and be.wikipedia agrees by a
    wide margin (Уільям 115 : Ўіл 1, Уэльс 756 : Ўэльс 2). The inventory is still
    shipped as `data/names/w_names.tsv` because it is real evidence about which names
    these are, but nothing in T → N reads it. See data/NORMS.md.

    Lowercase ў is left alone throughout: both orthographies write *ва ўніверсітэце*.
    An all-caps token is an abbreviation, not a word beginning with у, and is left as
    it is — the same exception the forward direction makes.
    """
    parts = word.split("-")
    out = [
        "У" + part[1:] if part.startswith("Ў") and len(part) > 1 and not part.isupper() else part
        for part in parts
    ]
    return "-".join(out) if out != parts else None


def is_first_syllable_stressed(
    word: str, stress: StressTable | None = None, words: FunctionWords | None = None
) -> bool:
    """Is ``word`` stressed on its first syllable?

    GrammarDB stress marks when a table is given; otherwise (and for words the
    table does not know) only monosyllables and a leading ё count.
    """
    inventory = words if words is not None else default_function_words()
    if word.lower() in inventory.clitics:
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
    words: FunctionWords | None = None,
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
    inventory = words if words is not None else default_function_words()
    if direction is Orthography.NARKAMAUKA:
        return inventory.particles_t2n.get(word)

    result: str | None = None
    if (
        word in inventory.particles_n2t
        and next_word is not None
        and is_first_syllable_stressed(next_word, stress, inventory)
    ):
        result = inventory.particles_n2t[word]
    base = result or word
    onset_form = next_target if next_target is not None else next_word
    if (
        base in inventory.softening_prepositions
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
