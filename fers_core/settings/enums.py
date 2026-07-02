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


class PdeltaMode(Enum):
    """High-level P-Delta amplification strategy.

    Values match the Rust ``PdeltaMode`` enum. ``FULL`` (solver default)
    amplifies all translational directions; ``IN_PLANE_ONLY`` auto-detects the
    out-of-plane axis from the model bounding box and suppresses it, matching
    the in-plane-only sway approach used by most commercial solvers.
    """

    FULL = "FULL"
    IN_PLANE_ONLY = "IN_PLANE_ONLY"
