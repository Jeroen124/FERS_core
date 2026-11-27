"""
A partly set PlateStiffnessModifiers was written with nulls for the factors left
unset, and the engine refused the model ("invalid type: null, expected f64"). The
round-trip tests never solved, so nothing caught it. An unset factor now stays out
of the JSON, and the engine reads it as 1.0.
"""

from typing import Optional

import pytest

from fers_core import (
    AnalysisOrder,
    FERS,
    LoadCase,
    NodalLoad,
    NodalSupport,
    Node,
    Plate,
    PlateStiffnessModifiers,
)

from tests.common_functions import build_steel_s235


def strip_elongation(modifiers: Optional[PlateStiffnessModifiers]) -> float:
    """Mean elongation (m) of a 2 m x 0.2 m strip, fixed at x = 0, pulled 2 kN along x."""
    model = FERS()
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    steel = build_steel_s235()
    support = NodalSupport()
    length, width, nx = 2.0, 0.20, 10

    columns = []
    for ix in range(nx + 1):
        x = length * ix / nx
        fixed = support if ix == 0 else None
        columns.append(
            (Node(X=x, Y=0.0, Z=0.0, nodal_support=fixed), Node(X=x, Y=width, Z=0.0, nodal_support=fixed))
        )

    for ix in range(nx):
        (n00, n01), (n10, n11) = columns[ix], columns[ix + 1]
        model.add_plate(
            Plate(nodes=[n00, n10, n11], material=steel, thickness=0.01, stiffness_modifiers=modifiers),
            Plate(nodes=[n00, n11, n01], material=steel, thickness=0.01, stiffness_modifiers=modifiers),
        )

    pull = LoadCase(name="Pull")
    for node in columns[-1]:
        NodalLoad(node=node, load_case=pull, magnitude=1000.0, direction=(1.0, 0.0, 0.0))
    model.add_load_case(pull)

    model.run_analysis()
    displacements = model.resultsbundle.loadcases["Pull"].displacement_nodes
    return sum(displacements[str(node.id)].dx for node in columns[-1]) / 2.0


def test_unset_factors_are_left_out_of_the_json():
    assert PlateStiffnessModifiers(membrane=0.5).to_dict() == {"membrane": 0.5}
    assert PlateStiffnessModifiers().to_dict() == {}
    assert PlateStiffnessModifiers(bending=0.0).to_dict() == {"bending": 0.0}


def test_one_factor_set_solves_as_if_the_others_were_one():
    one_set = strip_elongation(PlateStiffnessModifiers(membrane=0.5))
    all_set = strip_elongation(PlateStiffnessModifiers(bending=1.0, membrane=0.5, shear=1.0))
    unmodified = strip_elongation(None)

    assert one_set == pytest.approx(all_set, rel=1e-12)
    # Half the membrane stiffness, twice the stretch: the factor was applied.
    assert one_set == pytest.approx(2.0 * unmodified, rel=1e-6)
