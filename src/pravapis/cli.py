"""Command-line interface (typer + rich).

pravapis convert "снег" --to taraskievica
pravapis convert --file in.txt --out out.txt --to narkamauka
echo "снег" | pravapis convert --to t
pravapis explain "сімвал" --to taraskievica
pravapis build-lexicon data/lexicon/ --out data/lexicon.marisa
pravapis train data/eval/ambiguous.tsv --out data/models/disambig.joblib
pravapis eval data/eval/gold.tsv
pravapis bench --size 10mb
pravapis serve --port 8000
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from pravapis import __version__
from pravapis.config import Config
from pravapis.pipeline import Converter
from pravapis.types import Method, Orthography

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
    gold: Annotated[Path, typer.Argument(help="TSV: narkamauka, taraskievica.")],
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
) -> None:
    """Score the converter on a gold set: accuracy, coverage split, round trip, throughput.

    Rows marked ``uncertain`` are never scored. By default the remaining rows
    are scored and the hand_written subset is scored alongside for comparison;
    ``--trusted`` scores only that subset.
    """
    from pravapis.metrics import HAND_WRITTEN, UNCERTAIN, evaluate, read_gold, read_gold_rows

    converter = _converter(config)
    rows = read_gold_rows(gold)
    n_uncertain = sum(r.provenance == UNCERTAIN for r in rows)
    pairs = read_gold(gold, trusted_only=trusted)
    subset = "hand_written only (--trusted)" if trusted else "all except uncertain"
    console.print(f"lexicon: {converter.lexicon_origin}")
    console.print(
        f"gold rows: {len(rows)} · [yellow]skipped {n_uncertain} uncertain[/yellow]"
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
    for d in directions:
        rep = evaluate(converter, pairs, d, error_limit=show_errors)
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
        headline = Table(title="headline (vs do-nothing baseline)")
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
            tr = evaluate(converter, trusted_pairs, d, error_limit=0, round_trip=False)
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


@app.command()
def version() -> None:
    console.print(f"pravapis {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
