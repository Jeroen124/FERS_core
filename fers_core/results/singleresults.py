from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Mapping, Optional

from fers_core.results.compact import (
    KeyIndexCache,
    MemberResultTable,
    MemberResultTableBuilder,
    NodeDisplacementTable,
    NodeDisplacementTableBuilder,
)
from fers_core.results.member import MemberResult
from fers_core.results.plate import PlateResult
from fers_core.results.nodes import NodeDisplacement, ReactionNodeResult
from fers_core.results.resultssummary import ResultsSummary


def _to_plain(value: Any) -> Any:
    """Convert a pydantic model (or list/dict of them) to plain dicts."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    return value


def jsonable(value: Any) -> Any:
    """``value`` with every enum replaced by its wire value.

    The plain dicts carried on result objects come from pydantic's ``model_dump()``,
    which keeps enums as enum objects; ``to_dict()`` output has to survive
    ``json.dumps``, which is what ``save_to_json`` and a second ``run_analysis`` do.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {jsonable(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, tuple):
        return tuple(jsonable(v) for v in value)
    return value


# A real dataclass. These annotations carried `field(default_factory=...)` on a
# plain class, which does nothing: `SingleResults()` took no arguments at all
# (breaking `ResultsBundle.from_raw_dict`, which calls it with keywords), and
# every default read back as a `dataclasses.Field` object rather than a dict.
@dataclass
class SingleResults:
    """The results of one load case or combination. The four maps are keyed by
    node, member or plate id as a string."""

    name: str = ""
    # Loaded results hold these two as read-only tables (fers_core.results.compact):
    # dict-like, but every lookup builds a new object; `.copy()` gives plain dicts.
    displacement_nodes: Mapping[str, NodeDisplacement] = field(default_factory=dict)
    reaction_nodes: Dict[str, ReactionNodeResult] = field(default_factory=dict)
    member_results: Mapping[str, MemberResult] = field(default_factory=dict)
    plate_results: Dict[str, PlateResult] = field(default_factory=dict)
    summary: Optional[ResultsSummary] = None
    result_type: Optional[Dict[str, Any]] = None
    unity_checks: Optional[Dict[str, Any]] = None
    # How this one solve went, as plain dicts mirroring the solver schema.
    # `errors_and_warnings` is empty in the common case; `solver_diagnostics`
    # carries iterations, time and `converged`. Without these a caller cannot
    # tell a converged combination from one the solver had reservations about.
    errors_and_warnings: Optional[Dict[str, Any]] = None
    solver_diagnostics: Optional[Dict[str, Any]] = None
    # The three maps were rebuilt from `results.selections`; to_dict() writes them
    # empty again, as the solver did, since the selections carry the values.
    _from_selections: bool = field(default=False, init=False, repr=False, compare=False)

    @classmethod
    def from_pydantic(cls, pyd_results: Any, _keys: Optional[KeyIndexCache] = None) -> "SingleResults":
        keys = _keys if _keys is not None else KeyIndexCache()
        members = MemberResultTableBuilder(keys.members)
        for key, value in (getattr(pyd_results, "member_results", {}) or {}).items():
            members.add(str(key), value)
        nodes = NodeDisplacementTableBuilder(keys.nodes)
        for key, value in (getattr(pyd_results, "displacement_nodes", {}) or {}).items():
            nodes.add(str(key), value)
        reactions = {
            str(key): ReactionNodeResult.from_pydantic(value)
            for key, value in (getattr(pyd_results, "reaction_nodes", {}) or {}).items()
        }
        plates = {
            str(key): PlateResult.from_pydantic(value)
            for key, value in (getattr(pyd_results, "plate_results", {}) or {}).items()
        }
        return cls._assemble(pyd_results, members.finish(), nodes.finish(), reactions, plates, keys)

    @classmethod
    def _assemble(
        cls,
        pyd_results: Any,
        members: MemberResultTable,
        nodes: NodeDisplacementTable,
        reactions: Dict[str, ReactionNodeResult],
        plates: Dict[str, PlateResult],
        keys: KeyIndexCache,
    ) -> "SingleResults":
        """A loaded result: the tables built so far plus the small fields of ``pyd_results``."""
        keys.remember(members, nodes)
        instance = cls()
        instance.member_results = members
        instance.displacement_nodes = nodes
        instance.reaction_nodes = reactions
        instance.plate_results = plates

        name_value = getattr(pyd_results, "name", None)
        instance.name = name_value if name_value is not None else ""
        summary_pyd = getattr(pyd_results, "summary", None)
        instance.summary = ResultsSummary.from_pydantic(summary_pyd) if summary_pyd else None

        # result_type can be ResultType RootModel; store as a plain dict for stability
        result_type_pyd = getattr(pyd_results, "result_type", None)
        if result_type_pyd is not None:
            # tolerant try: pydantic v1 has .dict(), v2 has .model_dump(), RootModel has .root
            try:
                instance.result_type = (
                    result_type_pyd.model_dump()  # type: ignore[attr-defined]
                    if hasattr(result_type_pyd, "model_dump")
                    else result_type_pyd.dict()  # type: ignore[attr-defined]
                )
            except Exception:
                instance.result_type = {"value": getattr(result_type_pyd, "root", None)}

        unity_checks_value = getattr(pyd_results, "unity_checks", None)
        if hasattr(unity_checks_value, "model_dump"):
            unity_checks_value = unity_checks_value.model_dump()  # type: ignore[attr-defined]
        elif hasattr(unity_checks_value, "dict"):
            unity_checks_value = unity_checks_value.dict()  # type: ignore[attr-defined]
        instance.unity_checks = unity_checks_value
        instance.errors_and_warnings = _to_plain(getattr(pyd_results, "errors_and_warnings", None))
        instance.solver_diagnostics = _to_plain(getattr(pyd_results, "solver_diagnostics", None))
        return instance

    @classmethod
    def from_raw_dict(cls, raw: Mapping[str, Any], _keys: Optional[KeyIndexCache] = None) -> "SingleResults":
        """From parsed JSON without validating it; anything absent reads as empty or zero."""
        keys = _keys if _keys is not None else KeyIndexCache()
        members = MemberResultTableBuilder(keys.members)
        for key, value in (raw.get("member_results") or {}).items():
            members.add_raw(str(key), value)
        nodes = NodeDisplacementTableBuilder(keys.nodes)
        for key, value in (raw.get("displacement_nodes") or {}).items():
            nodes.add_raw(str(key), value)
        member_table, node_table = members.finish(), nodes.finish()
        keys.remember(member_table, node_table)
        return cls(
            name=str(raw.get("name", "")),
            displacement_nodes=node_table,
            reaction_nodes={
                str(k): ReactionNodeResult.from_dict(v) for k, v in (raw.get("reaction_nodes") or {}).items()
            },
            member_results=member_table,
            plate_results={
                str(k): PlateResult.from_dict(v) for k, v in (raw.get("plate_results") or {}).items()
            },
            summary=ResultsSummary.from_dict(raw["summary"]) if raw.get("summary") else None,
            result_type=raw.get("result_type"),
            unity_checks=raw.get("unity_checks"),
            errors_and_warnings=raw.get("errors_and_warnings"),
            solver_diagnostics=raw.get("solver_diagnostics"),
        )

    def to_dict(self) -> Dict[str, Any]:
        selected = self._from_selections
        return {
            "name": self.name,
            "displacement_nodes": {}
            if selected
            else {k: v.to_dict() for k, v in self.displacement_nodes.items()},
            "reaction_nodes": {} if selected else {k: v.to_dict() for k, v in self.reaction_nodes.items()},
            "member_results": {} if selected else {k: v.to_dict() for k, v in self.member_results.items()},
            "plate_results": {k: v.to_dict() for k, v in self.plate_results.items()},
            "summary": self.summary.to_dict() if self.summary else None,
            "result_type": jsonable(self.result_type),
            "unity_checks": jsonable(self.unity_checks),
            "errors_and_warnings": jsonable(self.errors_and_warnings),
            "solver_diagnostics": jsonable(self.solver_diagnostics),
        }
