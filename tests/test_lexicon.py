from __future__ import annotations

from pathlib import Path

import pytest

from belnorm.config import Config
from belnorm.lexicon.builder import (
    StaleLexiconError,
    align_corpora,
    build_both,
    build_from_sources,
    build_trie,
    load_lexicon_file,
    read_tsv_pairs,
    save_lexicon,
    sources_digest,
    validate_entries,
)
from belnorm.lexicon.store import Lexicon
from belnorm.pipeline import Converter
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
    save_lexicon(fwd, rev, out, source_digest=bytes(32))
    f2, r2, digest = load_lexicon_file(out)
    assert f2["клас"] == ["кляса".encode()]
    assert r2["менск"] == ["мінск".encode()]
    assert digest == bytes(32)
    lex = Lexicon.load(out)
    assert lex.lookup("клас", N2T) == "кляса"
    assert lex.lookup("менск", T2N) == "мінск"
    assert len(lex) == 2


def _compile(sources: Path, out: Path) -> None:
    save_lexicon(*build_from_sources(sources), out, source_digest=sources_digest(sources))


def test_compiled_lexicon_matching_sources_loads(tmp_path: Path) -> None:
    src = tmp_path / "lexicon"
    src.mkdir()
    (src / "a.tsv").write_text("клас\tкляса\n", encoding="utf-8")
    _compile(src, tmp_path / "lex.marisa")
    assert Lexicon.load(tmp_path / "lex.marisa", sources=src).lookup("клас", N2T) == "кляса"


def test_corrupted_source_hash_fails_loudly(tmp_path: Path) -> None:
    src = tmp_path / "lexicon"
    src.mkdir()
    (src / "a.tsv").write_text("клас\tкляса\n", encoding="utf-8")
    out = tmp_path / "lex.marisa"
    _compile(src, out)
    data = bytearray(out.read_bytes())
    data[len(b"BELNORM2")] ^= 0xFF  # flip the first byte of the stored digest
    out.write_bytes(bytes(data))
    with pytest.raises(StaleLexiconError, match="different sources"):
        Lexicon.load(out, sources=src)


def test_edited_sources_make_compiled_lexicon_stale(tmp_path: Path) -> None:
    # The Фёдар bug: TSV corrected after compiling, compiled file still says Хведар.
    src = tmp_path / "lexicon"
    src.mkdir()
    (src / "names.tsv").write_text("фёдар\tхведар\n", encoding="utf-8")
    out = tmp_path / "lex.marisa"
    _compile(src, out)
    (src / "names.tsv").write_text("# removed: optional form\n", encoding="utf-8")
    with pytest.raises(StaleLexiconError):
        Lexicon.load(out, sources=src)


def test_line_endings_do_not_change_the_digest(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "x.tsv").write_bytes("клас\tкляса\n".encode())
    (b / "x.tsv").write_bytes("клас\tкляса\r\n".encode())
    assert sources_digest(a) == sources_digest(b)


def test_old_container_without_hash_is_stale(tmp_path: Path) -> None:
    old = tmp_path / "old.marisa"
    old.write_bytes(b"BELNORM1" + bytes(8))
    with pytest.raises(StaleLexiconError, match="older belnorm"):
        Lexicon.load(old)


def test_converter_never_serves_a_stale_compiled_lexicon(
    tmp_path: Path, config: Config, caplog: pytest.LogCaptureFixture
) -> None:
    src = tmp_path / "lexicon"
    src.mkdir()
    (src / "names.tsv").write_text("фёдар\tхведар\n", encoding="utf-8")
    out = tmp_path / "lex.marisa"
    _compile(src, out)
    (src / "names.tsv").write_text("клас\tкляса\n", encoding="utf-8")
    cfg = config.model_copy(update={"lexicon": out, "lexicon_sources": src})
    with caplog.at_level("WARNING"):
        conv = Converter.from_config(cfg)
    assert "different sources" in caplog.text
    assert "STALE" in conv.lexicon_origin
    assert conv.convert("Фёдар і клас", N2T).text == "Фёдар і кляса"
    # without the sources there is nothing correct to serve: fail
    (src / "names.tsv").unlink()
    src.rmdir()
    cfg_missing = config.model_copy(update={"lexicon": tmp_path / "old.marisa"})
    (tmp_path / "old.marisa").write_bytes(b"BELNORM1" + bytes(8))
    with pytest.raises(StaleLexiconError):
        Converter.from_config(cfg_missing)


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
