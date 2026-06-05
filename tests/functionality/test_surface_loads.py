from fers_core import FERS, LoadCase, Member, MemberSet, Node, NodalSupport, SurfaceLoad, SurfaceLoadVertex

from tests.common_functions import build_ipe180, build_steel_s235


def build_surface_model() -> FERS:
    steel = build_steel_s235()
    section = build_ipe180(steel)

    model = FERS()
    node_1 = Node(0.0, 0.0, 0.0)
    node_2 = Node(4.0, 0.0, 0.0)
    node_3 = Node(0.0, 0.0, 1.0)
    node_4 = Node(4.0, 0.0, 1.0)

    node_1.nodal_support = NodalSupport()

    member_1 = Member(start_node=node_1, end_node=node_2, section=section)
    member_2 = Member(start_node=node_3, end_node=node_4, section=section)
    model.add_member_set(MemberSet(members=[member_1, member_2]))

    load_case = LoadCase(name="Surface")
    SurfaceLoad(
        load_case=load_case,
        polygon=[
            SurfaceLoadVertex(0.0, 0.0, 0.0),
            SurfaceLoadVertex(4.0, 0.0, 0.0),
            SurfaceLoadVertex(4.0, 0.0, 1.0),
            SurfaceLoadVertex(0.0, 0.0, 1.0),
        ],
        magnitude=5.0,
        direction=(0.0, -1.0, 0.0),
        distribution_direction=(1.0, 0.0, 0.0),
    )
    model.add_load_case(load_case)
    return model


def test_surface_load_to_dict_is_embedded_in_load_case():
    model = build_surface_model()

    data = model.to_dict(include_results=False)
    load_case = data["analysis"]["load_cases"][0]

    assert "surface_loads" in load_case
    assert len(load_case["surface_loads"]) == 1
    assert load_case["surface_loads"][0]["polygon"][2] == {"x": 4.0, "y": 0.0, "z": 1.0}
    assert tuple(load_case["surface_loads"][0]["distribution_direction"]) == (1.0, 0.0, 0.0)


def test_surface_load_round_trips_through_fers_dict():
    model = build_surface_model()

    rebuilt = FERS.from_dict(model.to_dict(include_results=False))

    assert len(rebuilt.load_cases) == 1
    assert len(rebuilt.load_cases[0].surface_loads) == 1

    surface_load = rebuilt.load_cases[0].surface_loads[0]
    assert surface_load.id == 1
    assert surface_load.magnitude == 5.0
    assert surface_load.direction == (0.0, -1.0, 0.0)
    assert surface_load.distribution_direction == (1.0, 0.0, 0.0)
    assert [(vertex.x, vertex.y, vertex.z) for vertex in surface_load.polygon] == [
        (0.0, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (4.0, 0.0, 1.0),
        (0.0, 0.0, 1.0),
    ]
