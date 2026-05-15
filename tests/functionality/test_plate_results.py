from fers_core import AnalysisOrder, FERS, LoadCase, Node, NodalSupport, Plate, SurfaceLoad

from tests.common_functions import (
    TOL,
    assert_close,
    build_steel_s235,
    cantilever_uniform_load_deflection_at_free_end,
)


def build_plate_strip_pressure_model() -> tuple[FERS, list[int]]:
    model = FERS()
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    steel = build_steel_s235()
    support = NodalSupport()

    length = 2.0
    width = 0.20
    thickness = 0.03
    nx = 40

    columns: list[tuple[Node, Node]] = []
    for ix in range(nx + 1):
        x = length * ix / nx
        left_support = support if ix == 0 else None
        columns.append(
            (
                Node(X=x, Y=0.0, Z=0.0, nodal_support=left_support),
                Node(X=x, Y=width, Z=0.0, nodal_support=left_support),
            )
        )

    for ix in range(nx):
        n00, n01 = columns[ix]
        n10, n11 = columns[ix + 1]
        model.add_plate(
            Plate(
                nodes=[n00, n10, n11],
                material=steel,
                thickness=thickness,
                classification="Strip",
                local_x_direction=(1.0, 0.0, 0.0),
            ),
            Plate(
                nodes=[n00, n11, n01],
                material=steel,
                thickness=thickness,
                classification="Strip",
                local_x_direction=(1.0, 0.0, 0.0),
            ),
        )

    load_case = LoadCase(name="Pressure")
    SurfaceLoad(
        load_case=load_case,
        polygon=[(0.0, 0.0, 0.0), (length, 0.0, 0.0), (length, width, 0.0), (0.0, width, 0.0)],
        magnitude=1000.0,
        direction=(0.0, 0.0, -1.0),
    )
    model.add_load_case(load_case)

    right_edge_node_ids = [columns[-1][0].id, columns[-1][1].id]
    return model, right_edge_node_ids


def test_plate_results_are_available_in_core_after_analysis():
    model, right_edge_node_ids = build_plate_strip_pressure_model()

    model.run_analysis()

    results = model.resultsbundle.loadcases["Pressure"]
    total_reaction_fz = sum(node.nodal_forces.fz for node in results.reaction_nodes.values())
    tip_dz = -0.5 * sum(results.displacement_nodes[str(node_id)].dz for node_id in right_edge_node_ids)

    expected_total_reaction = 1000.0 * 2.0 * 0.20
    expected_tip_dz = -cantilever_uniform_load_deflection_at_free_end(
        load_intensity_in_newton_per_meter=1000.0 * 0.20,
        beam_length_in_meter=2.0,
        modulus_of_elasticity_in_pascal=210_000_000_000.0,
        second_moment_of_area_in_m_to_power_4=0.20 * 0.03**3 / 12.0,
    )

    assert len(results.plate_results) == len(model.plates)
    assert results.summary.total_plate_forces == len(model.plates)
    assert_close(
        actual=abs(total_reaction_fz),
        expected=expected_total_reaction,
        abs_tol=TOL.absolute_force_in_newton,
        label="total plate reaction",
    )
    assert_close(
        actual=tip_dz,
        expected=expected_tip_dz,
        abs_tol=1.0e-3,
        rel_tol=0.25,
        label="plate strip tip deflection",
    )

    first_plate = next(iter(results.plate_results.values()))
    assert first_plate.resultants.mx != 0.0
    assert len(first_plate.nodal_forces_global) == 3


def test_plate_results_round_trip_through_core_serialization():
    model, _ = build_plate_strip_pressure_model()
    model.run_analysis()

    rebuilt = FERS.from_dict(model.to_dict(include_results=True))

    results = rebuilt.resultsbundle.loadcases["Pressure"]
    assert len(results.plate_results) == len(rebuilt.plates)
    assert results.summary.total_plate_forces == len(rebuilt.plates)
