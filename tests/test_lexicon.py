from __future__ import annotations

from pathlib import Path

import pytest

from belnorm.lexicon.builder import (
    align_corpora,
    build_both,
    build_trie,
    load_lexicon_file,
    read_tsv_pairs,
    save_lexicon,
    validate_entries,
)
from belnorm.lexicon.store import Lexicon
from belnorm.types import Orthography

N2T = Orthography.TARASKIEVICA
T2N = Orthography.NARKAMAUKA


def test_read_tsv_pairs_skips_comments_and_sanitizes(tmp_path: Path) -> None:
    tsv = tmp_path / "x.tsv"
    tsv.write_text("# c\n\nклас\tкляса\nз'ява \tзьява\n", encoding="utf-8")
    assert list(read_tsv_pairs(tsv)) == [("клас", "кляса"), ("з’ява", "зьява")]


def test_read_tsv_pairs_rejects_bad_rows(tmp_path: Path) -> None:
    tsv = tmp_path / "x.tsv"
    tsv.write_text("клас кляса\n", encoding="utf-8")
    with pytest.raises(ValueError, match="two tab-separated"):
        list(read_tsv_pairs(tsv))


def test_validate_entries() -> None:
    problems = validate_entries(
        [("клас", "кляса"), ("", "x"), ("a b", "c"), ("клас", "клясы"), ("привет", "привет")]
    )
    messages = [p.message for p in problems]
    assert any("empty" in m for m in messages)
    assert any("whitespace" in m for m in messages)
    assert any("conflicts" in m for m in messages)
    assert any("non-Belarusian" in m for m in messages)
    assert {p.severity for p in problems} == {"error", "warning"}
    assert not validate_entries([("снег", "сьнег")])


def test_build_trie_first_wins() -> None:
    trie = build_trie([("клас", "кляса"), ("клас", "клясы"), ("План", "Плян")])
    assert trie["клас"] == ["кляса".encode()]
    assert trie["план"] == ["плян".encode()]


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    fwd, rev = build_both([("клас", "кляса"), ("мінск", "менск")])
    out = tmp_path / "lex.marisa"
    save_lexicon(fwd, rev, out)
    f2, r2 = load_lexicon_file(out)
    assert f2["клас"] == ["кляса".encode()]
    assert r2["менск"] == ["мінск".encode()]
    lex = Lexicon.load(out)
    assert lex.lookup("клас", N2T) == "кляса"
    assert lex.lookup("менск", T2N) == "мінск"
    assert len(lex) == 2


def test_load_rejects_garbage(tmp_path: Path) -> None:
    bad = tmp_path / "bad.marisa"
    bad.write_bytes(b"nope")
    with pytest.raises(ValueError, match="not a belnorm lexicon"):
        Lexicon.load(bad)


def test_lookup_case_handling() -> None:
    lex = Lexicon.from_pairs([("мінск", "менск"), ("клас", "кляса")])
    assert lex.lookup("Мінск", N2T) is None  # exact lookup is lowercase-only
    assert lex.lookup_ci("Мінск", N2T) == "Менск"
    assert lex.lookup_ci("МІНСК", N2T) == "МЕНСК"
    assert lex.lookup_ci("мінск", N2T) == "менск"
    assert lex.lookup_ci("Менск", T2N) == "Мінск"
    assert lex.lookup_ci("снег", N2T) is None


def test_contains_prefix_identity() -> None:
    lex = Lexicon.from_pairs([("мінск", "менск"), ("мінскі", "менскі"), ("лапа", "лапа")])
    assert "мінск" in lex
    assert "менск" in lex
    assert "Мінск" in lex
    assert "снег" not in lex
    assert lex.prefix_search("мін") == ["мінск", "мінскі"]
    assert lex.prefix_search("м", limit=2) == ["менск", "менскі"]
    assert lex.is_identity("лапа")
    assert lex.is_identity("Лапа")
    assert not lex.is_identity("мінск")


def test_empty_lexicon() -> None:
    lex = Lexicon.empty()
    assert len(lex) == 0
    assert lex.lookup("снег", N2T) is None
    assert "снег" not in lex


def test_bundled_lexicon_loads_and_validates(lexicon: Lexicon, data_dir: Path) -> None:
    assert len(lexicon) > 200
    assert lexicon.lookup_ci("Мінск", N2T) == "Менск"
    assert lexicon.lookup_ci("сістэма", N2T) == "сыстэма"
    pairs: list[tuple[str, str]] = []
    for tsv in sorted((data_dir / "lexicon").glob("*.tsv")):
        pairs.extend(read_tsv_pairs(tsv))
    hard = [p for p in validate_entries(pairs) if p.severity == "error"]
    assert not hard, hard


def test_align_corpora(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("Ішоў снег у Мінску.\nдва словы\nтры розныя словы тут\n", encoding="utf-8")
    b.write_text("Ішоў сьнег у Менску.\nдва\nтры розныя словы тут\n", encoding="utf-8")
    assert list(align_corpora(a, b)) == [("снег", "сьнег"), ("мінску", "менску")]
