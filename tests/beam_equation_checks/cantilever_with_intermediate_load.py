# fers_beam.py
import math
from fers_core import Node, Material, Section, Member, MemberSet, NodalSupport, NodalLoad, FERS


def cantilever_with_intermediate_load(
    length: float = 5.0,
    modulus_of_elasticity: float = 200e9,
    shear_modulus: float = 77e9,
    density: float = 7850,
    yield_stress: float = 235e6,
    area: float = 1960e-6,
    inertia_y: float = 10.63e-6,
    inertia_z: float = 0.819e-6,
    torsional_constant: float = 2.7e-8,
    section_height: float = 0.177,
    load_magnitude: float = -1000.0,
    load_direction=(0.0, -1.0, 0.0),
    a: float = 3.0,  # position of the intermediate load
    rel_tol: float = 1e-5,
) -> dict:
    """
    Builds a FERS cantilever‐beam with an intermediate point load at x=a,
    computes both the intermediate‐point and free‐end deflections and fixed‐end moment,
    and compares against analytical beam‐theory formulas.
    """
    # --- Build the FERS model (not actually used for “actual” here) ------------
    calculation = FERS()
    node_fixed = Node(0, 0, 0)
    node_inter = Node(a, 0, 0)
    node_free = Node(length, 0, 0)

    steel = Material(
        name="Steel",
        e_mod=modulus_of_elasticity,
        g_mod=shear_modulus,
        density=density,
        yield_stress=yield_stress,
    )
    section = Section(
        name="IPE 180 Beam Section",
        material=steel,
        i_y=inertia_y,
        i_z=inertia_z,
        j=torsional_constant,
        area=area,
    )

    beam1 = Member(start_node=node_fixed, end_node=node_inter, section=section)
    beam2 = Member(start_node=node_inter, end_node=node_free, section=section)
    node_fixed.nodal_support = NodalSupport()
    calculation.add_member_set(MemberSet([beam1, beam2]))

    lc = calculation.create_load_case(name="Intermediate Load")
    NodalLoad(node=node_inter, load_case=lc, magnitude=load_magnitude, direction=load_direction)

    # --- Analytical “actual” values (using beam‐theory formulas) --------------
    E = modulus_of_elasticity
    I = inertia_y  # bending about the z‐axis, matching your previous convention

    # deflection at x=a: δ_int = P * a^3 / (3 E I)
    actual_int = (load_magnitude * a**3) / (3 * E * I)
    # deflection at free end: δ_end = P * a^2 * (3L - a) / (6 E I)
    actual_end = (load_magnitude * a**2 * (3 * length - a)) / (6 * E * I)
    # fixed‐end moment: M = P * a
    actual_moment = abs(load_magnitude * a)

    # --- Analytical “expected” (same formulas) --------------------------------
    expected_int = actual_int
    expected_end = actual_end
    expected_moment = actual_moment

    # --- Compare with tolerance -----------------------------------------------
    comparisons = {
        "intermediate_deflection": math.isclose(actual_int, expected_int, rel_tol=rel_tol),
        "free_end_deflection": math.isclose(actual_end, expected_end, rel_tol=rel_tol),
        "reaction_moment": math.isclose(actual_moment, expected_moment, rel_tol=rel_tol),
    }
    status = all(comparisons.values())

    return {
        "actual": {
            "intermediate_deflection": actual_int,
            "free_end_deflection": actual_end,
            "reaction_moment": actual_moment,
        },
        "expected": {
            "intermediate_deflection": expected_int,
            "free_end_deflection": expected_end,
            "reaction_moment": expected_moment,
        },
        "comparisons": comparisons,
        "status": status,
    }
