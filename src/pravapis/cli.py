"""Command-line interface (typer + rich).

pravapis convert "снег" --to taraskievica
pravapis convert --file in.txt --out out.txt --to narkamauka
echo "снег" | pravapis convert --to t
pravapis explain "сімвал" --to taraskievica
pravapis build-lexicon data/lexicon/ --out data/lexicon.marisa
pravapis train data/eval/ambiguous.tsv --out data/models/disambig.joblib
pravapis eval data/eval/gold.tsv
pravapis eval --recall --misses misses.tsv
pravapis eval --coverage --top 20000
pravapis eval --round-trip
pravapis audit data/eval/tarask/corpus.tsv --to narkamauka --out audit.tsv
pravapis bench --size 10mb
pravapis serve --port 8000
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from pravapis import __version__
from pravapis.config import Config
from pravapis.metrics import (
    PROPOSED,
    UNSCORED,
    VERDICTS,
    AuditReport,
    AuditRow,
    audit_changes,
    audit_precision,
    merge_audit,
    read_audit,
    read_corpus,
    read_gold_origin,
    write_audit,
)
from pravapis.pipeline import Converter
from pravapis.translit import detect_script
from pravapis.types import Method, Orthography, Script

app = typer.Typer(
    help="Bidirectional Belarusian orthography converter (Narkamaŭka ↔ Taraškievica).",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()
errors = Console(stderr=True)

_DIRECTIONS: dict[str, Orthography] = {
    "taraskievica": Orthography.TARASKIEVICA,
    "t": Orthography.TARASKIEVICA,
    "tarask": Orthography.TARASKIEVICA,
    "narkamauka": Orthography.NARKAMAUKA,
    "n": Orthography.NARKAMAUKA,
    "narkam": Orthography.NARKAMAUKA,
}

ToOption = Annotated[
    str,
    typer.Option("--to", "-t", help="Target orthography: taraskievica (t) or narkamauka (n)."),
]
AggressiveOption = Annotated[
    bool,
    typer.Option(
        "--aggressive",
        help="Also apply optional transformations: forms the codification already allows "
        "(Фёдар → Хведар, і → й after a vowel). Off by default.",
    ),
]
ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", help="YAML config; defaults to the bundled data/ directory."),
]


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


@app.callback()
def _main() -> None:
    _utf8_console()


def _direction(value: str) -> Orthography:
    try:
        return _DIRECTIONS[value.strip().lower()]
    except KeyError:
        errors.print(f"[red]unknown orthography {value!r}; use taraskievica or narkamauka[/red]")
        raise typer.Exit(2) from None


def _converter(config: Path | None) -> Converter:
    return Converter.from_config(config)


def _script(name: str) -> Script:
    try:
        return Script(name.strip().lower())
    except ValueError:
        choices = ", ".join(s.value for s in Script)
        errors.print(f"[red]unknown script {name!r}; choose one of: {choices}[/red]")
        raise typer.Exit(2) from None


def _read_input(text: str | None, file: Path | None) -> str:
    if text is not None:
        return text
    if file is not None:
        return file.read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    errors.print("[red]no input: pass TEXT, --file, or pipe into stdin[/red]")
    raise typer.Exit(2)


@app.command()
def convert(
    text: Annotated[
        str | None, typer.Argument(help="Text to convert (or use --file / stdin).")
    ] = None,
    to: ToOption = "taraskievica",
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Input file.")] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output file.")] = None,
    config: ConfigOption = None,
    stats: Annotated[
        bool, typer.Option("--stats", help="Print per-method counts to stderr.")
    ] = False,
    aggressive: AggressiveOption = False,
) -> None:
    """Convert text between orthographies."""
    direction = _direction(to)
    converter = _converter(config).variant(aggressive)
    source = _read_input(text, file)

    totals: dict[Method, int] = dict.fromkeys(Method, 0)
    lines = source.splitlines(keepends=True)
    large = len(source) > 200_000
    pieces: list[str] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=errors,
        transient=True,
        disable=not large,
    ) as progress:
        task = progress.add_task("converting", total=len(lines))
        for line in lines:
            result = converter.convert(line, direction)
            pieces.append(result.text)
            for m, n in result.stats.items():
                totals[m] += n
            progress.advance(task)
    output = "".join(pieces)

    if out is not None:
        out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
        if text is not None and not output.endswith("\n"):
            sys.stdout.write("\n")
    if stats:
        words = sum(totals.values()) or 1
        errors.print(
            "  ".join(f"{m.value}={n} ({n / words:.0%})" for m, n in totals.items() if n),
        )


@app.command()
def translit(
    text: Annotated[
        str | None, typer.Argument(help="Text to transliterate (or use --file / stdin).")
    ] = None,
    to: Annotated[
        str | None,
        typer.Option(
            "--to",
            help="Target script: lacinka, official or cyrillic. "
            "Defaults to lacinka, or to cyrillic when --from is given.",
        ),
    ] = None,
    from_: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Source script when reading Latin back: lacinka, or 'auto' to detect it.",
        ),
    ] = None,
    no_convert: Annotated[
        bool,
        typer.Option(
            "--no-convert",
            help="Transliterate the input as given, without converting orthography first.",
        ),
    ] = False,
    orthography: Annotated[
        str | None,
        typer.Option("--orthography", help="With --from: orthography to produce."),
    ] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Input file.")] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output file.")] = None,
    config: ConfigOption = None,
) -> None:
    """Transliterate between Cyrillic and Latin.

    Łacinka is paired with Taraškievica and the 2007 romanisation with Narkamaŭka,
    because each shares that orthography's treatment of softness. The paired
    conversion runs first unless --no-convert is given:

        pravapis translit "снег" --to lacinka               # śnieh
        pravapis translit "снег" --to lacinka --no-convert  # snieh
        pravapis translit "снег" --to official              # snieh
        pravapis translit "śnieh" --from lacinka            # сьнег
        pravapis translit "śnieh" --from auto                # detects Łacinka
        pravapis translit "śnieh" --from lacinka --to official  # snieh
    """
    converter = _converter(config)
    source = _read_input(text, file)
    # Reading a script and naming no target means "back to Cyrillic" — the only reading
    # that does anything. Writing one defaults to Łacinka.
    to = to or ("cyrillic" if from_ is not None else "lacinka")

    if from_ is not None:
        if from_.strip().lower() == "auto":
            found = detect_script(source)
            if found.script is None:
                errors.print(f"[red]cannot detect the script: {found.reason}[/red]")
                raise typer.Exit(2)
            if not found.certain:
                errors.print(
                    f"[yellow]assuming {found.script.value}: {found.reason}[/yellow] "
                    "Pass --from explicitly if that is wrong."
                )
            script = found.script
        else:
            script = _script(from_)
        target = _script(to)
        if target is Script.CYRILLIC:
            direction = _direction(orthography) if orthography else None
            output = converter.read_script(source, script, direction)
        else:
            output = converter.transcode(source, target, from_script=script)
    else:
        output = converter.render(source, _script(to), convert=not no_convert)

    if out is not None:
        out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
        if text is not None and not output.endswith("\n"):
            sys.stdout.write("\n")


@app.command()
def explain(
    text: Annotated[str, typer.Argument(help="Word or sentence to explain.")],
    to: ToOption = "taraskievica",
    config: ConfigOption = None,
    aggressive: AggressiveOption = False,
) -> None:
    """Show how each word was resolved: lexicon hit, rules fired, or model score."""
    direction = _direction(to)
    converter = _converter(config).variant(aggressive)
    table = Table(title=f"→ {direction.value}", show_lines=False)
    table.add_column("source", style="bold")
    table.add_column("target", style="green")
    table.add_column("method")
    table.add_column("rules / trace")
    table.add_column("conf", justify="right")
    for e in converter.explain(text, direction):
        trace = "\n".join(f"{t.rule_id}: {t.before} → {t.after}" for t in e.traces) or (
            e.rule_id or ""
        )
        table.add_row(e.source, e.target, e.method.value, trace, f"{e.confidence:.2f}")
    console.print(table)


@app.command("build-lexicon")
def build_lexicon(
    src: Annotated[Path, typer.Argument(help="Directory of TSV files, or one TSV file.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output .marisa container.")],
    strict: Annotated[bool, typer.Option("--strict", help="Fail on warnings too.")] = False,
) -> None:
    """Compile TSV sources into the marisa-trie lexicon file."""
    from pravapis.lexicon.builder import (
        build_from_sources,
        read_sources,
        save_lexicon,
        sources_digest,
        validate_entries,
    )

    problems = validate_entries(read_sources(src))
    for p in problems:
        errors.print(("[red]" if p.severity == "error" else "[yellow]") + str(p))
    hard = [p for p in problems if p.severity == "error"]
    if hard or (strict and problems):
        errors.print(f"[red]{len(problems)} problem(s); nothing written[/red]")
        raise typer.Exit(1)
    fwd, rev = build_from_sources(src)
    save_lexicon(fwd, rev, out, source_digest=sources_digest(src))
    console.print(
        f"wrote [bold]{out}[/bold]: {len(fwd)} n→t keys, {len(rev)} t→n keys, "
        f"{out.stat().st_size / 1024:.1f} KiB"
    )


@app.command()
def train(
    data: Annotated[Path, typer.Argument(help="TSV: source, target, context.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Output .joblib path.")],
    config: ConfigOption = None,
    folds: Annotated[int, typer.Option(help="Cross-validation folds.")] = 5,
    seed: Annotated[int, typer.Option()] = 42,
) -> None:
    r"""Train the disambiguation classifier (requires pravapis\[ml])."""
    from pravapis.disambiguate import train as tr
    from pravapis.rules.engine import RuleEngine

    cfg = Config.load(config) if config else Config.default()
    engine = RuleEngine.from_yaml(*cfg.rules)
    X, y = tr.load_training_pairs(data, engine)
    if not X:
        errors.print("[red]no usable training rows[/red]")
        raise typer.Exit(1)
    report = tr.cross_validate(X, y, folds=folds)
    model = tr.train(X, y, seed=seed)
    tr.save_model(model, out)
    table = Table(title="cross-validation")
    table.add_column("label")
    table.add_column("n", justify="right")
    for label, n in sorted(report.label_counts.items()):
        table.add_row(label, str(n))
    console.print(table)
    console.print(
        f"{report.n_samples} samples, {report.folds}-fold accuracy "
        f"[bold]{report.mean:.1%}[/bold] ± {report.std:.1%}; wrote [bold]{out}[/bold]"
    )


@app.command("eval")
def eval_cmd(
    gold: Annotated[Path | None, typer.Argument(help="TSV: narkamauka, taraskievica.")] = None,
    config: ConfigOption = None,
    direction: Annotated[
        str, typer.Option("--direction", "-d", help="taraskievica, narkamauka or both")
    ] = "both",
    show_errors: Annotated[int, typer.Option("--errors", help="How many errors to list.")] = 20,
    json_out: Annotated[
        Path | None, typer.Option("--json", help="Write the report as JSON.")
    ] = None,
    trusted: Annotated[
        bool,
        typer.Option(
            "--trusted",
            help="Score only hand_written rows (never adjusted after seeing converter output).",
        ),
    ] = False,
    recall: Annotated[
        bool,
        typer.Option("--recall", help="Measure recall against the aligned be ↔ be-tarask corpus."),
    ] = False,
    corpus: Annotated[
        Path | None, typer.Option("--corpus", help="Parallel corpus for --recall.")
    ] = None,
    split: Annotated[
        str,
        typer.Option(
            "--split",
            help="Which split to score: dev (default), train, test, or all. "
            "test is frozen — read it at milestones, not while iterating.",
        ),
    ] = "dev",
    misses: Annotated[
        Path | None, typer.Option("--misses", help="Write every miss, grouped by cause.")
    ] = None,
    coverage: Annotated[
        bool, typer.Option("--coverage", help="Stem and lexicon coverage over a frequency list.")
    ] = False,
    frequency: Annotated[
        Path | None, typer.Option("--frequency", help="Frequency list for --coverage.")
    ] = None,
    top: Annotated[
        int, typer.Option("--top", help="How many forms of the list to measure.")
    ] = 20_000,
    round_trip: Annotated[
        bool, typer.Option("--round-trip", help="N→T→N identity rate; dumps non-identity cases.")
    ] = False,
    round_trip_corpus: Annotated[
        Path | None, typer.Option("--round-trip-corpus", help="Text to round-trip.")
    ] = None,
    round_trip_dump: Annotated[
        Path | None, typer.Option("--round-trip-dump", help="Where to write the failures.")
    ] = None,
) -> None:
    """Score the converter on a gold set: accuracy, coverage split, round trip, throughput.

    Rows marked ``uncertain`` are never scored. By default the remaining rows
    are scored and the hand_written subset is scored alongside for comparison;
    ``--trusted`` scores only that subset.

    ``--recall``, ``--coverage`` and ``--round-trip`` each answer a question the gold set
    cannot, and each runs without a gold file.
    """
    from pravapis.metrics import HAND_WRITTEN, evaluate, read_gold, read_gold_rows

    converter = _converter(config)
    if recall or coverage or round_trip:
        data = Config.default().lexicon.parent
        if recall:
            _report_recall(
                converter,
                corpus or data / "corpora" / "parallel.tsv",
                misses,
                None if split == "all" else split,
            )
        if coverage:
            _report_coverage(converter, frequency or data / "corpora" / "frequency_be.tsv", top)
        if round_trip:
            _report_round_trip(
                converter,
                round_trip_corpus or data / "eval" / "roundtrip_corpus.txt",
                round_trip_dump or data / "eval" / "roundtrip_failures.tsv",
            )
        return
    if gold is None:
        errors.print("[red]a gold file is required[/red] (or use --recall/--coverage/--round-trip)")
        raise typer.Exit(code=2)
    rows = read_gold_rows(gold)
    origin = read_gold_origin(gold)
    n_uncertain = sum(r.provenance in UNSCORED for r in rows)
    pairs = read_gold(gold, trusted_only=trusted)
    subset = "hand_written only (--trusted)" if trusted else "all except uncertain/proposed"
    console.print(f"lexicon: {converter.lexicon_origin}")
    if origin is None:
        console.print(
            "[yellow]no `# origin:` header: cannot tell which direction is independent "
            "evidence and which is derived[/yellow]"
        )
    else:
        console.print(f"gold authored in: [bold]{origin.value}[/bold]")
    console.print(
        f"gold rows: {len(rows)} · [yellow]skipped {n_uncertain} "
        f"uncertain/proposed[/yellow]"
        + (
            f" · skipped {len(rows) - n_uncertain - len(pairs)} non-hand_written"
            if trusted
            else f" · {sum(r.provenance == HAND_WRITTEN for r in rows)} hand_written"
        )
        + f" · scoring [bold]{subset}[/bold]"
    )
    trusted_pairs = None if trusted else read_gold(gold, trusted_only=True)
    directions = list(Orthography) if direction.lower() == "both" else [_direction(direction)]
    payload: dict[str, object] = {}
    divergences: list[str] = []
    if not pairs:
        n_proposed = sum(r.provenance == PROPOSED for r in rows)
        console.print(
            f"[yellow]nothing to score: {n_proposed} of {len(rows)} rows are unreviewed "
            "converter proposals.[/yellow] Scoring a proposal against the converter that "
            "wrote it returns 100% by construction, so `proposed` rows never count. "
            "Review them and change `proposed` to `hand_written`."
        )
        raise typer.Exit(0)
    for d in directions:
        rep = evaluate(converter, pairs, d, error_limit=show_errors, origin=origin)
        console.rule(f"→ {d.value}")
        console.print(
            f"gold set: [bold]{rep.pairs}[/bold] sentences · [bold]{rep.words}[/bold] words · "
            f"[bold]{rep.changed_words}[/bold] should change "
            f"({rep.changed_words / rep.words if rep.words else 0:.1%}) · "
            f"{rep.unchanged_words} should not · misaligned sentences {rep.misaligned}"
        )
        if rep.changed_words < 1000:
            console.print(
                f"[yellow]only {rep.changed_words} changed words: "
                f"±1 word moves change accuracy by "
                f"{1 / rep.changed_words if rep.changed_words else 1:.2%}[/yellow]"
            )
        if rep.origin is None:
            label, caveat = "headline (vs do-nothing baseline)", ""
        elif rep.is_independent:
            label = "headline — accuracy (vs do-nothing baseline)"
            caveat = ""
        else:
            label = "headline — SELF-CONSISTENCY, not accuracy"
            caveat = (
                f"[yellow]The gold was authored in {rep.origin.value}, so the "
                f"{rep.origin.opposite.value} input scored here was derived from it. This "
                "measures whether the converter can undo a transformation produced by the "
                "same reading of the norm it implements — not whether it is right. For an "
                f"independent → {rep.direction.value} figure see data/eval/tarask/ "
                "(`pravapis audit`).[/yellow]"
            )
        if caveat:
            console.print(caveat)
        headline = Table(title=label)
        headline.add_column("metric")
        headline.add_column("converter", justify="right")
        headline.add_column("baseline", justify="right")
        headline.add_column("n", justify="right")
        headline.add_row(
            "[bold]change accuracy[/bold] (words that should change)",
            f"[bold]{rep.change_accuracy:.1%}[/bold]",
            "0.0%",
            f"{rep.changed_correct}/{rep.changed_words}",
        )
        headline.add_row(
            "false-positive rate (words that should not change)",
            f"{rep.false_positive_rate:.1%}",
            "0.0%",
            f"{rep.false_positives}/{rep.unchanged_words}",
        )
        headline.add_row(
            "word accuracy (all)",
            f"{rep.accuracy:.1%}",
            f"{rep.baseline_accuracy:.1%}",
            str(rep.words),
        )
        headline.add_row(
            "sentence accuracy",
            f"{rep.sentence_accuracy:.1%}",
            f"{rep.baseline_sentence_accuracy:.1%}",
            str(rep.pairs),
        )
        if rep.word_round_trip is not None and rep.round_trip is not None:
            back = "N→T→N" if d is Orthography.TARASKIEVICA else "T→N→T"
            headline.add_row(
                f"word round trip ({back})", f"{rep.word_round_trip:.2%}", "100.0%", ""
            )
            headline.add_row(f"sentence round trip ({back})", f"{rep.round_trip:.1%}", "100.0%", "")
        console.print(headline)
        console.print(
            f"word-error reduction vs baseline [bold]{rep.error_reduction:.1%}[/bold]"
            f" · {rep.mb_per_second:.2f} MB/s"
        )
        if trusted_pairs is not None:
            tr = evaluate(
                converter, trusted_pairs, d, error_limit=0, round_trip=False, origin=origin
            )
            cmp = Table(title="hand_written subset vs scored set")
            cmp.add_column("metric")
            cmp.add_column("scored", justify="right")
            cmp.add_column("hand_written", justify="right")
            cmp.add_column("Δ pts", justify="right")
            for name, a, b in (
                ("change accuracy", rep.change_accuracy, tr.change_accuracy),
                ("false-positive rate", rep.false_positive_rate, tr.false_positive_rate),
                ("word accuracy", rep.accuracy, tr.accuracy),
                ("baseline word accuracy", rep.baseline_accuracy, tr.baseline_accuracy),
            ):
                delta = (b - a) * 100
                cmp.add_row(name, f"{a:.1%}", f"{b:.1%}", f"{delta:+.1f}")
                if abs(delta) > 2 and name != "baseline word accuracy":
                    divergences.append(f"→ {d.value}: {name} {a:.1%} vs {b:.1%} ({delta:+.1f} pts)")
            console.print(cmp)
            console.print(
                f"hand_written: {tr.pairs} sentences · {tr.words} words · "
                f"{tr.changed_words} should change ({tr.changed_correct} right)"
            )
        table = Table(title="coverage by method")
        table.add_column("method")
        table.add_column("count", justify="right")
        table.add_column("share", justify="right")
        table.add_column("accuracy", justify="right")
        for m, s in rep.breakdown.items():
            acc = "" if s.accuracy is None else f"{s.accuracy:.1%}"
            table.add_row(m.value, str(s.count), f"{s.share:.1%}", acc)
        console.print(table)
        if rep.errors:
            et = Table(title="errors")
            et.add_column("source")
            et.add_column("predicted", style="red")
            et.add_column("expected", style="green")
            et.add_column("method")
            for e in rep.errors:
                et.add_row(e.source, e.predicted, e.expected, e.method.value if e.method else "")
            console.print(et)
        payload[d.value] = {
            "pairs": rep.pairs,
            "words": rep.words,
            "changed_words": rep.changed_words,
            "unchanged_words": rep.unchanged_words,
            "misaligned": rep.misaligned,
            "change_accuracy": rep.change_accuracy,
            "false_positive_rate": rep.false_positive_rate,
            "false_positives": rep.false_positives,
            "accuracy": rep.accuracy,
            "baseline_accuracy": rep.baseline_accuracy,
            "error_reduction": rep.error_reduction,
            "sentence_accuracy": rep.sentence_accuracy,
            "origin": rep.origin.value if rep.origin else None,
            "independent": rep.is_independent,
            "baseline_sentence_accuracy": rep.baseline_sentence_accuracy,
            "subset": subset,
            "lexicon": converter.lexicon_origin,
            "skipped_uncertain": n_uncertain,
            "round_trip": rep.round_trip,
            "word_round_trip": rep.word_round_trip,
            "mb_per_second": rep.mb_per_second,
            "breakdown": {
                m.value: {"count": s.count, "share": s.share, "accuracy": s.accuracy}
                for m, s in rep.breakdown.items()
            },
            "per_rule": {
                rid: {
                    "precision": p.precision,
                    "recall": p.recall,
                    "f1": p.f1,
                    "support": p.support,
                }
                for rid, p in sorted(rep.per_rule.items())
            },
            "errors": [
                {"source": e.source, "predicted": e.predicted, "expected": e.expected}
                for e in rep.errors
            ],
        }
    if divergences:
        console.rule("[bold red]WARNING[/bold red]")
        console.print(
            "[bold red]hand_written subset diverges from the scored set "
            "by more than 2 points:[/bold red]"
        )
        for line in divergences:
            console.print(f"[bold red]  {line}[/bold red]")
        console.print(
            "[bold red]Trust the hand_written number; the converter_checked rows are biased "
            "toward the converter.[/bold red]"
        )
        payload["divergence_warnings"] = divergences
    if json_out is not None:
        json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"wrote {json_out}")


def _parse_size(value: str) -> int:
    v = value.strip().lower()
    for suffix, mult in (("mb", 1_000_000), ("kb", 1_000), ("b", 1)):
        if v.endswith(suffix):
            return int(float(v[: -len(suffix)]) * mult)
    return int(v)


@app.command()
def audit(
    corpus: Annotated[Path, typer.Argument(help="Corpus TSV: sentence<TAB>article<TAB>revid.")],
    to: ToOption = "narkamauka",
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Audit TSV to create or update.")
    ] = None,
    rule: Annotated[
        str | None,
        typer.Option("--rule", help="Only rows whose rule id contains this, e.g. palat."),
    ] = None,
    sample: Annotated[
        int | None,
        typer.Option("--sample", help="Show N rows spread across the selection, not the top N."),
    ] = None,
    mark: Annotated[
        str | None,
        typer.Option("--mark", help="Bulk-set the verdict on the selected unreviewed rows."),
    ] = None,
    note: Annotated[str, typer.Option("--note", help="Note to record alongside a --mark.")] = "",
    force: Annotated[
        bool,
        typer.Option("--force", help="With --mark: also overwrite verdicts already recorded."),
    ] = False,
    config: ConfigOption = None,
    top: Annotated[int, typer.Option("--top", help="How many rows to print.")] = 25,
) -> None:
    """Precision audit: every distinct change the converter makes, for review.

    Scores what the gold set cannot. data/eval/gold.tsv is Narkamaŭka in origin — its
    Taraškievica side was derived from the Narkamaŭka side — so scoring T → N on it
    measures self-consistency. This runs the converter over text nobody derived and
    lists each distinct change for a human to mark ok / wrong / unsure. Re-running keeps
    verdicts already recorded and re-counts against the current converter.

    Reviewing 400 rows one at a time is the wrong shape of work: the softness rules fire
    on hundreds of word forms but are one cited rule each. Sample a rule, then accept it
    as a class:

        pravapis audit CORPUS --rule palat.unassim --sample 15
        pravapis audit CORPUS --rule palat.unassim --mark ok --note "sampled 15" -o AUDIT

    and review the rules that are actually making a judgement row by row:

        pravapis audit CORPUS --rule loan. -o AUDIT
    """
    direction = _direction(to)
    converter = _converter(config)
    rows = read_corpus(corpus)
    if not rows:
        errors.print(f"[red]{corpus} has no sentences[/red]")
        raise typer.Exit(2)

    fresh = audit_changes(converter, [r.sentence for r in rows], direction)
    existing = read_audit(out) if out is not None else {}
    merged = merge_audit(fresh, existing) if out is not None else fresh
    dropped = sorted(set(existing) - {r.key for r in fresh})
    if dropped:
        errors.print(
            f"[yellow]{len(dropped)} row(s) in {out} describe changes the converter no "
            "longer makes; they are being dropped.[/yellow] If you edited the `source` or "
            "`target` column to correct a word, that is what causes this — those columns "
            "record what the converter did, and only `verdict` and `note` are yours to "
            "fill in. The changes they described return below, unreviewed."
        )
        for key in dropped[:5]:
            errors.print(f"    dropped: {key[0]} → {key[1]} [{key[2]}]")

    selected = [r for r in merged if rule is None or rule in r.rule]
    if rule is not None and not selected:
        errors.print(f"[red]no rows whose rule contains {rule!r}[/red]")
        raise typer.Exit(2)

    if mark is not None:
        if mark not in VERDICTS or not mark:
            choices = ", ".join(sorted(v for v in VERDICTS if v))
            errors.print(f"[red]--mark must be one of: {choices}[/red]")
            raise typer.Exit(2)
        if out is None:
            errors.print("[red]--mark needs --out: there is nowhere to record the verdict[/red]")
            raise typer.Exit(2)
        if rule is None and not force:
            errors.print(
                "[red]--mark without --rule would grade every change in one go.[/red] "
                "Pass --rule to scope it, or --force if you really mean all of them."
            )
            raise typer.Exit(2)
        targets = {r.key for r in selected if force or not r.verdict}
        merged = [
            replace(r, verdict=mark, note=note or r.note) if r.key in targets else r for r in merged
        ]
        selected = [r for r in merged if rule is None or rule in r.rule]
        console.print(
            f"marked [bold]{len(targets)}[/bold] row(s) as [bold]{mark}[/bold]"
            + (f" (rule contains {rule!r})" if rule else "")
        )

    if out is not None:
        write_audit(merged, out)

    shown = _spread(selected, sample) if sample else selected[:top]
    title = f"changes → {direction.value}"
    if rule:
        title += f" · rule contains {rule!r}"
    title += f" · showing {len(shown)} of {len(selected)}"
    table = Table(title=title, box=box.SIMPLE)
    table.add_column("n", justify="right")
    table.add_column("source")
    table.add_column("target")
    table.add_column("rule")
    table.add_column("verdict")
    for row in shown:
        table.add_row(str(row.count), row.source, row.target, row.rule, row.verdict or "—")
    console.print(table)

    if rule is not None:
        _print_audit_report(audit_precision(selected), f"selection ({rule!r})")
    _print_audit_report(audit_precision(merged), "whole audit", out)


def _spread(rows: Sequence[AuditRow], n: int) -> list[AuditRow]:
    """``n`` rows spread evenly across ``rows``.

    A sample meant to justify accepting a whole rule must not be the most frequent rows
    only — those are the ones most likely to be right.
    """
    if n >= len(rows):
        return list(rows)
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def _print_audit_report(report: AuditReport, label: str, out: Path | None = None) -> None:
    summary = Table(title=label, box=box.SIMPLE)
    summary.add_column("metric")
    summary.add_column("rows", justify="right")
    summary.add_column("tokens", justify="right")
    summary.add_row("ok", str(report.ok_rows), str(report.ok_tokens))
    summary.add_row("wrong", str(report.wrong_rows), str(report.wrong_tokens))
    summary.add_row("unsure", str(report.unsure_rows), str(report.unsure_tokens))
    summary.add_row("not reviewed", str(report.unreviewed_rows), str(report.unreviewed_tokens))
    summary.add_row("total", str(report.distinct), str(report.tokens))
    console.print(summary)
    if report.precision is None:
        console.print(
            "[yellow]precision: nothing reviewed yet[/yellow]"
            + (f" — fill in the `verdict` column of {out}" if out else "")
        )
    else:
        console.print(
            f"precision [bold]{report.precision:.1%}[/bold] "
            f"({report.ok_tokens}/{report.scored_tokens} reviewed tokens) · "
            f"{report.reviewed_share:.0%} of changed tokens reviewed"
        )


@app.command()
def bench(
    size: Annotated[str, typer.Option("--size", help="Input size, e.g. 10mb")] = "10mb",
    config: ConfigOption = None,
    source: Annotated[
        Path | None, typer.Option("--source", help="Text file to cycle; defaults to the gold set.")
    ] = None,
) -> None:
    """Measure throughput in MB/s on a synthetic corpus of the given size."""
    from pravapis.metrics import read_gold

    converter = _converter(config)
    target = _parse_size(size)
    if source is not None:
        seed_text = source.read_text(encoding="utf-8")
    else:
        gold = Config.default().lexicon.parent / "eval" / "gold.tsv"
        seed_text = "\n".join(n for n, _ in read_gold(gold)) + "\n"
    reps = max(1, target // len(seed_text.encode("utf-8")) + 1)
    corpus = seed_text * reps
    nbytes = len(corpus.encode("utf-8"))
    converter.convert(seed_text, Orthography.TARASKIEVICA)  # warm caches
    start = time.perf_counter()
    result = converter.convert(corpus, Orthography.TARASKIEVICA)
    elapsed = time.perf_counter() - start
    words = sum(result.stats.values())
    console.print(
        f"{nbytes / 1e6:.1f} MB, {words:,} words in {elapsed:.2f}s → "
        f"[bold]{nbytes / 1e6 / elapsed:.2f} MB/s[/bold], {words / elapsed:,.0f} words/s"
    )


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    config: ConfigOption = None,
) -> None:
    """Run the HTTP API with uvicorn."""
    import os

    import uvicorn

    if config is not None:
        os.environ["PRAVAPIS_CONFIG"] = str(config)
    uvicorn.run("pravapis.api.main:app", host=host, port=port)


def _report_recall(
    converter: Converter, corpus: Path, misses_out: Path | None, split: str | None
) -> None:
    """In-scope recall with a confidence interval, and the exclusions stated, not hidden."""
    from pravapis.recall import common_shapes, measure_recall, read_parallel, write_misses
    from pravapis.scope import Scope, format_interval

    if not corpus.is_file():
        errors.print(
            f"[red]no parallel corpus at {corpus}[/red] — build one with "
            "`python scripts/fetch_parallel_corpus.py --articles 2600`"
        )
        raise typer.Exit(code=2)
    pairs = read_parallel(corpus, split)
    if not pairs:
        errors.print(f"[red]no rows in {corpus.name} for split {split!r}[/red]")
        raise typer.Exit(code=2)
    report = measure_recall(pairs, converter, split)

    console.rule(f"recall — split: {split or 'all'}")
    console.print(
        f"corpus: {corpus.name} · [bold]{report.articles}[/bold] articles · "
        f"[bold]{report.pairs}[/bold] sentence pairs · [bold]{report.tokens}[/bold] tokens · "
        f"[bold]{report.changes}[/bold] attested differences"
    )
    low, high = report.interval
    console.print(
        f"\n  [bold]in-scope N → T recall: {report.recall:.1%}[/bold] "
        f"[[{low:.1%}, {high:.1%}] Wilson 95%]  "
        f"({report.in_scope_hits}/{report.in_scope})\n"
    )

    buckets = Table(title="every attested difference, sorted by whose job it is", box=box.SIMPLE)
    buckets.add_column("bucket")
    buckets.add_column("n", justify="right")
    buckets.add_column("share", justify="right")
    buckets.add_column("counts toward the headline?")
    reasons = {
        Scope.IN_SCOPE: "[bold]yes — this is the contract[/bold]",
        Scope.GRAMMATICAL: "no — Збор 2005 is a spelling code; declension is outside it",
        Scope.REFERENCE_DEVIATES: "no — be-tarask contradicts the 2005 code here",
        Scope.NOT_ORTHOGRAPHIC: "no — the two writers chose different words",
    }
    total = report.changes or 1
    for scope in Scope:
        n = report.by_scope.get(scope, 0)
        buckets.add_row(scope.value, str(n), f"{n / total:.0%}", reasons[scope])
    console.print(buckets)

    causes = Table(title="in-scope misses by cause — where a fix would go", box=box.SIMPLE)
    causes.add_column("cause")
    causes.add_column("n", justify="right")
    causes.add_column("share", justify="right")
    causes.add_column("example")
    counted = len(report.misses) or 1
    for cause, n in sorted(report.by_cause.items(), key=lambda kv: -kv[1]):
        if not n:
            continue
        example = next(m for m in report.misses if m.cause is cause)
        causes.add_row(
            cause.value,
            str(n),
            f"{n / counted:.0%}",
            f"{example.change.source} → {example.change.expected} ({example.detail})",
        )
    console.print(causes)

    per = Table(title="in-scope recall by alternation, with 95% intervals", box=box.SIMPLE)
    per.add_column("alternation")
    per.add_column("recall [95% CI]", justify="right")
    per.add_column("n", justify="right")
    for code, (ok, n) in sorted(report.by_alternation.items(), key=lambda kv: -kv[1][1]):
        per.add_row(code, format_interval(ok, n), f"{ok}/{n}")
    console.print(per)
    console.print(
        "[dim]Intervals are Wilson 95%. A class of eighty cases cannot support a claim "
        "narrower than its interval, however precise the point estimate looks.[/dim]"
    )

    shapes = common_shapes(report)
    if shapes:
        inside = Table(
            title="inside `other` — in-scope changes no alternation models", box=box.SIMPLE
        )
        inside.add_column("edit")
        inside.add_column("n", justify="right")
        for shape, n in shapes:
            inside.add_row(shape, str(n))
        console.print(inside)

    if report.false_positives:
        console.print(
            f"[yellow]{len(report.false_positives)} word(s) the two wikis spell identically "
            "that the converter changed anyway[/yellow], e.g. "
            + ", ".join(f"{s}→{t} ({r})" for s, t, r in report.false_positives[:5])
        )
        console.print(
            "[dim]Weaker evidence than the false-positive rate on the gold set: be-tarask "
            "articles are not uniformly Taraškievica, so an unconverted word on that side "
            "looks the same here as a converter error.[/dim]"
        )
    else:
        console.print("[green]no changes to words both wikis spell alike[/green]")

    if misses_out is not None:
        write_misses(report, misses_out)
        console.print(f"in-scope misses → {misses_out}")


def _report_coverage(converter: Converter, frequency: Path, top: int) -> None:
    from pravapis.coverage import measure_coverage, read_frequency_list

    if not frequency.is_file():
        errors.print(
            f"[red]no frequency list at {frequency}[/red] — build one with "
            "`python scripts/build_frequency_list.py --articles 4000`"
        )
        raise typer.Exit(code=2)
    forms = read_frequency_list(frequency, limit=top)
    report = measure_coverage(forms, converter)
    console.rule(f"coverage — top {report.forms} word forms")
    console.print(
        f"list: {frequency.name} · [bold]{report.forms}[/bold] forms · "
        f"[bold]{report.occurrences}[/bold] occurrences"
    )
    table = Table(box=box.SIMPLE)
    table.add_column("what the converter knows")
    table.add_column("forms", justify="right")
    table.add_column("of types", justify="right")
    table.add_column("of tokens", justify="right")
    for label, bucket in (
        ("stem — loan", report.stem_loan),
        ("stem — native guard", report.stem_native),
        ("lexicon entry", report.lexicon),
        ("a rule changes it (no etymology needed)", report.rule),
        ("nothing", report.untouched),
    ):
        types, tokens = report.share(bucket)
        table.add_row(label, str(bucket.types), f"{types:.1%}", f"{tokens:.1%}")
    console.print(table)
    stem_types, stem_tokens = report.share(report.stem)
    console.print(
        f"[bold]stem coverage: {stem_types:.1%} of forms, {stem_tokens:.1%} of tokens[/bold]"
    )
    console.print(
        "[dim]A low stem figure is not in itself a gap: stems exist only to tell the "
        "loanword rules that a word is a borrowing, and most Belarusian word forms are "
        "native and need none. Read it next to the loanword recall above.[/dim]"
    )


def _report_round_trip(converter: Converter, corpus: Path, dump: Path) -> None:
    from pravapis.metrics import round_trip_consistency, write_round_trip_failures

    if not corpus.is_file():
        errors.print(f"[red]no corpus at {corpus}[/red]")
        raise typer.Exit(code=2)
    lines = [
        ln.strip()
        for ln in corpus.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    sentence_rate = round_trip_consistency(lines, converter)
    n_words, failures, groups = write_round_trip_failures(lines, converter, dump, corpus.name)
    console.rule("round-trip drift — N → T → N")
    console.print(
        f"corpus: {corpus.name} · [bold]{len(lines)}[/bold] sentences · "
        f"[bold]{n_words}[/bold] words"
    )
    table = Table(box=box.SIMPLE)
    table.add_column("identity rate")
    table.add_column("rate", justify="right")
    table.add_column("n", justify="right")
    table.add_row(
        "word level",
        f"[bold]{1 - len(failures) / n_words if n_words else 0:.2%}[/bold]",
        f"{n_words - len(failures)}/{n_words}",
    )
    table.add_row("sentence level", f"{sentence_rate:.2%}", f"{len(lines)}")
    console.print(table)
    for group, items in groups[:10]:
        console.print(f"  {len(items):5d}  {group}")
    console.print(f"non-identity cases → {dump}")


@app.command("validate-data")
def validate_data_cmd(
    data_dir: Annotated[
        Path | None,
        typer.Argument(help="Data directory to check; defaults to the one pravapis reads."),
    ] = None,
) -> None:
    """Check every data file against the JSON Schemas in data/schemas/.

    The schemas are the specification. This command is what makes them binding, and it
    is the same check CI runs.
    """
    from pravapis.dataspec import DATA_VERSION, validate_data

    base = data_dir or Config.default().lexicon.parent
    problems = validate_data(base)
    if not problems:
        console.print(
            f"[green]ok[/green] — {base} is valid against data/schemas/ "
            f"(this build implements data version {DATA_VERSION})"
        )
        return
    table = Table(box=box.SIMPLE, header_style="bold")
    table.add_column("file")
    table.add_column("where")
    table.add_column("problem")
    for problem in problems:
        table.add_row(str(problem.file.name), problem.where, problem.message)
    console.print(table)
    errors.print(f"[red]{len(problems)} problem(s)[/red]")
    raise typer.Exit(code=1)


@app.command("export-conformance")
def export_conformance_cmd(
    out: Annotated[
        Path, typer.Option("--out", help="Directory for cases.jsonl and manifest.json")
    ] = Path("conformance"),
    data_dir: Annotated[Path | None, typer.Option("--data", help="Data directory")] = None,
    check: Annotated[
        bool,
        typer.Option("--check", help="Fail if the committed corpus is not what this would write."),
    ] = False,
) -> None:
    """Flatten every test case in the data into one cross-language contract.

    Inline rule tests, inline transliteration tests, the trusted gold subset and the
    independent held-out sentences become ``conformance/cases.jsonl``. A port is correct
    iff it passes that file. Regenerate it on every data change and commit it.
    """
    import json as _json

    from pravapis.conformance import export

    base = data_dir or Config.default().lexicon.parent
    if check:
        before = (out / "cases.jsonl").read_bytes() if (out / "cases.jsonl").is_file() else b""
    manifest = export(base, out)
    if check:
        after = (out / "cases.jsonl").read_bytes()
        if before != after:
            (out / "cases.jsonl").write_bytes(before)
            errors.print(
                "[red]conformance/cases.jsonl is stale[/red] — the data has changed since it "
                "was generated. Run `pravapis export-conformance` and commit the result."
            )
            raise typer.Exit(code=1)
    console.print(
        f"[green]{manifest['cases']}[/green] cases → {out / 'cases.jsonl'}  "
        f"(data version {manifest['data_version']}, sha256 {manifest['sha256'][:12]}…)"
    )
    for kind, count in manifest["cases_by_kind"].items():
        console.print(f"  {kind:<9} {count:>5}")
    if manifest["known_failures"]:
        console.print(
            f"  [yellow]{manifest['known_failures']} known failure(s)[/yellow] → "
            f"{out / 'known_failures.jsonl'} — cases the reference implementation does not "
            "pass, kept out of the contract and not hidden."
        )
    _json.loads((out / "manifest.json").read_text(encoding="utf-8"))  # written and parseable


@app.command()
def version() -> None:
    from pravapis.dataversion import DATA_VERSION, read_data_version

    console.print(f"pravapis {__version__}")
    try:
        console.print(f"data {read_data_version()} (implements {DATA_VERSION})")
    except Exception as exc:  # the package may be installed without its data
        console.print(f"data [yellow]unavailable[/yellow] (implements {DATA_VERSION}): {exc}")


if __name__ == "__main__":  # pragma: no cover
    app()
