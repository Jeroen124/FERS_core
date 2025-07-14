# fers_beam.py
import math

from fers_core import Node, Material, Section, Member, MemberSet, NodalSupport, NodalLoad, FERS


def cantilever_with_end_load(
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
    rel_tol: float = 1e-5,
) -> dict:
    """
    Builds a FERS cantilever‐beam model, optionally writes JSON,
    does the FERS calc, and also returns the beam‐theory expected values.
    """
    # --- Build the FERS model ------------------------------------------------
    calculation = FERS()
    node_fixed = Node(0.0, 0.0, 0.0)
    node_free = Node(length, 0.0, 0.0)

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

    beam = Member(start_node=node_fixed, end_node=node_free, section=section)
    support = NodalSupport()
    node_fixed.nodal_support = support

    member_set = MemberSet(members=[beam])
    calculation.add_member_set(member_set)

    load_case = calculation.create_load_case(name="End Load")
    NodalLoad(
        node=node_free,
        load_case=load_case,
        magnitude=load_magnitude,
        direction=load_direction,
    )

    actual_deflection = (load_magnitude * length**3) / (3.0 * modulus_of_elasticity * inertia_y)
    actual_reaction_force_y = -load_magnitude
    actual_reaction_moment_z = abs(load_magnitude * length)
    y_max = section_height / 2.0
    actual_sigma_max = (actual_reaction_moment_z * y_max) / inertia_z

    expected_deflection = (load_magnitude * length**3) / (3.0 * modulus_of_elasticity * inertia_y)
    expected_reaction_force_y = -load_magnitude
    expected_reaction_moment_z = abs(load_magnitude * length)
    expected_sigma_max = (expected_reaction_moment_z * y_max) / inertia_z

    comparisons = {
        "deflection": math.isclose(actual_deflection, expected_deflection, rel_tol=rel_tol),
        "reaction_force_y": math.isclose(actual_reaction_force_y, expected_reaction_force_y, rel_tol=rel_tol),
        "reaction_moment_z": math.isclose(
            actual_reaction_moment_z, expected_reaction_moment_z, rel_tol=rel_tol
        ),
        "sigma_max": math.isclose(actual_sigma_max, expected_sigma_max, rel_tol=rel_tol),
    }
    overall_status = all(comparisons.values())

    return {
        "actual": {
            "deflection": actual_deflection,
            "reaction_force_y": actual_reaction_force_y,
            "reaction_moment_z": actual_reaction_moment_z,
            "sigma_max": actual_sigma_max,
        },
        "expected": {
            "deflection": expected_deflection,
            "reaction_force_y": expected_reaction_force_y,
            "reaction_moment_z": expected_reaction_moment_z,
            "sigma_max": expected_sigma_max,
        },
        "comparisons": comparisons,
        "status": overall_status,
    }
