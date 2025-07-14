import pytest
from fers_core import (
    Node,
    Material,
    Section,
    Member,
    MemberSet,
    NodalSupport,
    DistributedLoad,
    FERS,
)


@pytest.fixture
def uniform_cantilever_results():
    # Build the model exactly as in your script
    calc = FERS()
    node1 = Node(0, 0, 0)
    node2 = Node(5, 0, 0)
    steel = Material(
        name="Steel",
        e_mod=210e9,
        g_mod=80.769e9,
        density=7850,
        yield_stress=235e6,
    )
    section = Section(
        name="IPE 180 Beam Section",
        material=steel,
        i_y=0.819e-6,
        i_z=10.63e-6,
        j=0.027e-6,
        area=0.00196,
    )
    beam = Member(start_node=node1, end_node=node2, section=section)
    node1.nodal_support = NodalSupport()
    calc.add_member_set(MemberSet([beam]))

    lc = calc.create_load_case(name="Uniform Load")
    DistributedLoad(
        member=beam,
        load_case=lc,
        magnitude=1000.0,  # N/m
        direction=(0, -1, 0),
        start_pos=0.0,
        end_pos=beam.length(),
    )

    # Run the analysis
    calc.run_analysis()

    # Extract FERS results
    dy_fers = calc.results.displacement_nodes["2"].dy
    mz_fers = calc.results.reaction_forces[0].mz

    return dy_fers, mz_fers


def test_uniform_distributed_load(uniform_cantilever_results):
    dy_fers, mz_fers = uniform_cantilever_results

    # Analytical solution parameters
    w = 1000.0  # N/m
    L = 5.0  # m
    E = 210e9  # Pa
    I = 10.63e-6  # m^4

    # For a cantilever with uniform load:
    #   δ_max = w * L^4 / (8 * E * I)
    #   M_max = w * L^2 / 2
    delta_expected = w * L**4 / (8 * E * I)
    moment_expected = w * L**2 / 2

    # Compare with a reasonable tolerance
    assert dy_fers == pytest.approx(delta_expected, rel=1e-6), (
        f"Free-end deflection: got {dy_fers:.6e} m, " f"expected {delta_expected:.6e} m"
    )
    assert mz_fers == pytest.approx(moment_expected, rel=1e-6), (
        f"Fixed-end moment: got {mz_fers:.6e} Nm, " f"expected {moment_expected:.6e} Nm"
    )
