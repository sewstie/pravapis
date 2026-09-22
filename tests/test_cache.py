from __future__ import annotations

from pravapis.api.cache import ResponseCache, cache_key, etag_for
from pravapis.types import Orthography


def test_get_or_set_computes_once_per_key() -> None:
    cache = ResponseCache()
    calls = []

    def compute() -> str:
        calls.append(1)
        return "value"

    key = cache_key("снег", Orthography.TARASKIEVICA, "cyrillic", False, "1.3.0")
    assert cache.get_or_set(key, compute) == "value"
    assert cache.get_or_set(key, compute) == "value"
    assert len(calls) == 1


def test_different_keys_compute_independently() -> None:
    cache = ResponseCache()
    a = cache_key("снег", Orthography.TARASKIEVICA, "cyrillic", False, "1.3.0")
    b = cache_key("сьнег", Orthography.TARASKIEVICA, "cyrillic", False, "1.3.0")
    assert cache.get_or_set(a, lambda: "a") == "a"
    assert cache.get_or_set(b, lambda: "b") == "b"
    assert len(cache) == 2


def test_unresolved_is_part_of_the_key() -> None:
    cache = ResponseCache()
    off = cache_key("без мяне", Orthography.TARASKIEVICA, "cyrillic", False, "1.3.0")
    on = cache_key("без мяне", Orthography.TARASKIEVICA, "cyrillic", True, "1.3.0")
    assert off != on
    cache.get_or_set(off, lambda: "shape without unresolved")
    cache.get_or_set(on, lambda: "shape with unresolved")
    assert len(cache) == 2


def test_data_version_is_part_of_the_key() -> None:
    cache = ResponseCache()
    old = cache_key("снег", Orthography.TARASKIEVICA, "cyrillic", False, "1.3.0")
    new = cache_key("снег", Orthography.TARASKIEVICA, "cyrillic", False, "1.4.0")
    assert old != new
    assert cache.get_or_set(old, lambda: "old answer") == "old answer"
    assert cache.get_or_set(new, lambda: "new answer") == "new answer"


def test_lru_eviction_drops_the_least_recently_used() -> None:
    cache = ResponseCache(maxsize=2)
    a = cache_key("a", Orthography.TARASKIEVICA, "cyrillic", False, "1")
    b = cache_key("b", Orthography.TARASKIEVICA, "cyrillic", False, "1")
    c = cache_key("c", Orthography.TARASKIEVICA, "cyrillic", False, "1")

    cache.get_or_set(a, lambda: "a")
    cache.get_or_set(b, lambda: "b")
    cache.get_or_set(a, lambda: "a-again")  # touch a, so b becomes the LRU entry
    cache.get_or_set(c, lambda: "c")  # over maxsize=2: evicts b (LRU), not a

    calls: list[int] = []
    cache.get_or_set(a, lambda: calls.append(1) or "a-recomputed")
    assert calls == []  # a survived eviction: it was touched more recently than b

    calls = []
    cache.get_or_set(b, lambda: calls.append(1) or "b-recomputed")
    assert calls == [1]  # b had to be recomputed: it was evicted


def test_etag_is_deterministic_and_key_sensitive() -> None:
    key1 = cache_key("снег", Orthography.TARASKIEVICA, "cyrillic", False, "1.3.0")
    key2 = cache_key("снег", Orthography.TARASKIEVICA, "cyrillic", False, "1.3.0")
    key3 = cache_key("снег", Orthography.TARASKIEVICA, "cyrillic", True, "1.3.0")
    assert etag_for(key1) == etag_for(key2)
    assert etag_for(key1) != etag_for(key3)
