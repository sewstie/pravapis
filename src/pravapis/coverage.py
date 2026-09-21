"""Lexicon and stem coverage over a frequency list: what the converter can even see.

Recall says what the converter missed on the sentences that happened to align. Coverage
asks a blunter question with no sampling in it: of the word forms Belarusian text is
actually made of, how many does the converter have any knowledge about?

The number to be careful with is **stem coverage**, because a low figure is not in
itself a failure. Stems exist to gate the loanword rules: they answer "is this a Western
borrowing", which is the one fact the spelling cannot supply. Native vocabulary needs no
stem, and most word forms in any Belarusian text are native. A stem coverage of 4% is
therefore compatible with a converter that is entirely correct — and also with one that
is blind to half the loanwords in the language. The figures that separate those two cases
are reported alongside it:

``stem``        forms the stem inventory resolves (split loan / native)
``lexicon``     forms with an explicit lexicon entry
``rule``        forms no stem or lexicon covers that a rule changes anyway — almost all
                assimilative softness, which is phonological and needs no etymology
``untouched``   forms nothing covers and nothing changes

Each is reported twice: by **type** (share of the distinct forms) and by **token** (share
weighted by how often the form occurs). Type coverage describes the vocabulary; token
coverage describes the text a user will paste in. They differ a lot, and quoting only the
flattering one is the easiest mistake here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pravapis.lexicon.stems import WordClass
from pravapis.pipeline import Converter
from pravapis.types import Orthography


@dataclass(frozen=True, slots=True)
class Bucket:
    types: int = 0
    tokens: int = 0

    def add(self, count: int) -> Bucket:
        return Bucket(self.types + 1, self.tokens + count)


@dataclass(frozen=True, slots=True)
class CoverageReport:
    forms: int
    occurrences: int
    stem_loan: Bucket
    stem_native: Bucket
    lexicon: Bucket
    rule: Bucket
    untouched: Bucket

    @property
    def stem(self) -> Bucket:
        return Bucket(
            self.stem_loan.types + self.stem_native.types,
            self.stem_loan.tokens + self.stem_native.tokens,
        )

    def share(self, bucket: Bucket) -> tuple[float, float]:
        """``(type share, token share)`` for one bucket."""
        return (
            bucket.types / self.forms if self.forms else 0.0,
            bucket.tokens / self.occurrences if self.occurrences else 0.0,
        )


def read_frequency_list(path: Path, limit: int | None = None) -> list[tuple[str, int]]:
    """``form<TAB>count`` rows, most frequent first; ``#`` comments skipped."""
    out: list[tuple[str, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        out.append((parts[0], int(parts[1])))
        if limit is not None and len(out) >= limit:
            break
    return out


def measure_coverage(
    forms: list[tuple[str, int]],
    converter: Converter,
    direction: Orthography = Orthography.TARASKIEVICA,
) -> CoverageReport:
    """Classify each form by the most specific thing the converter knows about it."""
    stem_loan = stem_native = lexicon = rule = untouched = Bucket()
    occurrences = 0
    for form, count in forms:
        occurrences += count
        word = form.lower()
        match = converter.engine.stem_match(word, direction)
        if match is not None:
            if match.cls is WordClass.LOAN:
                stem_loan = stem_loan.add(count)
            else:
                stem_native = stem_native.add(count)
            continue
        if converter.lexicon.lookup(word, direction) is not None:
            lexicon = lexicon.add(count)
            continue
        if converter.engine.apply(word, direction)[0] != word:
            rule = rule.add(count)
            continue
        untouched = untouched.add(count)
    return CoverageReport(
        forms=len(forms),
        occurrences=occurrences,
        stem_loan=stem_loan,
        stem_native=stem_native,
        lexicon=lexicon,
        rule=rule,
        untouched=untouched,
    )
