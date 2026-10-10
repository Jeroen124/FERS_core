"""Member and node results held as arrays, not as one object per value.

A member's results used to be ten small objects per load case or combination,
one per force or displacement block, each holding seven floats. On a large model
that is most of what a result costs in memory. Here each block is one ``(n, 7)``
float64 array per load case or combination, and the ``MemberResult`` or
``NodeDisplacement`` a caller sees is built when it is looked up.

Those objects are read-only. An edit would change a copy that the next lookup
replaces, so it raises instead of being lost without a word; ``copy()`` on the
mapping returns ordinary, editable objects.
"""

from __future__ import annotations

from array import array
from collections.abc import Mapping
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import numpy as np

from fers_core.results.member import MemberResult
from fers_core.results.nodes import NodeDisplacement, NodeForces, SectionForce, number

FORCE_COMPONENTS = ("fx", "fy", "fz", "mx", "my", "mz", "bw")
DISPLACEMENT_COMPONENTS = ("dx", "dy", "dz", "rx", "ry", "rz", "warp")
FORCE_BLOCKS = (
    "start_node_forces",
    "end_node_forces",
    "maximums",
    "minimums",
    "local_start_forces",
    "local_end_forces",
    "local_maximums",
    "local_minimums",
)
DISPLACEMENT_BLOCKS = ("local_displacement_start_node", "local_displacement_end_node")
SECTION_SERIES = ("section_forces", "internal_force_series")
# Every field of the generated MemberResult, each stored by exactly one of the
# above or by the two sample fields; test_schema_conformance holds it to that.
MEMBER_FIELDS = (
    FORCE_BLOCKS + DISPLACEMENT_BLOCKS + SECTION_SERIES + ("member_displacements", "member_displacement_peak")
)


# ---------------------------------------------------------------------------
# Read-only result objects
# ---------------------------------------------------------------------------


class _ReadOnly:
    __slots__ = ()

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(_read_only_message(self))

    def __delattr__(self, name: str) -> None:
        raise AttributeError(_read_only_message(self))


def _read_only_message(obj: Any) -> str:
    public = type(obj).__mro__[2].__name__
    return (
        f"{public} objects from a loaded result are read-only: an edit would change a copy that the "
        "next lookup replaces. Call .copy() on member_results or displacement_nodes for editable objects."
    )


class _FrozenNodeForces(_ReadOnly, NodeForces):
    __slots__ = ()


class _FrozenNodeDisplacement(_ReadOnly, NodeDisplacement):
    __slots__ = ()


class _FrozenSectionForce(_ReadOnly, SectionForce):
    __slots__ = ()


class _FrozenMemberResult(_ReadOnly, MemberResult):
    __slots__ = ()


def _make(cls: type, fields: Iterable[Tuple[str, Any]]) -> Any:
    # Bypasses __init__ and __setattr__, which is the only way into a read-only object.
    obj = object.__new__(cls)
    obj.__dict__.update(fields)
    return obj


class _Kinds:
    """The classes and sequence type a lookup builds: read-only, or plain for copy()."""

    __slots__ = (
        "forces",
        "displacement",
        "section",
        "member",
        "sequence",
        "zero_forces",
        "zero_displacement",
    )

    def __init__(self, frozen: bool):
        self.forces = _FrozenNodeForces if frozen else NodeForces
        self.displacement = _FrozenNodeDisplacement if frozen else NodeDisplacement
        self.section = _FrozenSectionForce if frozen else SectionForce
        self.member = _FrozenMemberResult if frozen else MemberResult
        self.sequence = tuple if frozen else list
        zeros = (0.0,) * 7
        if frozen:
            # Shared: nothing can change them.
            forces = _make(self.forces, zip(FORCE_COMPONENTS, zeros))
            displacement = _make(self.displacement, zip(DISPLACEMENT_COMPONENTS, zeros))
            self.zero_forces = lambda: forces
            self.zero_displacement = lambda: displacement
        else:
            self.zero_forces = lambda: _make(NodeForces, zip(FORCE_COMPONENTS, zeros))
            self.zero_displacement = lambda: _make(NodeDisplacement, zip(DISPLACEMENT_COMPONENTS, zeros))


_FROZEN = _Kinds(frozen=True)
_PLAIN = _Kinds(frozen=False)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class KeyIndex:
    """Ids in file order and the row of each.

    One instance is shared by every load case and combination that lists the
    same ids, which on a solved model is nearly all of them.
    """

    __slots__ = ("keys", "rows")

    def __init__(self, keys: Tuple[str, ...]):
        self.keys = keys
        self.rows = {key: row for row, key in enumerate(keys)}


class KeyIndexCache:
    """The last index of each kind, offered to the next load case or combination."""

    __slots__ = ("members", "nodes")

    def __init__(self) -> None:
        self.members: Optional[KeyIndex] = None
        self.nodes: Optional[KeyIndex] = None

    def remember(self, members: "MemberResultTable", nodes: "NodeDisplacementTable") -> None:
        self.members = members._index
        self.nodes = nodes._index


_Series = Optional[Tuple[array, np.ndarray]]


class MemberResultTable(Mapping):
    """Member results of one load case or combination, by member id.

    Behaves like the ``dict`` it replaces, except that it cannot be changed and
    every lookup builds a new, read-only ``MemberResult``. ``copy()`` returns the
    old shape: a plain dict of editable objects, at the old memory cost.
    """

    __slots__ = (
        "_index",
        "_forces",
        "_displacements",
        "_series",
        "_series_none",
        "_samples",
        "_peaks",
        "_has_peak",
    )

    def __init__(
        self,
        index: KeyIndex,
        forces: Dict[str, np.ndarray],
        displacements: Dict[str, np.ndarray],
        series: Dict[str, _Series],
        series_none: Optional[bytes],
        samples: _Series,
        peaks: Optional[np.ndarray],
        has_peak: Optional[bytes],
    ):
        self._index = index
        self._forces = forces
        self._displacements = displacements
        self._series = series
        # Rows whose internal_force_series was null rather than a list.
        self._series_none = series_none
        self._samples = samples
        self._peaks = peaks
        self._has_peak = has_peak

    def __getitem__(self, key: str) -> MemberResult:
        return self._build(self._index.rows[key], _FROZEN)

    def __iter__(self) -> Iterator[str]:
        return iter(self._index.keys)

    def __reversed__(self) -> Iterator[str]:
        return reversed(self._index.keys)

    def __len__(self) -> int:
        return len(self._index.keys)

    def __contains__(self, key: object) -> bool:
        return key in self._index.rows

    def __repr__(self) -> str:
        return f"<MemberResultTable: {len(self)} members>"

    def copy(self) -> Dict[str, MemberResult]:
        return {key: self._build(row, _PLAIN) for row, key in enumerate(self._index.keys)}

    def _build(self, row: int, kinds: _Kinds) -> MemberResult:
        fields: Dict[str, Any] = {}
        for name in FORCE_BLOCKS:
            block = self._forces.get(name)
            fields[name] = (
                _make(kinds.forces, zip(FORCE_COMPONENTS, block[row].tolist()))
                if block is not None
                else kinds.zero_forces()
            )
        for name in DISPLACEMENT_BLOCKS:
            block = self._displacements.get(name)
            fields[name] = (
                _make(kinds.displacement, zip(DISPLACEMENT_COMPONENTS, block[row].tolist()))
                if block is not None
                else kinds.zero_displacement()
            )
        fields["section_forces"] = kinds.sequence(self._sections("section_forces", row, kinds))
        if self._series_none is not None and self._series_none[row]:
            fields["internal_force_series"] = None
        else:
            fields["internal_force_series"] = kinds.sequence(
                self._sections("internal_force_series", row, kinds)
            )
        fields["member_displacements"] = kinds.sequence(
            (x, (dx, dy, dz)) for x, dx, dy, dz in _rows(self._samples, row)
        )
        if self._has_peak is not None and self._has_peak[row]:
            x, dx, dy, dz = self._peaks[row].tolist()
            fields["member_displacement_peak"] = (x, (dx, dy, dz))
        else:
            fields["member_displacement_peak"] = None
        return _make(kinds.member, fields.items())

    def _sections(self, name: str, row: int, kinds: _Kinds) -> Iterator[SectionForce]:
        for record in _rows(self._series[name], row):
            forces = _make(kinds.forces, zip(FORCE_COMPONENTS, record[1:]))
            yield _make(kinds.section, (("x_frac", record[0]), ("forces", forces)))


def _rows(series: _Series, row: int) -> List[List[float]]:
    if series is None:
        return []
    offsets, values = series
    start, stop = offsets[row], offsets[row + 1]
    return values[start:stop].tolist() if stop > start else []


class NodeDisplacementTable(Mapping):
    """Node displacements of one load case or combination, by node id.

    Behaves like the ``dict`` it replaces; see ``MemberResultTable``.
    """

    __slots__ = ("_index", "_values")

    def __init__(self, index: KeyIndex, values: np.ndarray):
        self._index = index
        self._values = values

    def __getitem__(self, key: str) -> NodeDisplacement:
        row = self._index.rows[key]
        return _make(_FrozenNodeDisplacement, zip(DISPLACEMENT_COMPONENTS, self._values[row].tolist()))

    def __iter__(self) -> Iterator[str]:
        return iter(self._index.keys)

    def __reversed__(self) -> Iterator[str]:
        return reversed(self._index.keys)

    def __len__(self) -> int:
        return len(self._index.keys)

    def __contains__(self, key: object) -> bool:
        return key in self._index.rows

    def __repr__(self) -> str:
        return f"<NodeDisplacementTable: {len(self)} nodes>"

    def copy(self) -> Dict[str, NodeDisplacement]:
        return {
            key: _make(NodeDisplacement, zip(DISPLACEMENT_COMPONENTS, values))
            for key, values in zip(self._index.keys, self._values.tolist())
        }


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _zeros(count: int) -> array:
    return array("d", bytes(8 * count))


def _frozen_array(values: array, width: int) -> np.ndarray:
    if not values:
        return np.empty((0, width))
    out = np.frombuffer(values, dtype=np.float64).reshape(-1, width)
    out.flags.writeable = False
    return out


class _Blocks:
    """Fixed-width rows per named block, grown row by row; rows a block skips stay zero."""

    __slots__ = ("_width", "_data")

    def __init__(self, width: int):
        self._width = width
        self._data: Dict[str, array] = {}

    def put(self, name: str, row: int, values: Sequence[float]) -> None:
        column = self._data.get(name)
        if column is None:
            column = self._data[name] = _zeros(self._width * row)
        else:
            missing = self._width * row - len(column)
            if missing:
                column.extend(_zeros(missing))
        column.extend(values)

    def finish(self, rows: int) -> Dict[str, np.ndarray]:
        out = {}
        for name, column in self._data.items():
            missing = self._width * rows - len(column)
            if missing:
                column.extend(_zeros(missing))
            out[name] = _frozen_array(column, self._width)
        return out


class _RaggedRows:
    """Per-row lists of fixed-width records, as offsets into one value block."""

    __slots__ = ("_width", "_offsets", "_values")

    def __init__(self, width: int):
        self._width = width
        self._offsets = array("q", [0])
        self._values = array("d")

    def put(self, row: int, records: Iterable[Sequence[float]]) -> None:
        for record in records:
            self._values.extend(record)
        offsets = self._offsets
        while len(offsets) <= row:
            offsets.append(offsets[-1])
        offsets.append(len(self._values) // self._width)

    def finish(self, rows: int) -> _Series:
        if not self._values:
            return None
        offsets = self._offsets
        while len(offsets) <= rows:
            offsets.append(offsets[-1])
        return offsets, _frozen_array(self._values, self._width)


class _Flags:
    """Per-row booleans, allocated only once some row is set."""

    __slots__ = ("_bits",)

    def __init__(self) -> None:
        self._bits: Optional[bytearray] = None

    def set(self, row: int) -> None:
        if self._bits is None:
            self._bits = bytearray()
        if len(self._bits) <= row:
            self._bits.extend(bytes(row + 1 - len(self._bits)))
        self._bits[row] = 1

    def finish(self, rows: int) -> Optional[bytes]:
        if self._bits is None:
            return None
        self._bits.extend(bytes(max(0, rows - len(self._bits))))
        return bytes(self._bits)


class _KeyRecorder:
    """Records ids in order, reusing the previous index while the ids match it."""

    __slots__ = ("_previous", "_keys", "_same")

    def __init__(self, previous: Optional[KeyIndex]):
        self._previous = previous
        self._keys: List[str] = []
        self._same = previous is not None

    def add(self, key: str) -> int:
        row = len(self._keys)
        if self._same:
            previous = self._previous.keys
            if row < len(previous) and previous[row] == key:
                key = previous[row]
            else:
                self._same = False
        self._keys.append(key)
        return row

    def finish(self, what: str) -> KeyIndex:
        if self._same and len(self._keys) == len(self._previous.keys):
            return self._previous
        index = KeyIndex(tuple(self._keys))
        if len(index.rows) != len(index.keys):
            raise ValueError(f"duplicate id in {what}")
        return index


def _section_record(section: Any) -> Tuple[float, ...]:
    f = section.forces
    return (section.x_frac, f.fx, f.fy, f.fz, f.mx, f.my, f.mz, number(f.bw))


def _sample_record(sample: Any) -> Tuple[float, float, float, float]:
    d = sample.displacement
    d = getattr(d, "root", d)
    return (sample.x_frac, d[0], d[1], d[2])


def _raw_section_record(section: Mapping[str, Any]) -> Tuple[float, ...]:
    f = section.get("forces") or {}
    return (number(section.get("x_frac")),) + tuple(number(f.get(c)) for c in FORCE_COMPONENTS)


def _raw_sample_record(sample: Mapping[str, Any]) -> Tuple[float, ...]:
    d = sample.get("displacement") or (0.0, 0.0, 0.0)
    return (number(sample.get("x_frac")), number(d[0]), number(d[1]), number(d[2]))


class MemberResultTableBuilder:
    """Collects member results row by row; ``finish`` freezes them into a table."""

    def __init__(self, previous: Optional[KeyIndex] = None):
        self._keys = _KeyRecorder(previous)
        self._forces = _Blocks(7)
        self._displacements = _Blocks(7)
        self._series = {name: _RaggedRows(8) for name in SECTION_SERIES}
        self._series_none = _Flags()
        self._samples = _RaggedRows(4)
        self._peaks = _Blocks(4)
        self._has_peak = _Flags()

    def add(self, key: str, result: Any) -> None:
        """One validated ``MemberResult`` of the generated models."""
        row = self._keys.add(key)
        for name in FORCE_BLOCKS:
            b = getattr(result, name)
            if b is not None:
                self._forces.put(name, row, (b.fx, b.fy, b.fz, b.mx, b.my, b.mz, number(b.bw)))
        for name in DISPLACEMENT_BLOCKS:
            b = getattr(result, name)
            if b is not None:
                self._displacements.put(name, row, (b.dx, b.dy, b.dz, b.rx, b.ry, b.rz, number(b.warp)))
        self._series["section_forces"].put(row, map(_section_record, result.section_forces or ()))
        series = result.internal_force_series
        if series is None:
            self._series_none.set(row)
        self._series["internal_force_series"].put(row, map(_section_record, series or ()))
        self._samples.put(row, map(_sample_record, result.member_displacements or ()))
        if result.member_displacement_peak is not None:
            self._peaks.put("peak", row, _sample_record(result.member_displacement_peak))
            self._has_peak.set(row)

    def add_raw(self, key: str, result: Mapping[str, Any]) -> None:
        """One member result as parsed JSON, unvalidated; anything absent reads as zero."""
        row = self._keys.add(key)
        for name in FORCE_BLOCKS:
            b = result.get(name)
            if b:
                self._forces.put(name, row, tuple(number(b.get(c)) for c in FORCE_COMPONENTS))
        for name in DISPLACEMENT_BLOCKS:
            b = result.get(name)
            if b:
                self._displacements.put(name, row, tuple(number(b.get(c)) for c in DISPLACEMENT_COMPONENTS))
        self._series["section_forces"].put(row, map(_raw_section_record, result.get("section_forces") or ()))
        series = result.get("internal_force_series")
        if series is None:
            self._series_none.set(row)
        self._series["internal_force_series"].put(row, map(_raw_section_record, series or ()))
        self._samples.put(row, map(_raw_sample_record, result.get("member_displacements") or ()))
        peak = result.get("member_displacement_peak")
        if peak:
            self._peaks.put("peak", row, _raw_sample_record(peak))
            self._has_peak.set(row)

    def finish(self) -> MemberResultTable:
        index = self._keys.finish("member_results")
        rows = len(index.keys)
        return MemberResultTable(
            index,
            self._forces.finish(rows),
            self._displacements.finish(rows),
            {name: series.finish(rows) for name, series in self._series.items()},
            self._series_none.finish(rows),
            self._samples.finish(rows),
            self._peaks.finish(rows).get("peak"),
            self._has_peak.finish(rows),
        )


class NodeDisplacementTableBuilder:
    """Collects node displacements row by row; ``finish`` freezes them into a table."""

    def __init__(self, previous: Optional[KeyIndex] = None):
        self._keys = _KeyRecorder(previous)
        self._values = array("d")

    def add(self, key: str, d: Any) -> None:
        """One validated ``NodeDisplacement`` of the generated models."""
        self._keys.add(key)
        self._values.extend((d.dx, d.dy, d.dz, d.rx, d.ry, d.rz, number(d.warp)))

    def add_raw(self, key: str, d: Mapping[str, Any]) -> None:
        self._keys.add(key)
        self._values.extend(number(d.get(c)) for c in DISPLACEMENT_COMPONENTS)

    def finish(self) -> NodeDisplacementTable:
        return NodeDisplacementTable(self._keys.finish("displacement_nodes"), _frozen_array(self._values, 7))
