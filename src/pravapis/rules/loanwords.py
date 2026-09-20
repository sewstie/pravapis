"""Loanword adaptation rules (Narkamaŭka ↔ Taraškievica).

Taraškievica renders Western loans closer to their source pronunciation: soft *l*
(план → плян), *ы* after hard dentals in Greco-Latin stems (сістэма → сыстэма),
*э* after consonants (сезон → сэзон), the *ґ* plosive in a closed set of old
borrowings (ганак → ґанак), and *х*/*хв* for *ф* in traditional names
(Фёдар → Хведар).

Each alternation is **regular given the etymology**: Збор 2005 §11б states the
э rule as a plain phonological condition ("пасьля зычных, акрамя л і заднеязычных
(г (ґ), к, х)"), and §55.1/§56.2 do the same for soft *l*. What is not recoverable
from the surface form is whether a word is a borrowing at all — native *лапа* and
borrowed *лямпа* look identical to a regex.

So the functions here are general transducers over a **span**, and the etymology
comes from :mod:`pravapis.lexicon.stems`. Each rewrites only inside the matched
stem, which is also what keeps §66 honest for free: in *марксізм* the stem is
*маркс*, so the *-ізм* suffix lies outside the span and is never touched.

Each function is pure and independently testable, and they are composed by the
rule engine, never by each other.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import regex

from pravapis.lexicon.stems import (
    StemEntry,
    StemIndex,
    StemMatch,
    WordClass,
    read_stem_sources,
)
from pravapis.rules.palatalization import mark_assimilative_softness
from pravapis.types import Orthography

_V: Final[str] = "аеёіоуыэюя"
_VOWELS: Final[frozenset[str]] = frozenset(_V)

# --- soft l (Збор 2005 §55.1, §56.2) ---------------------------------------------------
# European *l* is soft: the following back vowel is written iotated, and before a
# consonant or at the end of the stem the softness is written with ь.
_SOFT_L_VOWEL: Final[dict[str, str]] = {"а": "я", "о": "ё", "у": "ю"}
#: vowels that already mark л as soft — nothing to do
_ALREADY_SOFT: Final[frozenset[str]] = frozenset("еёіюя")

# --- і → ы (Збор 2005 §67) -------------------------------------------------------------
#: hard consonants after which і becomes ы in Greco-Latin stems
_Y_TRIGGERS: Final[frozenset[str]] = frozenset("дтзсцжшчр")

# --- е → э (Збор 2005 §11б) ------------------------------------------------------------
#: §11б: "пасьля зычных, акрамя л і заднеязычных (г (ґ), к, х)"
_E_BLOCKERS: Final[frozenset[str]] = frozenset("лгґкх")
_CONSONANTS: Final[frozenset[str]] = frozenset("бвгґджзйклмнпрстўфхцчш")


def _span(word: str, match: StemMatch) -> tuple[str, str, str] | None:
    """Split ``word`` into (before, stem, after) at the match, or None if it is stale.

    The etymology is resolved once, from the word as it arrived. A higher-priority rule
    that changes the word's *length* would leave these indices pointing at the wrong
    letters, so that case is refused: silently rewriting the wrong characters is the
    worse failure. A change at the same length is fine and expected — one alternation
    feeding the next is exactly how класі → клясі → клясы works.
    """
    if not match.spans(word):
        return None
    return word[: match.start], word[match.start : match.end], word[match.end :]


# --- soft l ----------------------------------------------------------------------------
def palatalize_l(stem: str, following: str = "") -> str:
    """ла → ля, ло → лё, лу → лю, and л → ль before a consonant or at the end.

    ``following`` is the character after the stem in the word being converted. A
    stem-final л is not word-final: *алкагол* alone becomes *алькаголь*, but inside
    *алкагольны* the ь is already there, and adding another gives *алькаголььны*. The
    stem boundary is an artefact of the inventory, not a fact about the word.
    """
    out: list[str] = []
    for i, ch in enumerate(stem):
        if ch != "л":
            out.append(ch)
            continue
        nxt = stem[i + 1] if i + 1 < len(stem) else following[:1]
        if nxt in _ALREADY_SOFT or nxt == "ь" or nxt in _SOFT_L_VOWEL:
            out.append(ch)
        else:
            out.append("ль")
    # the vowel rewrite is done in a second pass so indices stay stable
    text = "".join(out)
    return regex.sub(r"л([аоу])", lambda m: "л" + _SOFT_L_VOWEL[m.group(1)], text)


def apply_l_palatalization(word: str, match: StemMatch) -> str:
    """план → плян, лампа → лямпа, біялогія → біялёгія; лапа → лапа."""
    if not match.allows("l"):
        return word
    span = _span(word, match)
    if span is None:
        return word
    before, stem, after = span
    return before + palatalize_l(stem, after) + after


# --- і → ы -----------------------------------------------------------------------------
def i_to_y(stem: str) -> str:
    """і → ы after a hard dental or husher."""
    return "".join(
        "ы" if ch == "і" and i > 0 and stem[i - 1] in _Y_TRIGGERS else ch
        for i, ch in enumerate(stem)
    )


def apply_i_to_y(word: str, match: StemMatch) -> str:
    """сістэма → сыстэма, прэзідэнт → прэзыдэнт; сіла → сіла."""
    if not match.allows("i"):
        return word
    span = _span(word, match)
    if span is None:
        return word
    before, stem, after = span
    return before + i_to_y(stem) + after


# --- е → э -----------------------------------------------------------------------------
#: The adjective suffix -ейск- keeps its е whatever the root does: Эўропа → эўрапейскі,
#: never эўрапэйскі, and likewise армейскі, асамблейскі, юбілейскі. Without this the §11б
#: rule would reach into the suffix as soon as a stem covered it.
_EJSK: Final[regex.Pattern[str]] = regex.compile(r"ейск")


def e_to_eh(stem: str) -> str:
    """е → э after any consonant except л and the velars г, ґ, к, х (§11б).

    The adjective suffix -ейск- is exempt: its е is structural and never hardens.
    """
    protected = {i for m in _EJSK.finditer(stem) for i in range(m.start(), m.start() + 1)}
    return "".join(
        "э"
        if ch == "е" and i > 0 and i not in protected and stem[i - 1] in _CONSONANTS - _E_BLOCKERS
        else ch
        for i, ch in enumerate(stem)
    )


def apply_e_to_eh(word: str, match: StemMatch) -> str:
    """сезон → сэзон, версія → вэрсія, аперацыя → апэрацыя; лекцыя → лекцыя."""
    if not match.allows("e"):
        return word
    span = _span(word, match)
    if span is None:
        return word
    before, stem, after = span
    return before + e_to_eh(stem) + after


# --- ґ ---------------------------------------------------------------------------------
# The forward rule (г → ґ) was removed: Збор 2005 зноска 55 licenses ґ but the alphabet
# marks the letter as факультатыўна, and this project takes the other option and writes
# г everywhere. Only the stripping direction remains. See data/NORMS.md.
def remove_g_distinction(word: str) -> str:
    """ґ → г, always (Narkamaŭka has no ґ). Needs no etymology: ґ only occurs in loans."""
    return word.replace("ґ", "г")


# --- Еўропа → Эўропа (Збор 2005 §52) ---------------------------------------------------
_EU_RE: Final[regex.Pattern[str]] = regex.compile(r"^еў")


def apply_eu_prefix(word: str) -> str:
    """еўропа → эўропа, еўрапейскі → эўрапейскі."""
    return _EU_RE.sub("эў", word, count=1)


# --- ф → хв in traditional Christian names (OPTIONAL) ----------------------------------
# Збор 2005, §81 Заўвага Б lists several valid forms side by side: "Тодар, Фёдар, Хведар,
# Ходар; … Фядос, Хвядос, Ходас". Фёдар is already correct, so this rewrite is optional
# and runs only in aggressive mode.
_F_NAMES: Final[dict[str, str]] = {
    "фёдар": "хведар",
    "фядос": "хвядос",
}
_F_RE: Final[regex.Pattern[str]] = regex.compile(r"^(?:фёдар|фядос)")


def apply_f_substitution(word: str) -> str:
    """фёдар → хведар, фядос → хвядос, with endings kept (optional; §81 Заўвага Б)."""
    if word in _F_NAMES:
        return _F_NAMES[word]
    m = _F_RE.match(word)
    if m is None:
        return word
    stem = m.group(0)
    return _F_NAMES.get(stem, stem) + word[len(stem) :]


# --- deriving the Taraškievica side of the inventory -----------------------------------
#: applied in this order when deriving a target stem; the transducers commute in
#: practice but a fixed order keeps the derivation reproducible.
_FORWARD: Final[tuple[tuple[str, object], ...]] = (
    ("g", lambda s: s.replace("г", "ґ", 1)),
    ("l", palatalize_l),
    ("i", i_to_y),
    ("e", e_to_eh),
)


def _apply_alternations(stem: str, alternations: frozenset[str], following: str = "") -> str:
    for code, fn in _FORWARD:
        if code not in alternations:
            continue
        stem = palatalize_l(stem, following) if code == "l" else fn(stem)  # type: ignore[operator]
    return stem


def target_stem(entry: StemEntry) -> str:
    """The Taraškievica spelling of a Narkamaŭka stem, from its own alternations.

    The reverse direction sees Taraškievica text, so it needs the inventory keyed by
    Taraškievica stems. Deriving them here — rather than listing them by hand — is what
    guarantees the two directions cannot drift apart.
    """
    if entry.target is not None:
        return entry.target
    return _apply_alternations(entry.stem, entry.alternations)


def derive_target_entries(entries: list[StemEntry]) -> list[StemEntry]:
    """``entries`` re-keyed by their Taraškievica form, for the T → N direction.

    Every reverse entry carries the Narkamaŭka stem as its ``target``, so T → N is a
    **stem substitution**, not an inverse transducer. That is what makes it exact: the
    string alone cannot tell which ``ь`` to remove — балькон → балкон must lose one and
    лякальн → лакальн must not — but the entry knows both spellings.

    A stem with any forward-only alternation gets no reverse entry at all: that flag
    exists precisely because its Taraškievica form is ambiguous, and the project leaves
    ambiguous forms alone.
    """
    out: list[StemEntry] = []
    for e in entries:
        if e.cls is WordClass.NATIVE:
            out.append(e)
            continue
        if e.forward_only or not (e.alternations or e.target):
            continue
        # Real Taraškievica text also carries assimilative softness, and softness is
        # marked on the *pre-alternation* form: бізнес → бізьнес → бізьнэс, because
        # palatalization outranks the loan rules. Index every spelling the forward
        # pipeline can produce, since the etymology is resolved once, from the word as
        # it arrives, and must match it as written.
        derived = target_stem(e)
        softened = (
            mark_assimilative_softness(e.stem)
            if e.target is None
            else mark_assimilative_softness(e.target)
        )
        # A stem ending in л has two Taraškievica spellings: алкаголь at the end of a
        # word, алкагол- before an ending. Both must be indexed, or алькагольны has no
        # reverse. Any vowel serves as the "something follows" case.
        in_word = _apply_alternations(e.stem, e.alternations, "а") if e.target is None else derived
        variants = (
            derived,
            in_word,
            mark_assimilative_softness(derived),
            mark_assimilative_softness(in_word),
            _apply_alternations(softened, e.alternations) if e.target is None else softened,
        )
        for stem in dict.fromkeys(variants):
            out.append(
                StemEntry(
                    stem=stem,
                    cls=e.cls,
                    alternations=frozenset(),
                    source=e.source,
                    provenance=e.provenance,
                    anchored=e.anchored,
                    target=e.stem,
                )
            )
    return out


# --- irregular stems -------------------------------------------------------------------
def apply_stem_target(word: str, match: StemMatch) -> str:
    """Replace the matched stem with its explicit target (the 6th TSV column).

    For stems whose alternation is not regular in either direction — ``каланіял →
    калёніял`` restores an etymological *о* that akanne wrote as *а*.
    """
    if match.target is None:
        return word
    span = _span(word, match)
    if span is None:
        return word
    before, _, after = span
    return before + match.target + after


def reverse_collisions(entries: list[StemEntry]) -> list[str]:
    """Loan stems whose derived Taraškievica key is shared by another stem.

    Two Narkamaŭka stems deriving to one Taraškievica form make the reverse direction
    ambiguous, and a dict would silently keep whichever came last.
    """
    by_key: dict[str, list[str]] = {}
    for e in derive_target_entries(entries):
        if e.cls is WordClass.LOAN and e.target is not None:
            by_key.setdefault(e.stem, [])
            if e.target not in by_key[e.stem]:
                by_key[e.stem].append(e.target)
    return [
        f"Taraškievica stem {stem!r} is derived from several Narkamaŭka stems: {sorted(srcs)}"
        for stem, srcs in by_key.items()
        if len(srcs) > 1
    ]


def build_stem_indexes(path: Path | None) -> dict[Orthography, StemIndex]:
    """Per-direction stem inventories: Narkamaŭka keys for N → T, derived Taraškievica keys
    for T → N.

    The reverse keys are computed from the forward ones by :func:`target_stem`, never
    listed by hand, so the two directions cannot disagree about what a stem licenses.
    """
    if path is None or not path.exists():
        return {d: StemIndex.empty() for d in Orthography}
    entries = read_stem_sources(path)
    return {
        Orthography.TARASKIEVICA: StemIndex(entries),
        Orthography.NARKAMAUKA: StemIndex(derive_target_entries(entries)),
    }
