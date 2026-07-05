from enum import Enum


class AnalysisOrder(Enum):
    # Values are the canonical solver/OpenAPI wire tokens (the solver also accepts
    # the legacy "Linear"/"Nonlinear" spellings via serde aliases).
    LINEAR = "LINEAR"
    NONLINEAR = "NONLINEAR"


class Dimensionality(Enum):
    TWO_DIMENSIONAL = "2D"
    THREE_DIMENSIONAL = "3D"


class RigidStrategy(Enum):
    # Canonical solver/OpenAPI wire tokens (legacy "Linear_MPC"/"Rigid_Member"
    # still accepted by the solver via serde aliases).
    LINEAR_MPC = "LinearMpc"
    RIGID_MEMBER = "RigidMember"


class NonlinearMethod(Enum):
    """Nonlinear solver formulation for a second-order (``NONLINEAR``) analysis.

    Values match the Rust ``NonlinearMethod`` enum (serialized ``UPPERCASE``).
    Only affects nonlinear solves; the solver default is ``COROTATIONAL``.
    """

    P_DELTA = "P_DELTA"
    COROTATIONAL = "COROTATIONAL"


class PdeltaFormulation(Enum):
    """Geometric-stiffness (K_g) formulation for P-Delta analysis.

    Values match the Rust ``PdeltaFormulation`` enum. ``CONSISTENT`` (solver
    default) uses the full Przemieniecki K_g; ``SIMPLIFIED`` uses P/L-only
    diagonal terms, matching most commercial solvers.
    """

    CONSISTENT = "CONSISTENT"
    SIMPLIFIED = "SIMPLIFIED"


class MassFormulation(Enum):
    """Mass-matrix formulation for a modal (natural-frequency) analysis.

    Values are the canonical solver/OpenAPI wire tokens (serialized
    ``UPPERCASE``; the solver also accepts legacy ``"Consistent"``/``"Lumped"``
    via serde aliases, but only the uppercase tokens pass the generated input
    schema). ``CONSISTENT`` (solver default) uses the full element-consistent
    mass matrix; ``LUMPED`` uses a diagonal (row-sum) lumping.
    """

    CONSISTENT = "CONSISTENT"
    LUMPED = "LUMPED"


class PdeltaMode(Enum):
    """High-level P-Delta amplification strategy.

    Values match the Rust ``PdeltaMode`` enum. ``FULL`` (solver default)
    amplifies all translational directions; ``IN_PLANE_ONLY`` auto-detects the
    out-of-plane axis from the model bounding box and suppresses it, matching
    the in-plane-only sway approach used by most commercial solvers.
    """

    FULL = "FULL"
    IN_PLANE_ONLY = "IN_PLANE_ONLY"


class ResultBlock(Enum):
    """Selectable result-block groups for ``AnalysisOptions.result_filter``.

    Values match the Rust ``ResultBlock`` enum (engine >= 0.2.48; older
    engines silently ignore ``result_filter`` and return the full output).
    Each token names the member/result JSON block(s) it keeps: when a filter
    list is present, only the listed blocks are emitted — scalar member
    blocks are omitted, list/map blocks (``section_forces``,
    ``internal_force_series``, ``displacement_nodes``, ``reaction_nodes``)
    are emitted empty.
    """

    LOCAL_ENVELOPES = "local_envelopes"
    GLOBAL_ENVELOPES = "global_envelopes"
    LOCAL_END_FORCES = "local_end_forces"
    GLOBAL_END_FORCES = "global_end_forces"
    SECTION_FORCES = "section_forces"
    INTERNAL_FORCE_SERIES = "internal_force_series"
    LOCAL_DISPLACEMENTS = "local_displacements"
    NODE_DISPLACEMENTS = "node_displacements"
    REACTIONS = "reactions"
