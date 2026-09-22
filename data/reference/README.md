# data/reference — normative sources (not redistributed)

The files here are **git-ignored**: they are copyrighted and no licence to redistribute them
is granted. This README records where they come from so anyone can obtain the same copy.

## Беларускі клясычны правапіс. Збор правілаў. Сучасная нармалізацыя (2005)

Юрась Бушлякоў, Вінцук Вячорка, Зьміцер Санько, Зьміцер Саўка. Вільня–Менск, 2005.
Title page: "© Юрась Бушлякоў, Вінцук Вячорка, Зьміцер Санько, Зьміцер Саўка, тэкст, 2005;
© Зьміцер Саўка, друкаваная вэрсія, 2005". Electronic version "падрыхтаваная для сайтаў
www.svaboda.org і www.pravapis.org"; the authors ask readers to buy the paper edition.

| File | Obtained from | SHA-256 |
|---|---|---|
| `pravapis2005.pdf` (46 pp., rules §1–91 + endnotes) | https://web.archive.org/web/20051224051023/http://pravapis.org:80/pravapis2005.pdf | `974058bc10cf6db380b3a2cd51d3f0417fad2283d18446542817db2f9e90b1fe` |
| `pravapis2005.doc` (same text, Word) | https://web.archive.org/web/20051224051909/http://pravapis.org:80/pravapis2005.doc | `a0114209beb96908dcfdce880523d2eeb73d103051a37a1519269966880f5dbd` |
| `pravapis2005.txt` | text extracted from the PDF with pypdf, whitespace normalised; for search only | — |

pravapis.org itself (download page `download_by.asp`) was not reachable from the build
machine; the Wayback Machine copies above are the files that page linked to.

## Правілы беларускай арфаграфіі і пунктуацыі (2008)

The **Narkamaŭka** side's authority: the rules attached to Закон Рэспублікі Беларусь
№ 420-З «Аб Правілах беларускай арфаграфіі і пунктуацыі», adopted 23 July 2008, in force
from 1 September 2010. The converter has two sides and each is answerable to its own
codification — 2005 for Taraškievica, 2008 for Narkamaŭka. Cite as `Правілы 2008, §N`.

| File | Obtained from | Pinned by |
|---|---|---|
| `pravily2008.txt` (the Law, with the Правілы attached, §1–§60) | be.wikisource.org, page `Закон Рэспублікі Беларусь «Аб Правілах беларускай арфаграфіі і пунктуацыі»` (pageid 12416), **revid 283776** | sha256 `286c03e0c4d92bc6f440ee55c308f8c2ca7d13ed89b6e83b97e0261ca5cc79a0` over the wikitext |

**This is a transcription, not the official act.** pravo.by and etalonline.by — which
publish the authoritative text — were not resolvable from the build machine, and neither
serves a stable hashed artefact to pin against. Wikisource is editable, so the *revision
id is part of the citation*: a § number read off a later revision is a different claim,
and the hash check refuses anything but revid 283776. The page names its own source as
a school's copy of the act. A citation taken from here should be spot-checked against
pravo.by wherever that is reachable, and this table replaced with the official artefact
the moment one can be pinned.

Restored by the same command as the 2005 file:

```
python scripts/fetch_reference.py
```

## What the electronic edition covers — and what it does not

- **Covered:** the rules, §1–91 (артаграмы 1–91), with their notes and the endnotes (i–xliv).
- **Absent:** the spelling dictionaries (артаграфічныя слоўнікі), roughly pp. 92–158 of the
  158-page printed book. The preface says they take up "ці не палову яго аб’ёму".

Consequences for this project:

- Anything settled only by a dictionary entry cannot be verified from these files. In
  particular **ґ in common words (ґанак, ґузік, ґрунт) and the whole `loan.g_distinction`
  stem list cannot be resolved**: the rules mention ґ only for foreign proper names, and only as
  an option (§61).
- The same holds for individual loanword stems not quoted as examples in the rules (e.g.
  лякальны, ляндшафт, балькон, атляс, рэкляма, кілямэтар, калёнія) and for most lexicon entries.
- slounik.org/bkp2005 publishes a dictionary derived from the book (5,123 entries). It has no
  licence and the content is the authors' copyright: private reference only, like these files,
  and not a data source for the lexicon.

## Getting them back

`data/reference/` is git-ignored, so a fresh checkout has none of this. One command
restores it — it downloads from the Wayback URL above, checks the SHA-256 against the
table, and extracts the searchable text:

```
python scripts/fetch_reference.py
```

Text extraction needs `pypdf`, which is deliberately not a project dependency: only this
one script wants it, and nothing in the library, the CLI or CI reads the PDF.

**The book numbers its rules plainly — `18.`, `20.` — not `§18`.** The § is this
project's citation convention. Search the chapter headings (`Разьдзел 6. ПРАВАПІС У – Ў`)
when a rule number is not enough.

Cite rules in `data/NORMS.md` as `Збор правілаў 2005, §N` (e.g. §29 Заўвага А) for the
Taraškievica side, and as `Правілы 2008, §N` for the Narkamaŭka side. The 2008 rules
*do* number themselves `§ 15.`, so there the § is the book's own convention, not this
project's.
