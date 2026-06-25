from typing import List, Optional
from ..settings.enums import (
    AnalysisOrder,
    Dimensionality,
    NonlinearMethod,
    PdeltaFormulation,
    PdeltaMode,
    RigidStrategy,
)


class AnalysisOptions:
    _analysis_options_counter = 1

    def __init__(
        self,
        id: Optional[int] = None,
        solve_loadcases: Optional[bool] = True,
        solver: Optional[str] = "newton_raphson",
        tolerance: Optional[float] = 0.01,
        max_iterations: Optional[int] = 30,
        dimensionality: Optional[Dimensionality] = Dimensionality.THREE_DIMENSIONAL,
        order: Optional[AnalysisOrder] = AnalysisOrder.NONLINEAR,
        rigid_strategy: Optional[RigidStrategy] = RigidStrategy.RIGID_MEMBER,
        axial_slack: Optional[float] = 500,
        include_shear_deformation: Optional[bool] = True,
        include_warping: Optional[bool] = True,
        include_shear_center_coupling: Optional[bool] = True,
        nonlinear_method: Optional[NonlinearMethod] = None,
        pdelta_formulation: Optional[PdeltaFormulation] = None,
        pdelta_mode: Optional[PdeltaMode] = None,
        pdelta_suppress_axes: Optional[List[str]] = None,
        enable_self_weight: Optional[bool] = None,
        gravity_direction: Optional[tuple] = None,
        gravity_factor: Optional[float] = None,
        self_weight_load_case_id: Optional[int] = None,
        include_member_deflected_shape: Optional[bool] = None,
    ):
        self.analysis_options_id = id or AnalysisOptions._analysis_options_counter
        if id is None:
            AnalysisOptions._analysis_options_counter += 1
        self.solve_loadcases = solve_loadcases
        self.solver = solver
        self.tolerance = tolerance
        self.max_iterations = max_iterations
        self.dimensionality = dimensionality
        self.order = order
        self.rigid_strategy = rigid_strategy
        self.axial_slack = axial_slack
        self.include_shear_deformation = include_shear_deformation
        self.include_warping = include_warping
        self.include_shear_center_coupling = include_shear_center_coupling
        # Second-order / P-delta controls. Left as None by default so the solver
        # applies its own defaults (nonlinear_method=COROTATIONAL, pdelta_mode=FULL,
        # pdelta_formulation=CONSISTENT); only emitted when explicitly set.
        self.nonlinear_method = nonlinear_method
        self.pdelta_formulation = pdelta_formulation
        self.pdelta_mode = pdelta_mode
        self.pdelta_suppress_axes = list(pdelta_suppress_axes) if pdelta_suppress_axes is not None else None
        self.enable_self_weight = enable_self_weight
        self.gravity_direction = tuple(gravity_direction) if gravity_direction is not None else None
        self.gravity_factor = float(gravity_factor) if gravity_factor is not None else None
        self.self_weight_load_case_id = self_weight_load_case_id
        # When set, the solver returns each member result's sampled deflected shape
        # (`member_displacements`) for load-exact deformation plots. Off by default.
        self.include_member_deflected_shape = include_member_deflected_shape

    def to_dict(self):
        data = {
            "solve_loadcases": self.solve_loadcases,
            "solver": self.solver,
            "tolerance": self.tolerance,
            "max_iterations": self.max_iterations,
            "dimensionality": self.dimensionality.value,
            "order": self.order.value,
            "rigid_strategy": self.rigid_strategy.value,
            "axial_slack": self.axial_slack,
            "include_shear_deformation": self.include_shear_deformation,
            "include_warping": self.include_warping,
            "include_shear_center_coupling": self.include_shear_center_coupling,
        }
        # Second-order / P-delta controls are only emitted when explicitly set so
        # the solver falls back to its own defaults (each Rust field is
        # `#[serde(default)]` and would reject an explicit null).
        if self.nonlinear_method is not None:
            data["nonlinear_method"] = self.nonlinear_method.value
        if self.pdelta_formulation is not None:
            data["pdelta_formulation"] = self.pdelta_formulation.value
        if self.pdelta_mode is not None:
            data["pdelta_mode"] = self.pdelta_mode.value
        if self.pdelta_suppress_axes is not None:
            data["pdelta_suppress_axes"] = list(self.pdelta_suppress_axes)
        # Self-weight options are only emitted when explicitly set, so the solver
        # falls back to its own defaults (its `enable_self_weight` is a plain bool
        # that rejects an explicit null).
        if self.enable_self_weight is not None:
            data["enable_self_weight"] = self.enable_self_weight
        if self.gravity_direction is not None:
            data["gravity_direction"] = list(self.gravity_direction)
        if self.gravity_factor is not None:
            data["gravity_factor"] = self.gravity_factor
        if self.self_weight_load_case_id is not None:
            data["self_weight_load_case_id"] = self.self_weight_load_case_id
        if self.include_member_deflected_shape is not None:
            data["include_member_deflected_shape"] = self.include_member_deflected_shape
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisOptions":
        """
        Accepts:
        - dimensionality/order/rigid_strategy as either:
          - their enum value (as written by to_dict),
          - their enum name,
          - or already as enum instances.
        """

        def parse_enum(enum_type, raw_value, default):
            if raw_value is None:
                return default
            if isinstance(raw_value, enum_type):
                return raw_value

            # Try by value
            for member in enum_type:
                if member.value == raw_value:
                    return member

            # Try by name (case-insensitive)
            raw_str = str(raw_value).upper()
            for member in enum_type:
                if member.name.upper() == raw_str:
                    return member

            # Fallback to default if nothing matches
            return default

        dimensionality = parse_enum(
            Dimensionality,
            data.get("dimensionality"),
            Dimensionality.THREE_DIMENSIONAL,
        )

        order = parse_enum(
            AnalysisOrder,
            data.get("order"),
            AnalysisOrder.NONLINEAR,
        )

        rigid_strategy = parse_enum(
            RigidStrategy,
            data.get("rigid_strategy"),
            RigidStrategy.RIGID_MEMBER,
        )

        # Second-order / P-delta controls: absent → None (solver default applies).
        nonlinear_method = parse_enum(NonlinearMethod, data.get("nonlinear_method"), None)
        pdelta_formulation = parse_enum(PdeltaFormulation, data.get("pdelta_formulation"), None)
        pdelta_mode = parse_enum(PdeltaMode, data.get("pdelta_mode"), None)

        return cls(
            id=data.get("id"),
            solve_loadcases=data.get("solve_loadcases", True),
            solver=data.get("solver", "newton_raphson"),
            tolerance=data.get("tolerance", 0.01),
            max_iterations=data.get("max_iterations", 30),
            dimensionality=dimensionality,
            order=order,
            rigid_strategy=rigid_strategy,
            axial_slack=data.get("axial_slack", 500),
            include_shear_deformation=data.get("include_shear_deformation", True),
            include_warping=data.get("include_warping", True),
            include_shear_center_coupling=data.get("include_shear_center_coupling", True),
            nonlinear_method=nonlinear_method,
            pdelta_formulation=pdelta_formulation,
            pdelta_mode=pdelta_mode,
            pdelta_suppress_axes=data.get("pdelta_suppress_axes"),
            enable_self_weight=data.get("enable_self_weight"),
            gravity_direction=data.get("gravity_direction"),
            gravity_factor=data.get("gravity_factor"),
            self_weight_load_case_id=data.get("self_weight_load_case_id"),
            include_member_deflected_shape=data.get("include_member_deflected_shape"),
        )
