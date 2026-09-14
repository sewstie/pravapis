# data/stress — first-syllable stress table

Built by `scripts/build_stress_table.py` from the verified GrammarDB release
recorded in `SOURCE` (release tag and SHA-256 of the zip).

| File | Content |
|---|---|
| `first_stressed.marisa` | lowercase word forms GrammarDB stresses unambiguously on the first vowel |
| `proper_first_stressed.marisa` | the same for capitalised forms (proper names) |
| `SOURCE` | release, checksum, and counts: forms seen, first-stressed, stressed elsewhere, homographs with different stresses, forms with several stress marks |

Used by the не/без → ня/бяз rule (`morph.particle`, see `data/NORMS.md`).

## Licence and attribution

Derived from the **Belarusian Grammar Database (GrammarDB)** by **Aleś Bułojčyk** and
**Uładzimir Koščanka**, https://github.com/Belarus/GrammarDB, licensed under
**Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**,
https://creativecommons.org/licenses/by-sa/4.0/.

Changes: stress marks reduced to a yes/no "stressed on the first syllable" fact per word form;
homographs and multi-stress forms dropped. This derived table is distributed under the same
licence, CC BY-SA 4.0.
