"""The cascade: identity → lexicon → rules → passthrough. First hit wins.

Lexicon runs *before* rules because loanwords are exactly the words the
phonological rules get wrong (клас → кляса, not клас).

An experimental classifier step (between rules and passthrough) exists behind
the ``[ml]`` extra and is off by default: it is only built when a config names
a model explicitly. It sees words that neither stage touched and that match
an ambiguity trigger, and its answer is discarded below the confidence
threshold.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, overload

import regex

from pravapis.casing import recase
from pravapis.config import DEFAULT_AMBIGUITY_TRIGGERS, Config
from pravapis.lexicon.builder import StaleLexiconError
from pravapis.lexicon.case_forms import CASE_RULE_ID, CaseForms
from pravapis.lexicon.store import Lexicon
from pravapis.morphology import MENT_RULE_ID, MentSuffix
from pravapis.normalize import sanitize
from pravapis.rules.engine import RuleEngine
from pravapis.rules.function_words import FunctionWords, default_function_words
from pravapis.rules.loanwords import build_stem_indexes
from pravapis.rules.morphology import (
    CONJ_RULE_ID,
    INITIAL_W_RULE_ID,
    conjunction_i_to_j,
    convert_particle,
    initial_u_to_w,
    initial_w_to_u,
)
from pravapis.stress import StressTable
from pravapis.tokenize import (
    bridges_words,
    context_of,
    is_belarusian_word,
    next_word,
    previous_word,
    tokenize,
)
from pravapis.translit import PAIRED, REVERSIBLE, Transliterator, detect_script
from pravapis.translit.engine import TransliterationResult
from pravapis.types import (
    METHOD_PRIORITY,
    ChangeContext,
    Conversion,
    ConversionResult,
    Method,
    Orthography,
    RuleTrace,
    Script,
    Token,
    TokenExplanation,
    TokenKind,
)

if TYPE_CHECKING:
    from pravapis.disambiguate.predict import Disambiguator

log = logging.getLogger(__name__)

PARTICLE_RULE_ID: Final[str] = "morph.particle"
CACHE_LIMIT: Final[int] = 200_000

#: The rules that read a neighbouring word, and what they read. Only these get a
#: ``context`` on the wire, so a ``null`` there positively means the change is
#: reproducible from the word alone. Keyed by rule id because that is what a change
#: carries; a combined id ("morph.particle+palat.assim") matches on any component.
CROSS_WORD_TRIGGERS: Final[dict[str, tuple[str, str | None]]] = {
    PARTICLE_RULE_ID: ("next_word", None),
    CASE_RULE_ID: ("prev_word", None),
    CONJ_RULE_ID: ("prev_word_vowel", "§13"),
    INITIAL_W_RULE_ID: ("prev_word_vowel", "§18"),
}

#: Citations for the rules that run here rather than in the YAML engine, because they
#: need the neighbouring word or a morphological fact. The YAML rules carry their own
#: `citation` field; these four have nowhere to carry one, so they are listed against
#: their entries in data/NORMS.md. Every change record can then name its source.
PSEUDO_RULE_CITATIONS: Final[dict[str, str]] = {
    CASE_RULE_ID: "Збор 2005, §37; GrammarDB RELEASE-202601 paradigms",
    PARTICLE_RULE_ID: "Збор 2005, §3, §29, §29 Заўвага А",
    CONJ_RULE_ID: "Збор 2005, §13",
    INITIAL_W_RULE_ID: "Збор 2005, §18; §20 (N→T) / Правілы 2008, §15 п.4 (T→N)",
    MENT_RULE_ID: "Збор 2005, §11б",
}


def context_sensitive(words: FunctionWords) -> frozenset[str]:
    """Words whose conversion depends on the next word; never memoised.

    Derived from the inventories rather than listed again: a particle added to
    ``data/morphology/function_words.tsv`` that was not also added here would be
    memoised on its first context and then converted wrongly ever after.
    """
    return (
        frozenset(words.particles_n2t)
        | frozenset(words.particles_t2n)
        | words.softening_prepositions
    )


#: Shared empty context, so the no-classifier path allocates no list per token.
_NO_CONTEXT: Final[list[Token]] = []

#: (lowercase target, method, rule ids) for a context-free word.
Resolved = tuple[str, Method, str | None]


def _across(tokens: Sequence[Token], i: int, *, back: bool) -> str | None:
    """The non-space characters a cross-word rule reached over, or None if only space.

    §18 Заўвага — "Злучок і двукосьсе ня ёсьць знакамі прыпынку" — lets these rules see
    past a hyphen or a quotation mark. That is the part of a firing a reader is least
    able to reconstruct from the two words alone, so it is recorded: *школу «Ўітні»* is
    a rule reaching across a «, and `across: null` says the two words were merely
    adjacent.
    """
    step = -1 if back else 1
    j = i + step
    bridged: list[str] = []
    while 0 <= j < len(tokens) and tokens[j].kind is not TokenKind.WORD:
        if tokens[j].kind is not TokenKind.SPACE:
            bridged.append(tokens[j].text)
        j += step
    if not (0 <= j < len(tokens)):
        return None
    if back:
        bridged.reverse()
    joined = "".join(bridged)
    return joined or None


def _context_for(
    conv: Conversion, tokens: Sequence[Token], i: int, direction: Orthography
) -> ChangeContext | None:
    """The cross-word context for a change, or None when the rule read only the word.

    Assigned in one place, from the rule that fired, rather than at each construction
    site: a rule that gains a neighbour-reading condition then cannot quietly keep
    reporting ``context: null``.
    """
    if not conv.changed or conv.rule_id is None:
        return None
    for part in conv.rule_id.split("+"):
        trigger = CROSS_WORD_TRIGGERS.get(part)
        if trigger is None:
            continue
        # T → N undoes §18 unconditionally (Правілы 2008 §15 п.4), reading no
        # neighbour, so only the forward direction is cross-word there.
        if part == INITIAL_W_RULE_ID and direction is not Orthography.TARASKIEVICA:
            continue
        name, rule = trigger
        return ChangeContext(
            trigger=name,
            across=_across(tokens, i, back=name.startswith("prev")),
            rule=rule,
        )
    return None


def _recase_like(source: str, lw: str, target: str) -> str:
    """Give ``target`` the capitalisation of ``source``, part by part for hyphenated words."""
    if target == lw:
        return source
    if "-" in source and source.count("-") == target.count("-"):
        return "-".join(
            recase(s, t) for s, t in zip(source.split("-"), target.split("-"), strict=True)
        )
    return recase(source, target)


class Converter:
    def __init__(
        self,
        lexicon: Lexicon,
        engine: RuleEngine,
        disambiguator: Disambiguator | None = None,
        config: Config | None = None,
        stress: StressTable | None = None,
        *,
        aggressive: bool = False,
        case_forms: CaseForms | None = None,
        ment_suffix: MentSuffix | None = None,
        function_words: FunctionWords | None = None,
    ):
        """``aggressive`` also applies optional transformations: rewrites of forms the
        codification already allows (Фёдар → Хведар, і → й after a vowel). Off by default;
        see data/NORMS.md, "Policy: optional forms"."""
        self.lexicon = lexicon
        #: where the lexicon came from, for reports (set by from_config)
        self.lexicon_origin = "in-memory"
        self.aggressive = aggressive
        self.engine = engine.with_optional(aggressive)
        self.disambiguator = disambiguator
        self.config = config
        self.stress = stress
        self.case_forms = case_forms if case_forms is not None else CaseForms.empty()
        self.ment_suffix = ment_suffix if ment_suffix is not None else MentSuffix.empty()
        #: Particle, clitic and preposition inventories, from data.
        self.function_words = (
            function_words if function_words is not None else default_function_words()
        )
        self._context_sensitive = context_sensitive(self.function_words)
        triggers = config.ambiguity_triggers if config else DEFAULT_AMBIGUITY_TRIGGERS
        self._triggers: tuple[regex.Pattern[str], ...] = tuple(regex.compile(t) for t in triggers)
        self._cache: dict[tuple[str, Orthography], Resolved | None] = {}
        #: rule_id (possibly several joined with "+") -> citation. Memoised because the
        #: set of combinations that actually occur is small and closed, so after warmup
        #: attaching a citation to a change is a dict hit.
        self._citations: dict[str | None, str | None] = {None: None}
        self._variants: dict[bool, Converter] = {aggressive: self}
        if disambiguator is not None and config is not None:
            disambiguator.threshold = config.confidence_threshold

    def variant(self, aggressive: bool) -> Converter:
        """This converter with optional transformations on or off (shares lexicon and stress)."""
        if aggressive not in self._variants:
            other = Converter(
                self.lexicon,
                self.engine,
                self.disambiguator,
                self.config,
                self.stress,
                aggressive=aggressive,
                case_forms=self.case_forms,
                ment_suffix=self.ment_suffix,
                function_words=self.function_words,
            )
            other._variants = self._variants
            other.lexicon_origin = self.lexicon_origin
            self._variants[aggressive] = other
        return self._variants[aggressive]

    # --- script ---------------------------------------------------------------
    def render(self, text: str, script: Script, *, convert: bool = True) -> str:
        """Convert to the orthography ``script`` is paired with, then transliterate.

        Łacinka and Taraškievica share a softness convention, so ``снег`` rendered as
        Łacinka is ``śnieh``, not ``snieh`` — the orthography step is what makes the
        output idiomatic rather than merely legible. ``convert=False`` skips it and
        transliterates the input exactly as given.
        """
        return self.render_result(text, script, convert=convert).text

    def render_result(
        self, text: str, script: Script, *, convert: bool = True
    ) -> TransliterationResult:
        """:meth:`render`, keeping the graphemes the scheme could not render faithfully."""
        if script is Script.CYRILLIC:
            out = self.convert(text, Orthography.TARASKIEVICA).text if convert else text
            return TransliterationResult(out, ())
        clean = sanitize(text)
        if convert:
            clean = self.convert(clean, PAIRED[script]).text
        return Transliterator.load(script).transliterate(clean)

    def read_script(self, text: str, script: Script, direction: Orthography | None = None) -> str:
        """Latin → Cyrillic, optionally converting to ``direction`` afterwards.

        Only schemes in :data:`pravapis.translit.REVERSIBLE` can be read: the 2007
        romanisation does not write assimilative softness, so reading it back would be
        a guess, and this project does not guess.
        """
        if script not in REVERSIBLE:
            raise ValueError(
                f"{script.value} cannot be read back into Cyrillic: it does not write "
                "assimilative softness, so the reverse would not round-trip"
            )
        clean = sanitize(text, script)
        cyrillic = Transliterator.load(script, reverse=True).transliterate(clean).text
        if direction is None or direction is PAIRED[script]:
            return cyrillic
        return self.convert(cyrillic, direction).text

    def transcode(self, text: str, to: Script, *, from_script: Script | None = None) -> str:
        """Convert between writing systems, detecting the source when not told.

        Latin → Latin goes through Cyrillic, and through *both* orthographies, because
        the two Latin schemes are paired with different ones: Łacinka ``śnieh`` reads back
        to Taraškievica ``сьнег``, which becomes Narkamaŭka ``снег``, which the 2007
        scheme writes ``snieh``. Skipping the orthography step would hand the official
        scheme a Taraškievica input and produce a spelling neither convention uses.

        Only schemes in :data:`pravapis.translit.REVERSIBLE` can be read *from*; the 2007
        romanisation does not write assimilative softness, so there is nothing faithful to
        read back.
        """
        source = from_script or detect_script(text).script
        if source is None:
            raise ValueError("cannot tell what script this text is in")
        if source is to:
            return text
        if source is Script.CYRILLIC:
            return self.render(text, to)
        cyrillic = self.read_script(text, source)
        if to is Script.CYRILLIC:
            return cyrillic
        return self.render(cyrillic, to)

    @classmethod
    def from_config(cls, path: Path | Config | None = None) -> Converter:
        if path is None:
            config = Config.default()
        elif isinstance(path, Config):
            config = path
        else:
            config = Config.load(path)
        compiled = not (config.lexicon.is_dir() or config.lexicon.suffix == ".tsv")
        checked = config.lexicon_sources is not None and config.lexicon_sources.exists()
        try:
            lexicon = Lexicon.load(config.lexicon, sources=config.lexicon_sources)
            if not compiled:
                origin = f"TSV sources {config.lexicon}"
            elif checked:
                origin = f"compiled {config.lexicon} (hash matches {config.lexicon_sources})"
            else:
                origin = f"compiled {config.lexicon} (sources not available, hash not checked)"
        except StaleLexiconError as exc:
            # Never serve stale entries. With the sources at hand, rebuild in memory
            # and say so loudly; without them there is nothing correct to serve.
            if not checked:
                raise
            assert config.lexicon_sources is not None
            log.warning("%s — using the TSV sources in %s instead", exc, config.lexicon_sources)
            lexicon = Lexicon.load(config.lexicon_sources)
            origin = f"TSV sources {config.lexicon_sources} (compiled {config.lexicon} was STALE)"
        engine = RuleEngine.from_yaml(*config.rules, stems=build_stem_indexes(config.stems))
        stress = StressTable.load(config.stress) if config.stress is not None else None
        disambiguator: Disambiguator | None = None
        if config.model is not None:  # explicit opt-in only; Config.default() never sets it
            try:
                from pravapis.disambiguate.predict import Disambiguator

                disambiguator = Disambiguator.load(
                    config.model, threshold=config.confidence_threshold
                )
            except Exception as exc:  # fail-safe: rules + lexicon still work
                log.warning("disambiguation model %s not loaded: %s", config.model, exc)
        function_words = FunctionWords.load(config.lexicon.parent)
        case_forms = (
            CaseForms.load(config.case_forms, function_words.dative_locative_prepositions)
            if config.case_forms is not None and config.case_forms.exists()
            else None
        )
        conv = cls(
            lexicon,
            engine,
            disambiguator,
            config,
            stress,
            case_forms=case_forms,
            function_words=function_words,
            ment_suffix=(
                MentSuffix.load(config.morphology)
                if config.morphology is not None and config.morphology.exists()
                else None
            ),
        )
        conv.lexicon_origin = origin
        return conv

    # --- introspection --------------------------------------------------------
    @property
    def model_version(self) -> str | None:
        return None if self.disambiguator is None else self.disambiguator.version

    def is_ambiguous(self, word: str) -> bool:
        return any(t.search(word) for t in self._triggers)

    def citation_for(self, rule_id: str | None) -> str | None:
        """Why the rewrite that ``rule_id`` names is permissible.

        ``rule_id`` may name several rules joined with ``+`` — the cascade composes them
        — in which case the citations are joined too, in firing order, without repeats.
        """
        try:
            return self._citations[rule_id]
        except KeyError:
            pass
        assert rule_id is not None
        found: list[str] = []
        for part in rule_id.split("+"):
            citation = PSEUDO_RULE_CITATIONS.get(part) or self.engine.citation_for(part)
            if citation and citation not in found:
                found.append(citation)
        result = "; ".join(found) or None
        self._citations[rule_id] = result
        return result

    # --- text-level API -------------------------------------------------------
    def convert(
        self,
        text: str,
        direction: Orthography,
        *,
        aggressive: bool | None = None,
        unresolved: bool = False,
    ) -> ConversionResult:
        """``unresolved`` is off by default: measured on the dev parallel corpus, the
        heuristic behind it flags a possible miss at 12-15% of all tokens for a
        precision of 2-15% (see README, "Unresolved: measured, not guessed") — far
        short of the 0.5 precision / 2% rate bar for shipping it unconditionally.
        Pass ``unresolved=True`` to compute it anyway (the future ``?unresolved=true``
        API flag)."""
        if aggressive is not None and aggressive != self.aggressive:
            return self.variant(aggressive).convert(text, direction, unresolved=unresolved)
        text = sanitize(text)
        tokens = tokenize(text)
        conversions: list[Conversion | None] = []
        out: list[str] = []
        words: list[tuple[int, int]] = []  # (token index, conversion index)
        # Words the deterministic stages could not resolve are batched through
        # the classifier once per call: one predict_proba, not one per word.
        pending: list[tuple[int, int, Token, list[Token]]] = []
        # The neighbouring-word context exists only to featurise a word for the
        # classifier. With no classifier loaded — the default — building it for every
        # token is the single largest cost in the hot path and is thrown away.
        wants_context = self.disambiguator is not None
        for i, tok in enumerate(tokens):
            if tok.kind is not TokenKind.WORD:
                out.append(tok.text)
                continue
            ctx = context_of(tokens, i) if wants_context else _NO_CONTEXT
            # The neighbouring words are read only by the clitic rules (не/без/з) and by
            # the case-dependent lexicon. Both are keyed on the word itself, so scanning
            # for neighbours around every token is work thrown away for all but a few.
            lw = tok.text.lower()
            if lw in self._context_sensitive or lw in self.case_forms:
                following, preceding = next_word(tokens, i), previous_word(tokens, i)
            else:
                following = preceding = None
            conv = self._cascade(tok, ctx, following, direction, preceding, lw)
            if conv is None:
                pending.append((len(conversions), i, tok, ctx))
            words.append((i, len(conversions)))
            conversions.append(conv)
            out.append(tok.text if conv is None else conv.target)
        if pending:
            assert self.disambiguator is not None
            preds = self.disambiguator.predict_batch([(tok, ctx) for _, _, tok, ctx in pending])
            for (ci, ti, tok, _), (pred, score) in zip(pending, preds, strict=True):
                conv = self._from_prediction(tok, pred, score, direction)
                conversions[ci] = conv
                out[ti] = conv.target
        for ti, new in self._optional_conjunctions(tokens, out, direction):
            ci = next(c for t, c in words if t == ti)
            out[ti] = new
            conversions[ci] = Conversion(
                tokens[ti].text,
                new,
                Method.RULE,
                CONJ_RULE_ID,
                citation=self.citation_for(CONJ_RULE_ID),
            )
        for ti, new in self._initial_u(tokens, out, direction):
            ci = next(c for t, c in words if t == ti)
            out[ti] = new
            conversions[ci] = Conversion(
                tokens[ti].text,
                new,
                Method.RULE,
                INITIAL_W_RULE_ID,
                citation=self.citation_for(INITIAL_W_RULE_ID),
            )
        done = [c for c in conversions if c is not None]
        stats: dict[Method, int] = dict.fromkeys(Method, 0)
        for c in done:
            stats[c.method] += 1
        spanned = self._with_output_spans(tokens, out, words, conversions, direction)
        unresolved_words = (
            tuple(
                c.source
                for c in spanned
                if c.method is Method.UNKNOWN
                and not c.changed
                and self.is_ambiguous(c.source.lower())
            )
            if unresolved
            else ()
        )
        return ConversionResult(
            "".join(out), spanned, stats, direction=direction, unresolved=unresolved_words
        )

    @staticmethod
    def _with_output_spans(
        tokens: Sequence[Token],
        out: Sequence[str],
        words: Sequence[tuple[int, int]],
        conversions: Sequence[Conversion | None],
        direction: Orthography,
    ) -> tuple[Conversion, ...]:
        """Give every conversion its span in the **output** text, in code points.

        The output rather than the input because that is the string the caller has in
        hand, and a rule that changes a word's length makes the input offsets
        unrecoverable from it. Code points because ``len`` on a Python ``str`` counts
        those; a JS port converts at its own boundary (see docs/API.md).

        Computed here, once, from the same ``out`` list the text is joined from, so the
        spans cannot drift from the string they index into.
        """
        starts: list[int] = []
        cursor = 0
        for piece in out:
            starts.append(cursor)
            cursor += len(piece)
        spanned: list[Conversion] = []
        for token_index, conversion_index in words:
            conv = conversions[conversion_index]
            if conv is None:  # pragma: no cover - the classifier pass fills these in
                continue
            start = starts[token_index]
            spanned.append(
                replace(
                    conv,
                    start=start,
                    end=start + len(out[token_index]),
                    context=_context_for(conv, tokens, token_index, direction),
                )
            )
        return tuple(spanned)

    def convert_word(
        self,
        word: str,
        direction: Orthography,
        context: Sequence[Token] = (),
        *,
        aggressive: bool | None = None,
    ) -> Conversion:
        """Convert one word.

        ``context`` tokens positioned after the word count as its right context.
        """
        if aggressive is not None and aggressive != self.aggressive:
            return self.variant(aggressive).convert_word(word, direction, context)
        word = sanitize(word)
        token = Token(word, 0, len(word), TokenKind.WORD)
        right = [t for t in context if t.kind is TokenKind.WORD and t.start >= token.end]
        return self._convert_token(token, context, right[0] if right else None, direction)

    def explain(
        self, text: str, direction: Orthography, *, aggressive: bool | None = None
    ) -> list[TokenExplanation]:
        """A **view** over :meth:`convert`, not a second pass over the text.

        Every conversion decision — which stage resolved the word, which rules fired,
        the citation, the offset — is already made and recorded by ``convert``, because
        the cascade cannot convert a word without making it. All this adds is the
        per-rule trace: the intermediate forms a word passed through on its way to the
        answer, which nothing but an explanation needs.

        Keeping these as one code path is the point. When they were two, they could
        disagree, and an explanation that disagrees with the conversion it explains is
        worse than no explanation.
        """
        if aggressive is not None and aggressive != self.aggressive:
            return self.variant(aggressive).explain(text, direction)
        conversions = self.convert(text, direction).conversions
        # The conversions are exactly the word tokens, in order, so the next word is the
        # next conversion — no need to tokenize the text a second time to find it.
        return [
            self._explanation_for(
                conv,
                direction,
                conversions[i + 1].source if i + 1 < len(conversions) else None,
            )
            for i, conv in enumerate(conversions)
        ]

    def _explanation_for(
        self, conv: Conversion, direction: Orthography, following: str | None
    ) -> TokenExplanation:
        """One conversion, plus the trace of how it got there."""
        lw = conv.source.lower()
        traces: tuple[RuleTrace, ...] = ()
        if conv.rule_id == CONJ_RULE_ID:
            traces = (RuleTrace(CONJ_RULE_ID, conv.source, conv.target),)
        elif conv.method in (Method.RULE, Method.MODEL):
            traces = self._traces_for(lw, conv, direction, following)
        elif conv.rule_id == CASE_RULE_ID:
            traces = (RuleTrace(CASE_RULE_ID, lw, conv.target.lower()),)
        return TokenExplanation(
            conv.source, conv.target, conv.method, conv.rule_id, conv.confidence, traces
        )

    def _optional_conjunctions(
        self, tokens: Sequence[Token], out: Sequence[str], direction: Orthography
    ) -> list[tuple[int, str]]:
        """Aggressive mode only: і → й after a word ending in a vowel (Збор 2005, §13).

        ``out`` holds each token's converted text. Only whitespace may separate the two
        words; after punctuation the conjunction stays і, as §13 requires.
        """
        if not self.aggressive or direction is not Orthography.TARASKIEVICA:
            return []
        changes: list[tuple[int, str]] = []
        prev: int | None = None
        for i, tok in enumerate(tokens):
            if tok.kind is TokenKind.WORD:
                if prev is not None and all(bridges_words(tokens, j) for j in range(prev + 1, i)):
                    new = conjunction_i_to_j(tok.text, out[prev])
                    if new is not None:
                        changes.append((i, new))
                        out = [*out[:i], new, *out[i + 1 :]]
                prev = i
            elif not bridges_words(tokens, i):
                prev = None
        return changes

    def _initial_u(
        self, tokens: Sequence[Token], out: Sequence[str], direction: Orthography
    ) -> list[tuple[int, str]]:
        """Збор 2005 §18 forward; Правілы 2008 §15 п.4 back.

        The two directions are not mirror images. §18 makes У → Ў *conditional* — after
        a vowel, unstressed, capitalised. §15 п.4 makes the reverse *unconditional*:
        Narkamaŭka never starts a proper name with Ў, whatever precedes it. Each side
        of the converter answers to its own codification, and here the two codifications
        genuinely differ in shape, not just in spelling.

        A post-pass rather than a rule in the engine, because it needs the *previous*
        word as it will finally be written — and the same shape as the §13 conjunction
        rule next to it, including its §18 Заўвага: a hyphen or a quotation mark is not
        a punctuation mark and does not break the run (`Кука-Ўітсан`).

        Not gated behind ``aggressive``. §13 says the conjunction *may* become й; §18
        says У *is* written Ў, and the reverse direction has no optionality either.
        """
        changes: list[tuple[int, str]] = []
        prev: int | None = None
        for i, tok in enumerate(tokens):
            if tok.kind is TokenKind.WORD:
                if direction is Orthography.NARKAMAUKA:
                    # Правілы 2008 §15 п.4 is categorical, so unlike the forward rule
                    # this one does not care what came before: a capital word-initial
                    # Ў is written У wherever it stands.
                    new = initial_w_to_u(out[i])
                    if new is not None:
                        changes.append((i, new))
                        out = [*out[:i], new, *out[i + 1 :]]
                elif prev is not None and all(bridges_words(tokens, j) for j in range(prev + 1, i)):
                    new = initial_u_to_w(out[i], out[prev], self.stress, self.function_words)
                    if new is not None:
                        changes.append((i, new))
                        out = [*out[:i], new, *out[i + 1 :]]
                prev = i
            elif not bridges_words(tokens, i):
                prev = None
        return changes

    # --- the cascade ----------------------------------------------------------
    def _convert_token(
        self,
        token: Token,
        context: Sequence[Token],
        following: Token | None,
        direction: Orthography,
        preceding: Token | None = None,
    ) -> Conversion:
        """Full cascade for one token, including a single-word model call."""
        conv = self._cascade(token, context, following, direction, preceding)
        if conv is not None:
            return conv
        assert self.disambiguator is not None
        predicted, score = self.disambiguator.predict(token, context)
        return self._from_prediction(token, predicted, score, direction)

    def _from_prediction(
        self, token: Token, predicted: str, score: float, direction: Orthography
    ) -> Conversion:
        source = token.text
        lw = source.lower()
        assert self.disambiguator is not None
        if predicted != lw and self.disambiguator.is_confident(score):
            final, ids = self.engine.apply(predicted, direction)
            rule_id = "+".join(ids) or None
            return Conversion(
                source,
                recase(source, final),
                Method.MODEL,
                rule_id,
                score,
                citation=self.citation_for(rule_id),
            )
        return Conversion(source, source, Method.UNKNOWN)

    def _cascade(
        self,
        token: Token,
        context: Sequence[Token],
        following: Token | None,
        direction: Orthography,
        preceding: Token | None = None,
        lw: str | None = None,
    ) -> Conversion | None:
        """Steps 1-3 and 5 of the cascade; None means "ask the classifier" (step 4).

        Context-free words are memoised per (word, direction): under a Zipfian
        text most tokens are repeats, so this turns the rule engine into a
        dictionary lookup for the bulk of the input.
        """
        source = token.text
        if not is_belarusian_word(token):
            return Conversion(source, source, Method.UNKNOWN)
        if lw is None:
            lw = source.lower()
        if direction is Orthography.TARASKIEVICA and lw in self.case_forms:
            # One form, several cases, different Taraškievica endings: the preposition
            # before it decides (Германіі → Нямеччыны / у Нямеччыне).
            choice = self.case_forms.choose(lw, preceding.text if preceding else None)
            assert choice is not None
            return Conversion(
                source,
                _recase_like(source, lw, choice[0]),
                Method.LEXICON,
                CASE_RULE_ID,
                citation=self.citation_for(CASE_RULE_ID),
            )
        if lw in self._context_sensitive:
            resolved = self._resolve_clitic(lw, following.text if following else None, direction)
        else:
            resolved = self._resolve_cached(lw, direction)
        if resolved is None:
            return None
        target, method, rule_id = resolved
        return Conversion(
            source,
            _recase_like(source, lw, target),
            method,
            rule_id,
            citation=self.citation_for(rule_id),
        )

    def _lookup(self, lw: str, direction: Orthography) -> Resolved | None:
        """Steps 1 and 2: identity set, then lexicon."""
        if self.lexicon.is_identity(lw):
            return (lw, Method.IDENTITY, None)
        hit = self.lexicon.lookup(lw, direction)
        if hit is not None:
            return (hit, Method.LEXICON, None)
        return None

    def _wants_model(self, lw: str, direction: Orthography) -> bool:
        return (
            self.disambiguator is not None
            and direction is self.disambiguator.direction
            and self.is_ambiguous(lw)
        )

    def _resolve(self, lw: str, direction: Orthography) -> Resolved | None:
        head = self._lookup(lw, direction)
        if head is not None:
            return head
        if "-" in lw:
            return self._resolve_hyphenated(lw, direction)
        # 3. rules
        work, ids = self.engine.apply(lw, direction)
        # 3b. The -мент suffix is written -мэнт when the word's *base noun* is a -мент
        #     noun, and the э is inherited by everything derived from it even after the
        #     stress moves: манумэнт → манумэнтальны, дакумэнт → дакумэнтацыя. No stem
        #     rule sees that, so it runs here, against the word as it arrived, and after
        #     the engine so парламент → парлямент → парлямэнт composes.
        before_ment = work
        if direction is Orthography.TARASKIEVICA:
            if self.ment_suffix.applies(lw):
                work = MentSuffix.to_hard(work)
        else:
            work = MentSuffix.to_soft(work)
        if work != before_ment:
            ids = [*ids, MENT_RULE_ID]
        if work != lw:
            return (work, Method.RULE, "+".join(ids))
        # 4. model, deferred to the caller so text-level conversion can batch it
        if self._wants_model(lw, direction):
            return None
        # 5. passthrough
        return (lw, Method.UNKNOWN, None)

    def _resolve_cached(self, lw: str, direction: Orthography) -> Resolved | None:
        key = (lw, direction)
        try:
            return self._cache[key]
        except KeyError:
            pass
        if len(self._cache) >= CACHE_LIMIT:
            self._cache.clear()
        result = self._resolve(lw, direction)
        self._cache[key] = result
        return result

    def _resolve_clitic(
        self, lw: str, following: str | None, direction: Orthography
    ) -> Resolved | None:
        """Same cascade, but step 3 starts with the next-word-dependent clitic rule."""
        head = self._lookup(lw, direction)
        if head is not None:
            return head
        fired: list[str] = []
        work = lw
        particle = convert_particle(
            lw,
            following,
            direction,
            self.stress,
            self._next_target(following, direction),
            self.function_words,
        )
        if particle is not None and particle != lw:
            work = particle
            fired.append(PARTICLE_RULE_ID)
        work, ids = self.engine.apply(work, direction)
        fired.extend(ids)
        if work != lw:
            return (work, Method.RULE, "+".join(fired))
        if self._wants_model(lw, direction):
            return None
        return (lw, Method.UNKNOWN, None)

    def _next_target(self, following: str | None, direction: Orthography) -> str | None:
        """The following word in the *target* orthography, converted without context.

        A clitic's soft-onset condition must read the next word as it will be
        written in the output, where softness is marked (слёз → сьлёз). A next
        word that is itself a clitic gets only the context-free rules.
        """
        if following is None or direction is not Orthography.TARASKIEVICA:
            return None
        lw = following.lower()
        if lw in self._context_sensitive:
            return self.engine.apply(lw, direction)[0]
        resolved = self._resolve_cached(lw, direction)
        return lw if resolved is None else resolved[0]

    def _resolve_hyphenated(self, lw: str, direction: Orthography) -> Resolved:
        """Each part goes through the cascade; parts never consult the classifier."""
        parts = lw.split("-")
        resolved: list[Resolved] = []
        for part in parts:
            r = self._resolve_cached(part, direction) if part else (part, Method.IDENTITY, None)
            resolved.append((part, Method.UNKNOWN, None) if r is None else r)
        target = "-".join(r[0] for r in resolved)
        changed = [r for part, r in zip(parts, resolved, strict=True) if r[0] != part]
        if changed:
            best = max(changed, key=lambda r: METHOD_PRIORITY[r[1]])
            rule_ids = [r[2] for r in changed if r[2]]
            return (target, best[1], "+".join(rule_ids) or None)
        if all(r[1] is Method.IDENTITY for r in resolved if r[0]):
            return (lw, Method.IDENTITY, None)
        return (lw, Method.UNKNOWN, None)

    def _traces_for(
        self, lw: str, conv: Conversion, direction: Orthography, following: str | None
    ) -> tuple[RuleTrace, ...]:
        traces: list[RuleTrace] = []
        work = lw
        if conv.method is Method.RULE:
            nxt = following
            particle = convert_particle(
                lw, nxt, direction, self.stress, self._next_target(nxt, direction)
            )
            if particle is not None and particle != lw:
                traces.append(RuleTrace(PARTICLE_RULE_ID, lw, particle))
                work = particle
        elif conv.method is Method.MODEL and self.disambiguator is not None:
            token = Token(lw, 0, len(lw), TokenKind.WORD)
            label, score = self.disambiguator.predict_label(token, ())
            predicted, _ = self.disambiguator.predict(token, ())
            traces.append(RuleTrace(f"model:{label}@{score:.2f}", lw, predicted))
            work = predicted
        traces.extend(self.engine.explain(work, direction))
        return tuple(traces)


# --- module-level convenience ---------------------------------------------------
@lru_cache(maxsize=1)
def default_converter() -> Converter:
    """A process-wide converter built from the default data directory (built once)."""
    return Converter.from_config()


def parse_options(options: Mapping[str, str]) -> Orthography:
    """``{"from": …, "to": …}`` → the direction to convert in.

    ``to`` is required. ``from`` is optional — there are exactly two orthographies, so
    omitting it means "the other one" — but when given it must be the other one, because
    a caller who says ``from`` and ``to`` has stated an expectation, and silently
    converting in a direction they did not ask for is how a caller ends up shipping
    text they never checked.
    """
    if "to" not in options:
        raise ValueError("convert() needs a 'to' orthography in its options")
    try:
        to = Orthography(options["to"])
    except ValueError as exc:
        raise ValueError(
            f"unknown orthography {options['to']!r}; expected one of "
            f"{[o.value for o in Orthography]}"
        ) from exc
    unknown = set(options) - {"from", "to"}
    if unknown:
        raise ValueError(f"unknown option(s) {sorted(unknown)}; expected 'from' and 'to'")
    if "from" in options:
        try:
            source = Orthography(options["from"])
        except ValueError as exc:
            raise ValueError(
                f"unknown orthography {options['from']!r}; expected one of "
                f"{[o.value for o in Orthography]}"
            ) from exc
        if source is to:
            raise ValueError(f"'from' and 'to' are both {to.value}; there is nothing to convert")
    return to


@overload
def convert(text: str, options: Orthography, *, aggressive: bool = False) -> str: ...


@overload
def convert(
    text: str, options: Mapping[str, str], *, aggressive: bool = False
) -> ConversionResult: ...


def convert(
    text: str, options: Orthography | Mapping[str, str], *, aggressive: bool = False
) -> str | ConversionResult:
    """Convert ``text`` between the two orthographies.

    The frozen public form takes an options mapping and returns the full result::

        >>> convert("снег", {"from": "narkamauka", "to": "taraskievica"}).to_dict()
        {'text': 'сьнег', 'changes': [{'from': 'снег', 'to': 'сьнег', 'offset': 0,
         'rule': 'palat.assim', 'class': 'rule', 'citation': 'Збор 2005, §29'}]}

    That shape — ``convert(text, {from, to}) → {text, changes}`` — is the contract, and
    it is the same in every implementation of pravapis. ``changes`` is always present:
    see :class:`~pravapis.types.ConversionResult`.

    Passing an :class:`~pravapis.types.Orthography` instead returns just the converted
    string. It is the older, narrower form, kept because it reads well at a REPL and in
    a one-line script; new callers should prefer the options form, which can tell them
    what it did.
    """
    if isinstance(options, Orthography):
        return default_converter().convert(text, options, aggressive=aggressive).text
    return default_converter().convert(text, parse_options(options), aggressive=aggressive)
