from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

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


# A real dataclass. These annotations carried `field(default_factory=...)` on a
# plain class, which does nothing: `SingleResults()` took no arguments at all
# (breaking `ResultsBundle.from_raw_dict`, which calls it with keywords), and
# every default read back as a `dataclasses.Field` object rather than a dict.
@dataclass
class SingleResults:
    name: str = ""
    displacement_nodes: Dict[str, NodeDisplacement] = field(default_factory=dict)
    reaction_nodes: Dict[str, ReactionNodeResult] = field(default_factory=dict)
    member_results: Dict[str, MemberResult] = field(default_factory=dict)
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

    @classmethod
    def from_pydantic(cls, pyd_results: Any) -> "SingleResults":
        name_value = getattr(pyd_results, "name", None)
        displacement_map: Dict[str, NodeDisplacement] = {}
        for key, value in (getattr(pyd_results, "displacement_nodes", {}) or {}).items():
            displacement_map[str(key)] = NodeDisplacement.from_pydantic(value)

        reaction_map: Dict[str, ReactionNodeResult] = {}
        for key, value in (getattr(pyd_results, "reaction_nodes", {}) or {}).items():
            reaction_map[str(key)] = ReactionNodeResult.from_pydantic(value)

        member_map: Dict[str, MemberResult] = {}
        for key, value in (getattr(pyd_results, "member_results", {}) or {}).items():
            member_map[str(key)] = MemberResult.from_pydantic(value)

        plate_map: Dict[str, PlateResult] = {}
        for key, value in (getattr(pyd_results, "plate_results", {}) or {}).items():
            plate_map[str(key)] = PlateResult.from_pydantic(value)

        summary_pyd = getattr(pyd_results, "summary", None)
        summary_ = ResultsSummary.from_pydantic(summary_pyd) if summary_pyd else None

        # result_type can be ResultType RootModel; store as a plain dict for stability
        result_type_pyd = getattr(pyd_results, "result_type", None)
        result_type_dict: Optional[Dict[str, Any]] = None
        if result_type_pyd is not None:
            # tolerant try: pydantic v1 has .dict(), v2 has .model_dump(), RootModel has .root
            try:
                result_type_dict = (
                    result_type_pyd.model_dump()  # type: ignore[attr-defined]
                    if hasattr(result_type_pyd, "model_dump")
                    else result_type_pyd.dict()  # type: ignore[attr-defined]
                )
            except Exception:
                result_type_dict = {"value": getattr(result_type_pyd, "root", None)}

        unity_checks_value = getattr(pyd_results, "unity_checks", None)
        if hasattr(unity_checks_value, "model_dump"):
            unity_checks_value = unity_checks_value.model_dump()  # type: ignore[attr-defined]
        elif hasattr(unity_checks_value, "dict"):
            unity_checks_value = unity_checks_value.dict()  # type: ignore[attr-defined]

        instance = cls()
        instance.name = name_value if name_value is not None else ""
        instance.displacement_nodes = displacement_map
        instance.reaction_nodes = reaction_map
        instance.member_results = member_map
        instance.plate_results = plate_map
        instance.summary = summary_
        instance.result_type = result_type_dict
        instance.unity_checks = unity_checks_value
        instance.errors_and_warnings = _to_plain(getattr(pyd_results, "errors_and_warnings", None))
        instance.solver_diagnostics = _to_plain(getattr(pyd_results, "solver_diagnostics", None))
        return instance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "displacement_nodes": {k: v.to_dict() for k, v in self.displacement_nodes.items()},
            "reaction_nodes": {k: v.to_dict() for k, v in self.reaction_nodes.items()},
            "member_results": {k: v.to_dict() for k, v in self.member_results.items()},
            "plate_results": {k: v.to_dict() for k, v in self.plate_results.items()},
            "summary": self.summary.to_dict() if self.summary else None,
            "result_type": self.result_type,
            "unity_checks": self.unity_checks,
            "errors_and_warnings": self.errors_and_warnings,
            "solver_diagnostics": self.solver_diagnostics,
        }
