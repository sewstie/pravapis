# What to review, and how to check it

## Running the commands (Windows / PowerShell)

Activate the virtualenv once per terminal, then `pravapis` works bare:

```powershell
.\.venv\Scripts\Activate.ps1
pravapis audit data/eval/tarask/corpus.tsv --rule palat.unassim --sample 15
```

Or skip activation and call it directly:

```powershell
.\.venv\Scripts\pravapis.exe audit data/eval/tarask/corpus.tsv --rule palat.unassim --sample 15
```

Two things that will bite otherwise:

- **Do not type `bash` in front of the command.** The ```` ```powershell ```` label on a
  code block is a syntax-highlighting hint, not part of the command. Typing `bash …`
  launches WSL.
- **Every command below is on one line.** A trailing `\` continuation is bash syntax;
  PowerShell uses a backtick `` ` `` — but nothing here needs one.

Everything here is built and tested. What is missing is judgement, and it has to be
yours: a precision figure where the converter's author graded its own output would be
worth nothing, which is the same reason `gold_t2n.tsv` rows start as `proposed` and are
never scored. See `../../NORMS.md` and the README's "Independent T → N".

Two things are unreviewed:

| File | Unreviewed | What it gives you when done |
|---|---|---|
| `audit.tsv` | 437 rows / 640 tokens | **precision** on genuine Taraškievica |
| `gold_t2n.tsv` | 150 rows | **recall** and word accuracy for T → N |

---

## 1. The audit — precision

### Don't review it top to bottom

356 of the 437 rows occur exactly once, so working down by frequency buys almost nothing.
The leverage is in *which rule* fired:

| Rule | Rows | Tokens | Already evidenced by |
|---|---|---|---|
| `palat.*` | **349** | 488 (76%) | §29/§40/§43 citations, inline YAML tests, round-trip property tests |
| `lexicon` | 34 | 50 | hand-written entries only |
| `loan.stem_reverse` | 39 | 44 | derived from the forward stems |
| `morph.particle` | 6 | 45 | GrammarDB stress marks, §3/§29 |
| the rest | 9 | 13 | — |

The 349 `palat.*` rows are one cited rule each, firing on hundreds of different word
forms (`пасьля → пасля`, `ёсьць → ёсць`, `вобласьці → вобласці`). Grading them
individually is most of the clicking for almost none of the information.

### Step A — sample the softness rules, then accept them as a class

```powershell
pravapis audit data/eval/tarask/corpus.tsv --rule palat.unassim --sample 15
```

`--sample` spreads across the whole selection rather than showing the most frequent rows,
which are the ones least able to falsify the rule. Read the 15. If they are all right:

```powershell
pravapis audit data/eval/tarask/corpus.tsv --rule palat.unassim --mark ok --note "sampled 15, all correct" -o data/eval/tarask/audit.tsv
```

Repeat for `palat.ungeminate`, `palat.unapostrophe`, `palat.ungeminate.dz`. If a sample
turns up something wrong, don't bulk-mark that rule — review it row by row and record the
failure, because that is a real finding.

### Step B — review the 88 non-`palat` rows properly

```powershell
pravapis audit data/eval/tarask/corpus.tsv --rule morph.particle -o data/eval/tarask/audit.tsv
pravapis audit data/eval/tarask/corpus.tsv --rule loan. -o data/eval/tarask/audit.tsv
pravapis audit data/eval/tarask/corpus.tsv --rule lexicon -o data/eval/tarask/audit.tsv
```

These are where the converter makes a judgement rather than applying a cited pattern.
Start with `morph.particle`: 6 rows carrying 45 tokens, and the only rule that depends on
a stress heuristic rather than a spelling rule.

Edit the `verdict` column of `audit.tsv` directly — it is plain TSV, so a spreadsheet or
a text editor is fine. Values: `ok`, `wrong`, `unsure`, or blank for not yet reviewed.

### Step C — check

```powershell
pravapis audit data/eval/tarask/corpus.tsv -o data/eval/tarask/audit.tsv
```

prints precision and the share reviewed. Precision is token-weighted `ok / (ok + wrong)`;
`unsure` is excluded from the ratio but still counted, so it can't be used to flatter the
number.

---

## 2. `gold_t2n.tsv` — recall

150 rows whose Narkamaŭka side is a converter draft. Read a row, fix the Narkamaŭka side
if it is wrong, change `proposed` to `hand_written`. Only then does it count.

**You do not need all 150.** 40–50 promoted rows give a real number; `pravapis eval` warns
you when the changed-word count is too small to lean on. Check with:

```powershell
pravapis eval data/eval/tarask/gold_t2n.tsv -d narkamauka --trusted
```

While nothing is promoted it will tell you there is nothing to score, and say why.

---

## When a disagreement is not the converter's fault

be-tarask is community-written and does not follow the 2005 codification uniformly — some
articles use older Taraškievič conventions. If the input itself is non-conforming, mark
the audit row `unsure` or the gold row `uncertain`, **not** `wrong`. Scoring the converter
against text it was never meant to agree with would make the number worse than useless.

The tiebreaker is `data/reference/pravapis2005.txt`, the codifier's own prose.

---

## What "done" looks like

```powershell
python -m pytest                   # the skipped test stops skipping
pravapis audit data/eval/tarask/corpus.tsv -o data/eval/tarask/audit.tsv
pravapis eval data/eval/tarask/gold_t2n.tsv -d narkamauka --trusted
```

The one test that currently skips is
`test_independent_eval.py::test_audited_precision_does_not_regress`. It runs as soon as
any verdict exists and holds precision at ≥ 95% from then on. When it stops skipping,
Phase C has actually answered its question — and the README's T → N column can carry a
real accuracy figure instead of the asterisk it has now.

---

## Re-running after you change the converter

The audit counts describe one version of the converter. After adding stems or changing a
rule, re-run it: verdicts you have recorded are kept, counts are refreshed, and changes
the converter no longer makes are dropped so a stale verdict cannot skew the figure.
