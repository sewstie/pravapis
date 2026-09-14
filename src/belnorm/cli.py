"""Command-line interface (typer + rich).

belnorm convert "снег" --to taraskievica
belnorm convert --file in.txt --out out.txt --to narkamauka
echo "снег" | belnorm convert --to t
belnorm explain "сімвал" --to taraskievica
belnorm build-lexicon data/lexicon/ --out data/lexicon.marisa
belnorm train data/eval/ambiguous.tsv --out data/models/disambig.joblib
belnorm eval data/eval/gold.tsv
belnorm bench --size 10mb
belnorm serve --port 8000
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

from belnorm import __version__
from belnorm.config import Config
from belnorm.pipeline import Converter
from belnorm.types import Method, Orthography

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
) -> None:
    """Convert text between orthographies."""
    direction = _direction(to)
    converter = _converter(config)
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
) -> None:
    """Show how each word was resolved: lexicon hit, rules fired, or model score."""
    direction = _direction(to)
    converter = _converter(config)
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
    from belnorm.lexicon.builder import (
        build_both,
        read_tsv_dir,
        read_tsv_pairs,
        save_lexicon,
        validate_entries,
    )

    pairs = list(read_tsv_dir(src) if src.is_dir() else read_tsv_pairs(src))
    problems = validate_entries(pairs)
    for p in problems:
        errors.print(("[red]" if p.severity == "error" else "[yellow]") + str(p))
    hard = [p for p in problems if p.severity == "error"]
    if hard or (strict and problems):
        errors.print(f"[red]{len(problems)} problem(s); nothing written[/red]")
        raise typer.Exit(1)
    fwd, rev = build_both(pairs)
    save_lexicon(fwd, rev, out)
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
    r"""Train the disambiguation classifier (requires belnorm\[ml])."""
    from belnorm.disambiguate import train as tr
    from belnorm.rules.engine import RuleEngine

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
) -> None:
    """Score the converter on a gold set: accuracy, coverage split, round trip, throughput."""
    from belnorm.metrics import evaluate, read_gold

    converter = _converter(config)
    pairs = read_gold(gold)
    directions = list(Orthography) if direction.lower() == "both" else [_direction(direction)]
    payload: dict[str, object] = {}
    for d in directions:
        rep = evaluate(converter, pairs, d, error_limit=show_errors)
        table = Table(title=f"→ {d.value}: {rep.pairs} pairs, {rep.words} words")
        table.add_column("method")
        table.add_column("count", justify="right")
        table.add_column("share", justify="right")
        table.add_column("accuracy", justify="right")
        for m, s in rep.breakdown.items():
            acc = "" if s.accuracy is None else f"{s.accuracy:.1%}"
            table.add_row(m.value, str(s.count), f"{s.share:.1%}", acc)
        console.print(table)
        console.print(
            f"word accuracy [bold]{rep.accuracy:.1%}[/bold] · sentence accuracy "
            f"{rep.sentence_accuracy:.1%} · misaligned {rep.misaligned}"
            + (f" · round trip {rep.round_trip:.1%}" if rep.round_trip is not None else "")
            + f" · {rep.mb_per_second:.2f} MB/s"
        )
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
            "accuracy": rep.accuracy,
            "sentence_accuracy": rep.sentence_accuracy,
            "round_trip": rep.round_trip,
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
    from belnorm.metrics import read_gold

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
        os.environ["BELNORM_CONFIG"] = str(config)
    uvicorn.run("belnorm.api.main:app", host=host, port=port)


@app.command()
def version() -> None:
    console.print(f"belnorm {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
