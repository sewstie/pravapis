# data/morphology — genitive-plural tables

Built by `scripts/build_morphology.py` from the verified GrammarDB release recorded
in `SOURCE` (release tag and SHA-256 of the zip).

| File | Content |
|---|---|
| `ment_lemmas.marisa` | the 116 GrammarDB noun lemmas ending in -мент |
| `SOURCE` | release, checksum and count |

Used by `loan.ment_suffix` (`src/pravapis/morphology.py`). Taraškievica writes the suffix
-мэнт when the base noun carries the stress on it, and the э is inherited by everything
derived from that base even after the stress moves: манумэ́нт → манумэнта́льны, дакумэ́нт →
дакумэнта́цыя. So the fact stored is the base noun, not a per-form stress mark — a first
attempt used GrammarDB's per-form stress and got exactly those derived words wrong.

The bare colloquial noun *мент* is excluded, or any word starting мент- would match and
drag in *ментальны*, which is not derived from a -мент noun.

Three further tries lived here for the genitive plural in -аў. That rule was replaced by a
whitelist in `data/lexicon/exceptions.tsv`, which took 752 KiB out of the payload.

## Licence and attribution

Derived from the **Belarusian Grammar Database (GrammarDB)** by **Aleś Bułojčyk** and
**Uładzimir Koščanka**, https://github.com/Belarus/GrammarDB, licensed
**CC BY-SA 4.0**. Changes: reduced to three membership tables, stress marks removed,
lemmas restricted to those ending in а/я. Distributed under the same licence.
