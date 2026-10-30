"""JSON parsing that preserves duplicate-key metadata for validation."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


class JsonObject(Mapping[str, object]):
    """A JSON object that keeps raw key occurrences and a last-wins view.

    ``pairs`` preserves every occurrence in document order, ``duplicates``
    records each key's second and later occurrences, and normal mapping access
    uses the collapsed last-wins value, matching standard JSON semantics.
    """

    __slots__ = ("_collapsed", "_duplicates", "_pairs")

    def __init__(self, pairs: Sequence[tuple[str, object]]) -> None:
        raw_pairs = tuple(pairs)
        collapsed: dict[str, object] = {}
        duplicates: list[str] = []
        for key, value in raw_pairs:
            if key in collapsed:
                duplicates.append(key)
            collapsed[key] = value
        self._pairs = raw_pairs
        self._duplicates = tuple(duplicates)
        self._collapsed = MappingProxyType(collapsed)

    @property
    def pairs(self) -> tuple[tuple[str, object], ...]:
        """Every key/value occurrence in original document order."""
        return self._pairs

    @property
    def duplicates(self) -> tuple[str, ...]:
        """Keys of every occurrence after the first, in document order."""
        return self._duplicates

    def to_plain(self) -> dict[str, object]:
        """Recursively convert to builtin ``dict``/``list``/scalar values."""
        return {key: _to_plain(value) for key, value in self._collapsed.items()}

    def __getitem__(self, key: str) -> object:
        return self._collapsed[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._collapsed)

    def __len__(self) -> int:
        return len(self._collapsed)


def _to_plain(value: object) -> object:
    if isinstance(value, JsonObject):
        return value.to_plain()
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ParsedJson:
    """Root of a parsed JSON document, whatever its top-level shape."""

    value: object

    def to_plain(self) -> object:
        return _to_plain(self.value)


def _pairs_hook(pairs: list[tuple[str, object]]) -> JsonObject:
    return JsonObject(pairs)


def parse_json_text(text: str) -> ParsedJson:
    """Parse ``text`` so every nested JSON object becomes a ``JsonObject``."""
    return ParsedJson(json.loads(text, object_pairs_hook=_pairs_hook))
