"""First-class settings for the solver's eigenvalue analyses.

``ModalAnalysisSettings`` maps to the wire ``analysis.modal`` object and
``BucklingAnalysisSettings`` to ``analysis.buckling``. Both mirror the style of
:class:`~fers_core.settings.anlysis_options.AnalysisOptions`: plain classes with
typed constructor args, a ``to_dict()`` that omits unset optionals (the Rust
side uses ``skip_serializing_if`` and would reject an explicit ``null``), and a
``from_dict()`` for round-tripping saved documents.
"""

from typing import Any, Optional, Union

from ..settings.enums import MassFormulation


def _parse_mass_formulation(
    value: Union[MassFormulation, str, None],
) -> Optional[MassFormulation]:
    """Normalize a mass formulation to the enum (case-insensitive for strings)."""
    if value is None or isinstance(value, MassFormulation):
        return value
    raw = str(value).upper()
    for member in MassFormulation:
        if member.value == raw or member.name == raw:
            return member
    raise ValueError(
        f"Invalid mass_formulation {value!r}; expected one of {[m.value for m in MassFormulation]}"
    )


class ModalAnalysisSettings:
    """Natural-frequency (modal) analysis request (wire: ``analysis.modal``).

    Args:
        num_modes: Number of natural modes (lowest frequencies) to extract (>= 1).
        mass_formulation: Mass-matrix formulation. Defaults to
            ``MassFormulation.CONSISTENT``; also accepts the wire strings
            (``"CONSISTENT"``/``"LUMPED"``, case-insensitive). Pass ``None`` to
            omit it and let the solver apply its own default.
        tolerance: Eigen convergence tolerance. Omitted when ``None`` (solver
            default 1e-6).
        max_iterations: Maximum subspace-iteration sweeps. Omitted when ``None``
            (solver default 100).
    """

    def __init__(
        self,
        num_modes: int = 6,
        mass_formulation: Union[MassFormulation, str, None] = MassFormulation.CONSISTENT,
        tolerance: Optional[float] = None,
        max_iterations: Optional[int] = None,
    ):
        if int(num_modes) < 1:
            raise ValueError(f"num_modes must be >= 1, got {num_modes}")
        self.num_modes = int(num_modes)
        self.mass_formulation = _parse_mass_formulation(mass_formulation)
        self.tolerance = float(tolerance) if tolerance is not None else None
        self.max_iterations = int(max_iterations) if max_iterations is not None else None

    def to_dict(self) -> dict:
        data: dict = {"num_modes": self.num_modes}
        # Optionals are only emitted when set (Rust: skip_serializing_if /
        # solver defaults apply when absent).
        if self.mass_formulation is not None:
            data["mass_formulation"] = self.mass_formulation.value
        if self.tolerance is not None:
            data["tolerance"] = self.tolerance
        if self.max_iterations is not None:
            data["max_iterations"] = self.max_iterations
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ModalAnalysisSettings":
        return cls(
            num_modes=data.get("num_modes", 6),
            mass_formulation=data.get("mass_formulation"),
            tolerance=data.get("tolerance"),
            max_iterations=data.get("max_iterations"),
        )


class BucklingAnalysisSettings:
    """Linear (eigenvalue) buckling analysis request (wire: ``analysis.buckling``).

    Args:
        reference: The load whose first-order stress state drives the geometric
            stiffness. Accepts a ``LoadCase`` or ``LoadCombination`` object, an
            already-tagged dict (``{"LoadCase": id}`` / ``{"LoadCombination": id}``),
            or a ``(kind, id)`` tuple where kind is ``"LoadCase"`` /
            ``"LoadCombination"`` (case/underscore-insensitive). The returned
            eigenvalue is the critical load factor `alpha_cr` of that load.
        num_modes: Number of buckling modes (lowest positive critical factors)
            to extract (>= 1).
        tolerance: Eigen convergence tolerance. Omitted when ``None`` (solver
            default 1e-6).
        max_iterations: Maximum subspace-iteration sweeps. Omitted when ``None``
            (solver default 100).
    """

    _REFERENCE_KINDS = {
        "loadcase": "LoadCase",
        "load_case": "LoadCase",
        "loadcombination": "LoadCombination",
        "load_combination": "LoadCombination",
    }

    def __init__(
        self,
        reference: Any,
        num_modes: int = 1,
        tolerance: Optional[float] = None,
        max_iterations: Optional[int] = None,
    ):
        if int(num_modes) < 1:
            raise ValueError(f"num_modes must be >= 1, got {num_modes}")
        self.num_modes = int(num_modes)
        # Normalized eagerly so invalid references fail at author time, not at
        # serialization time; to_dict() re-normalizes in case the attribute was
        # reassigned afterwards.
        self.reference = self._normalize_reference(reference)
        self.tolerance = float(tolerance) if tolerance is not None else None
        self.max_iterations = int(max_iterations) if max_iterations is not None else None

    @classmethod
    def _normalize_reference(cls, reference: Any) -> dict:
        """Normalize any accepted reference form to the externally-tagged wire
        dict ``{"LoadCase": <id>}`` / ``{"LoadCombination": <id>}``."""
        # Lazy imports keep this settings module free of load-module cycles.
        from ..loads.loadcase import LoadCase
        from ..loads.loadcombination import LoadCombination

        if isinstance(reference, LoadCase):
            return {"LoadCase": int(reference.id)}
        if isinstance(reference, LoadCombination):
            return {"LoadCombination": int(reference.id)}
        if isinstance(reference, dict):
            if len(reference) == 1:
                key, value = next(iter(reference.items()))
                if key in ("LoadCase", "LoadCombination"):
                    return {key: int(value)}
            raise ValueError(
                "Buckling reference dict must be externally tagged as "
                f'{{"LoadCase": id}} or {{"LoadCombination": id}}, got {reference!r}'
            )
        if isinstance(reference, (tuple, list)) and len(reference) == 2:
            kind_raw, ref_id = reference
            kind = cls._REFERENCE_KINDS.get(str(kind_raw).lower())
            if kind is None:
                raise ValueError(
                    f'Unknown buckling reference kind {kind_raw!r}; expected "LoadCase" or "LoadCombination"'
                )
            return {kind: int(ref_id)}
        raise TypeError(
            "Buckling reference must be a LoadCase, LoadCombination, tagged dict, "
            f"or (kind, id) tuple, got {type(reference).__name__}"
        )

    def to_dict(self) -> dict:
        data: dict = {
            "num_modes": self.num_modes,
            "reference": self._normalize_reference(self.reference),
        }
        # Optionals are only emitted when set (Rust: skip_serializing_if /
        # solver defaults apply when absent).
        if self.tolerance is not None:
            data["tolerance"] = self.tolerance
        if self.max_iterations is not None:
            data["max_iterations"] = self.max_iterations
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "BucklingAnalysisSettings":
        return cls(
            reference=data["reference"],
            num_modes=data.get("num_modes", 1),
            tolerance=data.get("tolerance"),
            max_iterations=data.get("max_iterations"),
        )
