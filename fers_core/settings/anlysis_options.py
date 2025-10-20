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
