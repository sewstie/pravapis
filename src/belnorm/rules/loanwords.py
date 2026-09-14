"""Loanword adaptation rules (Narkamaŭka → Taraškievica).

Taraškievica renders Western loans closer to their source pronunciation:
soft *l* (план → плян), *ы* after dentals in Greco-Latin stems
(сістэма → сыстэма), *э* in Еўропа → Эўропа, the *ґ* plosive in a closed set
of old borrowings (ганак → ґанак), and *х*/*хв* for *ф* in traditional names
(Фёдар → Хведар).

None of these is decidable from the surface form alone — native *лапа* keeps
its hard л while borrowed *лямпа* does not — so each function only fires on
a curated, anchored stem list and leaves everything else to the lexicon and
the classifier. Each is a pure ``str -> str`` on lowercase input and is
composed by the rule engine, never by another rule.
"""

from __future__ import annotations

from typing import Final

import regex

_V: Final[str] = "аеёіоуыэюя"

# --- soft l --------------------------------------------------------------------
# (pattern, replacement): anchored at word start unless the stem is unambiguous.
_L_RULES: Final[tuple[tuple[regex.Pattern[str], str], ...]] = tuple(
    (regex.compile(p), r)
    for p, r in (
        (r"^план", "плян"),
        (r"^клас(?!ц)", "кляс"),
        (r"^ламп", "лямп"),
        (r"^клуб(?!о)", "клюб"),
        (r"^блок", "блёк"),
        (r"^глоб", "глёб"),
        (r"^глаб", "гляб"),
        (r"^лабарат", "лябарат"),
        (r"^бланк", "блянк"),
        (r"^лозунг", "лёзунг"),
        (r"^лакальн", "лякальн"),
        (r"^ландшафт", "ляндшафт"),
        (r"^лагер", "лягер"),
        (r"^лаўрэат", "ляўрэат"),
        (r"^балкон", "балькон"),
        (r"^атлас", "атляс"),
        (r"^дыплам", "дыплям"),
        (r"^дыплом", "дыплём"),
        (r"^платформ", "плятформ"),
        (r"^рэклам", "рэклям"),
        (r"^парламент", "парлямэнт"),
        (r"^кіламетр", "кілямэтр"),
        (r"^кілаграм", "кіляграм"),
        (r"^каланіял", "калёніял"),
        (r"^калоні", "калёні"),
        (r"^салон", "салён"),
        (r"^логік", "лёгік"),
        # -логія only after a vowel: біялогія, тэхналогія; never падлогі (genitive of падлога).
        (rf"(?<=[{_V}])логі", "лёгі"),
    )
)

# --- і → ы after dentals in Greco-Latin stems ------------------------------------
_I_RULES: Final[tuple[tuple[regex.Pattern[str], str], ...]] = tuple(
    (regex.compile(p), r)
    for p, r in (
        (r"^сіст", "сыст"),
        (r"^сігн", "сыгн"),
        (r"^сінт", "сынт"),
        (r"^сінх", "сынх"),
        (r"^сімп", "сымп"),
        (r"^сімул", "сымул"),
        (r"^сітуац", "сытуац"),
        (r"^сірэн", "сырэн"),
        (r"^сінонім", "сынонім"),
        (r"^сінагог", "сынагог"),
        (r"^сіндык", "сындык"),
        (r"^сілуэт", "сылюэт"),
        (r"^прэзід", "прэзыд"),
        (r"^рэзід", "рэзыд"),
        (r"^дысід", "дысыд"),
        (r"^фізі(?=[кчя])", "фізы"),
        (r"^візіт", "візыт"),
        (r"^дэпазіт", "дэпазыт"),
        (r"^(а|апа|кампа|экспа|прапа|дыспа|пра)?пазіц", r"\1пазыц"),
    )
)

# --- Еўропа → Эўропа ---------------------------------------------------------------
_EU_RE: Final[regex.Pattern[str]] = regex.compile(r"^еў")

# --- ф → х / хв in traditional Christian names ---------------------------------------
_F_NAMES: Final[dict[str, str]] = {
    "фёдар": "хведар",
    "фёдара": "хведара",
    "фёдару": "хведару",
    "фёдарам": "хведарам",
    "фёдары": "хведары",
    "фядос": "хвядос",
    "фама": "хама",
    "фаміч": "хаміч",
    "філіп": "піліп",
    "фядора": "хвядора",
}
_F_RE: Final[regex.Pattern[str]] = regex.compile(r"^(?:фёдар|фядос|фядор|фаміч|філіп)")

# --- ґ in a closed set of old Polish/German borrowings ----------------------------------
_G_STEMS: Final[str] = "|".join(
    (
        "анак",
        "анк(?=[аеіуо])",
        "узік",
        "узак",
        "валт",
        "рунт",
        "арсэт",
        "атунак",
        "онт[аы]",
        "ільдыя",
        "ляйс",
        "зымс",
        "узы",
    )
)
_G_RE: Final[regex.Pattern[str]] = regex.compile(rf"^г(?={_G_STEMS})")


def _apply_first(word: str, rules: tuple[tuple[regex.Pattern[str], str], ...]) -> str:
    for pattern, repl in rules:
        new = pattern.sub(repl, word, count=1)
        if new != word:
            return new
    return word


def apply_l_palatalization(word: str) -> str:
    """план → плян, лампа → лямпа, біялогія → біялёгія; лапа → лапа."""
    return _apply_first(word, _L_RULES)


def apply_i_to_y(word: str) -> str:
    """сістэма → сыстэма, прэзідэнт → прэзыдэнт; сіла → сіла."""
    return _apply_first(word, _I_RULES)


def apply_eu_prefix(word: str) -> str:
    """еўропа → эўропа, еўрапейскі → эўрапейскі."""
    return _EU_RE.sub("эў", word, count=1)


def apply_f_substitution(word: str) -> str:
    """фёдар → хведар, фама → хама (traditional given names only)."""
    if word in _F_NAMES:
        return _F_NAMES[word]
    m = _F_RE.match(word)
    if m is None:
        return word
    stem = m.group(0)
    return _F_NAMES.get(stem, stem) + word[len(stem) :]


def apply_g_distinction(word: str) -> str:
    """ганак → ґанак, гузік → ґузік, грунт → ґрунт; гара → гара."""
    return _G_RE.sub("ґ", word, count=1)


def remove_g_distinction(word: str) -> str:
    """ґ → г, always (Narkamaŭka has no ґ)."""
    return word.replace("ґ", "г")
