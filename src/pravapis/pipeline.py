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
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

import regex

from pravapis.casing import recase
from pravapis.config import DEFAULT_AMBIGUITY_TRIGGERS, Config
from pravapis.lexicon.builder import StaleLexiconError
from pravapis.lexicon.case_forms import CASE_RULE_ID, CaseForms
from pravapis.lexicon.store import Lexicon
from pravapis.normalize import sanitize
from pravapis.rules.engine import RuleEngine
from pravapis.rules.loanwords import build_stem_indexes
from pravapis.rules.morphology import (
    CONJ_RULE_ID,
    PARTICLES_N2T,
    PARTICLES_T2N,
    SOFTENING_PREPOSITIONS,
    conjunction_i_to_j,
    convert_particle,
)
from pravapis.stress import StressTable
from pravapis.tokenize import context_of, is_belarusian_word, next_word, previous_word, tokenize
from pravapis.translit import PAIRED, REVERSIBLE, Transliterator
from pravapis.translit.engine import TransliterationResult
from pravapis.types import (
    METHOD_PRIORITY,
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

#: Words whose conversion depends on the next word; never memoised.
CONTEXT_SENSITIVE: Final[frozenset[str]] = (
    frozenset(PARTICLES_N2T) | frozenset(PARTICLES_T2N) | SOFTENING_PREPOSITIONS
)

#: (lowercase target, method, rule ids) for a context-free word.
Resolved = tuple[str, Method, str | None]


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
        triggers = config.ambiguity_triggers if config else DEFAULT_AMBIGUITY_TRIGGERS
        self._triggers: tuple[regex.Pattern[str], ...] = tuple(regex.compile(t) for t in triggers)
        self._cache: dict[tuple[str, Orthography], Resolved | None] = {}
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
        case_forms = (
            CaseForms.load(config.case_forms)
            if config.case_forms is not None and config.case_forms.exists()
            else None
        )
        conv = cls(lexicon, engine, disambiguator, config, stress, case_forms=case_forms)
        conv.lexicon_origin = origin
        return conv

    # --- introspection --------------------------------------------------------
    @property
    def model_version(self) -> str | None:
        return None if self.disambiguator is None else self.disambiguator.version

    def is_ambiguous(self, word: str) -> bool:
        return any(t.search(word) for t in self._triggers)

    # --- text-level API -------------------------------------------------------
    def convert(
        self, text: str, direction: Orthography, *, aggressive: bool | None = None
    ) -> ConversionResult:
        if aggressive is not None and aggressive != self.aggressive:
            return self.variant(aggressive).convert(text, direction)
        text = sanitize(text)
        tokens = tokenize(text)
        conversions: list[Conversion | None] = []
        out: list[str] = []
        words: list[tuple[int, int]] = []  # (token index, conversion index)
        # Words the deterministic stages could not resolve are batched through
        # the classifier once per call: one predict_proba, not one per word.
        pending: list[tuple[int, int, Token, list[Token]]] = []
        for i, tok in enumerate(tokens):
            if tok.kind is not TokenKind.WORD:
                out.append(tok.text)
                continue
            ctx = context_of(tokens, i)
            conv = self._cascade(
                tok, ctx, next_word(tokens, i), direction, previous_word(tokens, i)
            )
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
            conversions[ci] = Conversion(tokens[ti].text, new, Method.RULE, CONJ_RULE_ID)
        done = [c for c in conversions if c is not None]
        stats: dict[Method, int] = dict.fromkeys(Method, 0)
        for c in done:
            stats[c.method] += 1
        return ConversionResult("".join(out), tuple(done), stats)

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
        if aggressive is not None and aggressive != self.aggressive:
            return self.variant(aggressive).explain(text, direction)
        text = sanitize(text)
        tokens = tokenize(text)
        explanations: list[TokenExplanation] = []
        out = [t.text for t in tokens]
        index: dict[int, int] = {}  # token index -> explanation index
        for i, tok in enumerate(tokens):
            if tok.kind is not TokenKind.WORD:
                continue
            conv = self._convert_token(
                tok,
                context_of(tokens, i),
                next_word(tokens, i),
                direction,
                previous_word(tokens, i),
            )
            traces: tuple[RuleTrace, ...] = ()
            if conv.method in (Method.RULE, Method.MODEL):
                traces = self._traces_for(tok.text.lower(), conv, direction, next_word(tokens, i))
            elif conv.rule_id == CASE_RULE_ID:
                traces = (RuleTrace(CASE_RULE_ID, tok.text.lower(), conv.target.lower()),)
            index[i] = len(explanations)
            out[i] = conv.target
            explanations.append(
                TokenExplanation(
                    conv.source, conv.target, conv.method, conv.rule_id, conv.confidence, traces
                )
            )
        for ti, new in self._optional_conjunctions(tokens, out, direction):
            src = tokens[ti].text
            explanations[index[ti]] = TokenExplanation(
                src, new, Method.RULE, CONJ_RULE_ID, 1.0, (RuleTrace(CONJ_RULE_ID, src, new),)
            )
        return explanations

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
                if prev is not None and all(
                    tokens[j].kind is TokenKind.SPACE for j in range(prev + 1, i)
                ):
                    new = conjunction_i_to_j(tok.text, out[prev])
                    if new is not None:
                        changes.append((i, new))
                        out = [*out[:i], new, *out[i + 1 :]]
                prev = i
            elif tok.kind is not TokenKind.SPACE:
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
            return Conversion(
                source, recase(source, final), Method.MODEL, "+".join(ids) or None, score
            )
        return Conversion(source, source, Method.UNKNOWN)

    def _cascade(
        self,
        token: Token,
        context: Sequence[Token],
        following: Token | None,
        direction: Orthography,
        preceding: Token | None = None,
    ) -> Conversion | None:
        """Steps 1-3 and 5 of the cascade; None means "ask the classifier" (step 4).

        Context-free words are memoised per (word, direction): under a Zipfian
        text most tokens are repeats, so this turns the rule engine into a
        dictionary lookup for the bulk of the input.
        """
        source = token.text
        if not is_belarusian_word(token):
            return Conversion(source, source, Method.UNKNOWN)
        lw = source.lower()
        if direction is Orthography.TARASKIEVICA and lw in self.case_forms:
            # One form, several cases, different Taraškievica endings: the preposition
            # before it decides (Германіі → Нямеччыны / у Нямеччыне).
            choice = self.case_forms.choose(lw, preceding.text if preceding else None)
            assert choice is not None
            return Conversion(
                source, _recase_like(source, lw, choice[0]), Method.LEXICON, CASE_RULE_ID
            )
        if lw in CONTEXT_SENSITIVE:
            resolved = self._resolve_clitic(lw, following.text if following else None, direction)
        else:
            resolved = self._resolve_cached(lw, direction)
        if resolved is None:
            return None
        target, method, rule_id = resolved
        return Conversion(source, _recase_like(source, lw, target), method, rule_id)

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
            lw, following, direction, self.stress, self._next_target(following, direction)
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
        if lw in CONTEXT_SENSITIVE:
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
        self, lw: str, conv: Conversion, direction: Orthography, following: Token | None
    ) -> tuple[RuleTrace, ...]:
        traces: list[RuleTrace] = []
        work = lw
        if conv.method is Method.RULE:
            nxt = following.text if following else None
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


def convert(text: str, direction: Orthography, *, aggressive: bool = False) -> str:
    return default_converter().convert(text, direction, aggressive=aggressive).text
