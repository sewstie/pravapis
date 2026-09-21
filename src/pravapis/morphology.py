"""Morphological facts the spelling rules cannot see, read from GrammarDB paradigms.

So far one: the *-мент* suffix, whose э belongs to the base noun and is inherited by
everything derived from it.

The genitive plural in -аў lived here too, table-driven from every GrammarDB noun. It was
replaced by a whitelist in ``data/lexicon/exceptions.tsv``. Taraškievica extends -аў to
feminine and neuter nouns in a vowel — this is *not* Збор 2005 §80, which is the German
*ei* rule; the 2005 code is a spelling code and does not legislate declension — but for
many words *both* forms are permissible — хвілін and
хвілінаў are equally valid — so a rule that fires on all of them corrupts ordinary text.
Six nouns where -аў is strongly preferred are listed; everything else is left alone. That
also took 752 KiB of tries out of the deployment payload.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import marisa_trie

MENT_RULE_ID: Final[str] = "loan.ment_suffix"


class MentSuffix:
    """The *-мент* suffix, which Taraškievica writes *-мэнт*.

    The suffix takes э when the base noun carries the stress on it — дакумэ́нт,
    аргумэ́нт, парлямэ́нт — and, crucially, **the э is inherited by everything derived
    from that base even after the stress moves**: манумэ́нт → манумэнта́льны, дакумэ́нт →
    дакумэнта́цыя, інструмэ́нт → інструмэнта́льны. The stem is what is preserved, not the
    stress of the word in hand.

    So the fact to store is the base noun, not a per-form stress mark. A first attempt
    used GrammarDB's stress on each form and got *дакументацыя* and *манументальны*
    wrong; those are precisely the derived words where the stress has moved but the stem
    has not. GrammarDB also marks *парламент* as stressed on -ла́-, while Taraškievica
    writes парлямэ́нт, so its stress is not the right discriminator here either.

    The guard against over-reach is that the word must contain one of these lemmas:
    *ментальны* and *менталітэт* are not derived from a -мент noun and are untouched.

    The reverse needs no table. GrammarDB holds no Narkamaŭka form containing мэнт, so
    Taraškievica мэнт always becomes мент.
    """

    def __init__(self, forms: marisa_trie.Trie):
        self.forms = forms

    @classmethod
    def load(cls, path: Path) -> MentSuffix:
        trie = marisa_trie.Trie()
        trie.load(str(path / "ment_lemmas.marisa"))
        return cls(trie)

    @classmethod
    def empty(cls) -> MentSuffix:
        return cls(marisa_trie.Trie())

    def __len__(self) -> int:
        return len(self.forms)

    def applies(self, narkamauka_form: str) -> bool:
        """Does this word carry a -мент base, and so inherit its э?

        Asked of the word as it *arrived*, never of a partly converted one: by the time
        the soft-л rule has run, парламент is парлямент, which GrammarDB has never seen.
        """
        lw = narkamauka_form.lower()
        if "мент" not in lw:
            return False
        # Every stored lemma ends in -мент, so the base can only be a *suffix* of the
        # text up to and including the first мент: абцэментаваны → абцэмент → цэмент.
        head = lw[: lw.index("мент") + 4]
        return any(head[i:] in self.forms for i in range(len(head) - 3))

    @staticmethod
    def to_hard(word: str) -> str:
        """мент → мэнт, preserving case."""
        return word.replace("мент", "мэнт").replace("МЕНТ", "МЭНТ").replace("Мент", "Мэнт")

    @staticmethod
    def to_soft(word: str) -> str:
        """мэнт → мент, preserving case."""
        return word.replace("мэнт", "мент").replace("МЭНТ", "МЕНТ").replace("Мэнт", "Мент")
