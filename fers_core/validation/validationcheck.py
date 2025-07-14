from typing import Optional, Dict, Any, List, Union

from ..loads.loadcombination import LoadCombination
from ..validation.checktype import CheckType
from ..nodes.node import Node
from ..members.member import Member
from ..members.memberset import MemberSet


class ValidationCheck:
    """
    Represents a validation check definition that can compare various performance measures
    (like deflection, bending moment, or axial force) against specified limits.

    Attributes:
        id (int): Unique identifier for the check.
        check_type (CheckType): The type of check (e.g., global_deflection, local_deflection, bending_moment,
            axial_force, etc.).
        targets (List[Union[Node, Member, MemberSet]]): The elements the check applies to.
        conditions (Dict[str, float]): A dictionary mapping performance measure names to their maximum
            allowable values. For example, {"deflection_y": 25.0} or {"bending_moment": 10000.0}.
        load_combinations (List[LoadCombination]): The load combinations for which this check should run.
    """

    _validation_check_counter = 1

    def __init__(
        self,
        check_type: CheckType,
        targets: List[Union[Node, Member, MemberSet]],
        conditions: Optional[Dict[str, float]] = None,
        load_combinations: Optional[List[LoadCombination]] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id or ValidationCheck._counter
        if id is None:
            ValidationCheck._counter += 1

        self.check_type = check_type

        self.targets = targets
        self.load_combinations = load_combinations if load_combinations is not None else []
        self.conditions = conditions if conditions is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the validation check into a dictionary.
        """
        return {
            "id": self.id,
            "check_type": self.check_type.value,
            "conditions": self.conditions,
            "targets": [str(target) for target in self.targets],
            "load_combinations": [lc.to_dict() for lc in self.load_combinations],
        }
