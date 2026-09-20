# pravapis — open questions for a native reviewer

Every question below is one where the project cannot settle the answer from the sources it
has. They are ordered by how much they affect the measured numbers.

**How to answer:** write the correct form next to each item, or "leave as is". Where a
question offers two spellings, either may be right — the point is which one Belarusian
actually uses, not which one a rule predicts.

No knowledge of the code is needed.


## 1. The converter and the gold set disagree

None — the two files agree.


## 2. Words held back for want of a source


## 3. Two cited sections pointing different ways

    - **эўрапейскі or эўрапэйскі?** §52 gives еў → эў; §11б gives е → э after a consonant. Applying both gives эўрапэйскі, which is what be-tarask writes; the project's codification test expects эўрапейскі. Which is used?
    - **мадрыдзкі or мадрыдскі?** The corpus writes мадрыдзкі; no section was found licensing дз before с here. Is мадрыдзкі right, and does it generalise (бэрлінскі/бэрлінзкі, лёнданскі/лёнданзкі)?
    - **Genitive plural -аў**: хвілін or хвілінаў, краін or краінаў? The project converts краінаў only, on instruction, and leaves every other noun alone. Is -аў general, or does it depend on the noun?
    - **Softness across a hyphen**: §29 limits assimilative softness to "у межах слова". In a compound like сьвятлова-зялёны, does the softness of the first part carry?


## 4. Is the gold set trustworthy at all?

The 150 Taraškievica sentences in `data/eval/tarask/gold_t2n.tsv` come from be-tarask.wikipedia.org, so they are genuine. Their Narkamaŭka counterparts were drafted by the converter and corrected by hand. **A spot-check of ten rows** — do they read as ordinary Narkamaŭka? — would say more about the headline accuracy figure than any other single answer here.

