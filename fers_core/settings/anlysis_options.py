from typing import Optional
from ..settings.enums import AnalysisOrder, Dimensionality, RigidStrategy


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

    def to_dict(self):
        return {
            "id": self.analysis_options_id,
            "solve_loadcases": self.solve_loadcases,
            "solver": self.solver,
            "tolerance": self.tolerance,
            "max_iterations": self.max_iterations,
            "dimensionality": self.dimensionality.value,
            "order": self.order.value,
            "rigid_strategy": self.rigid_strategy.value,
            "axial_slack": self.axial_slack,
        }

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
        )
