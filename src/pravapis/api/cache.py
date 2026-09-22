"""In-process LRU cache for conversion responses.

Keyed on ``(text, direction, script, unresolved, data_version)``. ``unresolved`` is
part of the key because it changes the response *shape* — an empty list and a
populated one are different payloads for the same text, not two representations of
one answer. ``data_version`` is part of it because the converter's answer for the
same input can change between data versions without a line of code changing, and a
cache that did not know that would keep serving yesterday's data version's answer
after a redeploy. ``script`` is included for the day this cache also fronts
``/v1/transliterate`` (fixed to ``"cyrillic"`` for ``/v1/convert``, which has no
script of its own); only the convert routes use it today.

Per-app-instance, not a bare module-level cache: more than one ``Converter`` can
exist in one process (tests build several, from different configs), and a cache keyed
only on text/direction would silently serve one converter's answer for another's
input. ``create_app`` attaches one fresh :class:`ResponseCache` to ``app.state`` per
app.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Callable
from threading import Lock
from typing import Final, TypeVar

from pravapis.types import Orthography

DEFAULT_MAXSIZE: Final[int] = 4096

CacheKey = tuple[str, str, str, bool, str]
T = TypeVar("T")


def cache_key(
    text: str, direction: Orthography, script: str, unresolved: bool, data_version: str
) -> CacheKey:
    return (text, direction.value, script, unresolved, data_version)


def etag_for(key: CacheKey) -> str:
    """A weak-ish but deterministic ETag: the same key always yields the same tag,
    and a different key (different text, direction, script, unresolved-ness, or data
    version) always yields a different one."""
    digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()
    return f'"{digest[:16]}"'


class ResponseCache:
    """A small thread-safe LRU. Values are whatever the caller computes; this class
    does not know or care what a "response" is."""

    def __init__(self, maxsize: int = DEFAULT_MAXSIZE) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[CacheKey, object] = OrderedDict()
        self._lock = Lock()

    def get_or_set(self, key: CacheKey, compute: Callable[[], T]) -> T:
        with self._lock:
            cached = self._store.get(key)
            if cached is not None or key in self._store:
                self._store.move_to_end(key)
                return cached  # type: ignore[return-value]
        value = compute()
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)
        return value

    def __len__(self) -> int:
        return len(self._store)
