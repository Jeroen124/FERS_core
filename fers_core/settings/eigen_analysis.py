"""First-class settings for the solver's eigenvalue analyses.

``ModalAnalysisSettings`` maps to the wire ``analysis.modal`` object and
``BucklingAnalysisSettings`` to ``analysis.buckling``. Both mirror the style of
:class:`~fers_core.settings.anlysis_options.AnalysisOptions`: plain classes with
typed constructor args, a ``to_dict()`` that omits unset optionals (the Rust
side uses ``skip_serializing_if`` and would reject an explicit ``null``), and a
``from_dict()`` for round-tripping saved documents.
"""

from typing import Any, Optional, Sequence, Union

from ..settings.enums import MassFormulation


_REFERENCE_KINDS = {
    "loadcase": "LoadCase",
    "load_case": "LoadCase",
    "loadcombination": "LoadCombination",
    "load_combination": "LoadCombination",
}


def _normalize_eigen_reference(reference: Any, *, label: str = "reference") -> dict:
    """Normalize any accepted reference form to the externally-tagged wire dict
    ``{"LoadCase": <id>}`` / ``{"LoadCombination": <id>}``.

    Shared by every setting that takes the solver's ``EigenLoadRef``: the
    buckling reference(s) and the modal/seismic ``stiffness_reference``.
    """
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
            f"{label} dict must be externally tagged as "
            f'{{"LoadCase": id}} or {{"LoadCombination": id}}, got {reference!r}'
        )
    if isinstance(reference, (tuple, list)) and len(reference) == 2:
        kind_raw, ref_id = reference
        kind = _REFERENCE_KINDS.get(str(kind_raw).lower())
        if kind is None:
            raise ValueError(f'Unknown {label} kind {kind_raw!r}; expected "LoadCase" or "LoadCombination"')
        return {kind: int(ref_id)}
    raise TypeError(
        f"{label} must be a LoadCase, LoadCombination, tagged dict, "
        f"or (kind, id) tuple, got {type(reference).__name__}"
    )


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
        stiffness_reference: Load state at which force-dependent stiffness is
            linearized (engine >= 0.2.52). With a reference, StiffnessCurve
            supports and member hinges enter the modal K at their secant under
            that load, and tension/compression members at that load's
            engagement state, instead of at force = 0. Accepts the same forms
            as a buckling reference. Omitted (``None``) keeps the historical
            zero-force linearization.
        include_geometric_stiffness: Add the reference state's geometric
            (stress) stiffness to the modal K, so compression lowers the
            frequencies (engine >= 0.2.52). **Requires**
            ``stiffness_reference``; the solver errors without it, and so does
            this class, at author time.
    """

    def __init__(
        self,
        num_modes: int = 6,
        mass_formulation: Union[MassFormulation, str, None] = MassFormulation.CONSISTENT,
        tolerance: Optional[float] = None,
        max_iterations: Optional[int] = None,
        stiffness_reference: Any = None,
        include_geometric_stiffness: Optional[bool] = None,
    ):
        if int(num_modes) < 1:
            raise ValueError(f"num_modes must be >= 1, got {num_modes}")
        self.num_modes = int(num_modes)
        self.mass_formulation = _parse_mass_formulation(mass_formulation)
        self.tolerance = float(tolerance) if tolerance is not None else None
        self.max_iterations = int(max_iterations) if max_iterations is not None else None
        self.stiffness_reference = (
            _normalize_eigen_reference(stiffness_reference, label="stiffness_reference")
            if stiffness_reference is not None
            else None
        )
        self.include_geometric_stiffness = (
            bool(include_geometric_stiffness) if include_geometric_stiffness is not None else None
        )
        # Mirror the solver's own guard, but fail here so the message arrives
        # before a solve is spent: K_g is the stress state of a specific load.
        if self.include_geometric_stiffness and self.stiffness_reference is None:
            raise ValueError(
                "include_geometric_stiffness requires a stiffness_reference — the "
                "geometric stiffness is the stress state of a specific load."
            )

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
        if self.stiffness_reference is not None:
            data["stiffness_reference"] = _normalize_eigen_reference(
                self.stiffness_reference, label="stiffness_reference"
            )
        if self.include_geometric_stiffness is not None:
            data["include_geometric_stiffness"] = self.include_geometric_stiffness
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ModalAnalysisSettings":
        return cls(
            num_modes=data.get("num_modes", 6),
            mass_formulation=data.get("mass_formulation"),
            tolerance=data.get("tolerance"),
            max_iterations=data.get("max_iterations"),
            stiffness_reference=data.get("stiffness_reference"),
            include_geometric_stiffness=data.get("include_geometric_stiffness"),
        )


class BucklingAnalysisSettings:
    """Linear (eigenvalue) buckling analysis request (wire: ``analysis.buckling``).

    Exactly one reference form must be given: ``reference`` (single),
    ``references`` (explicit list), or ``all_combinations=True`` (every load
    combination in the model). Each reference runs as its own analysis with its
    own StiffnessCurve linearization and geometric stiffness; with more than
    one, per-run results arrive in ``results.buckling_runs`` and
    ``results.buckling`` carries the first successful run.

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
        references: Explicit list of reference loads, each analysed
            independently (engine >= 0.2.52). Same accepted forms as
            ``reference``. Must be non-empty.
        all_combinations: Analyse every load combination in the model
            (engine >= 0.2.52).
        member_effective_lengths: Ask for per-member critical-load-method
            effective lengths (engine >= 0.2.52). Off by default; the output
            adds two entries per member.
        participation_threshold: Minimum member-set share of the
            geometric-stiffness quadratic for a mode to be considered relevant
            to a member's effective length (solver default 0.05).
    """

    # Kept as a class attribute for backwards compatibility; the shared
    # module-level table is the source of truth.
    _REFERENCE_KINDS = _REFERENCE_KINDS

    def __init__(
        self,
        reference: Any = None,
        num_modes: int = 1,
        tolerance: Optional[float] = None,
        max_iterations: Optional[int] = None,
        references: Optional[Sequence[Any]] = None,
        all_combinations: Optional[bool] = None,
        member_effective_lengths: Optional[bool] = None,
        participation_threshold: Optional[float] = None,
    ):
        if int(num_modes) < 1:
            raise ValueError(f"num_modes must be >= 1, got {num_modes}")
        self.num_modes = int(num_modes)

        # Exactly one reference form. The solver applies a precedence
        # (all_combinations > references > reference) but specifying two here
        # is far more likely to be a mistake than an intent, so it is rejected
        # at author time rather than silently resolved.
        given = [
            name
            for name, value in (
                ("reference", reference),
                ("references", references),
                ("all_combinations", all_combinations if all_combinations else None),
            )
            if value is not None
        ]
        if not given:
            raise ValueError(
                "Buckling settings need a reference load: pass `reference`, a non-empty "
                "`references` list, or `all_combinations=True`."
            )
        if len(given) > 1:
            raise ValueError(
                f"Buckling settings take exactly one reference form, got {given}. "
                "Use `reference`, `references`, or `all_combinations=True`."
            )

        if references is not None:
            if isinstance(references, (str, bytes)) or not isinstance(references, Sequence):
                raise TypeError(
                    f"`references` must be a sequence of references, got {type(references).__name__}"
                )
            if len(references) == 0:
                raise ValueError("`references` must not be empty; pass at least one reference or omit it.")
            self.references: Optional[list] = [
                _normalize_eigen_reference(r, label="buckling reference") for r in references
            ]
        else:
            self.references = None

        # Normalized eagerly so invalid references fail at author time, not at
        # serialization time; to_dict() re-normalizes in case the attribute was
        # reassigned afterwards.
        self.reference = (
            _normalize_eigen_reference(reference, label="Buckling reference")
            if reference is not None
            else None
        )
        self.all_combinations = bool(all_combinations) if all_combinations is not None else None
        self.member_effective_lengths = (
            bool(member_effective_lengths) if member_effective_lengths is not None else None
        )
        self.participation_threshold = (
            float(participation_threshold) if participation_threshold is not None else None
        )
        self.tolerance = float(tolerance) if tolerance is not None else None
        self.max_iterations = int(max_iterations) if max_iterations is not None else None

    @classmethod
    def _normalize_reference(cls, reference: Any) -> dict:
        """Backwards-compatible alias for :func:`_normalize_eigen_reference`."""
        return _normalize_eigen_reference(reference, label="Buckling reference")

    def to_dict(self) -> dict:
        data: dict = {"num_modes": self.num_modes}
        # Optionals are only emitted when set (Rust: skip_serializing_if /
        # solver defaults apply when absent).
        if self.reference is not None:
            data["reference"] = _normalize_eigen_reference(self.reference, label="Buckling reference")
        if self.references is not None:
            data["references"] = [
                _normalize_eigen_reference(r, label="buckling reference") for r in self.references
            ]
        if self.all_combinations is not None:
            data["all_combinations"] = self.all_combinations
        if self.member_effective_lengths is not None:
            data["member_effective_lengths"] = self.member_effective_lengths
        if self.participation_threshold is not None:
            data["participation_threshold"] = self.participation_threshold
        if self.tolerance is not None:
            data["tolerance"] = self.tolerance
        if self.max_iterations is not None:
            data["max_iterations"] = self.max_iterations
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "BucklingAnalysisSettings":
        # A stored document may legitimately carry more than one reference form
        # (the solver resolves them by precedence), so resolve it the same way
        # here rather than tripping the stricter constructor check.
        all_combinations = data.get("all_combinations")
        references = data.get("references")
        reference = data.get("reference")
        if all_combinations:
            references = None
            reference = None
        elif references:
            reference = None
        return cls(
            reference=reference,
            num_modes=data.get("num_modes", 1),
            tolerance=data.get("tolerance"),
            max_iterations=data.get("max_iterations"),
            references=references,
            all_combinations=all_combinations,
            member_effective_lengths=data.get("member_effective_lengths"),
            participation_threshold=data.get("participation_threshold"),
        )
