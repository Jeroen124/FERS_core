"""Round-trip + schema-conformance coverage for the newly added model features:
cable members, work axes/planes, entity groups, plate elements/pressures."""

from fers_core import (
    FERS,
    Node,
    Member,
    Material,
    Section,
    MemberSet,
    LoadCase,
    MemberType,
    PlateElement,
    PlateSurface,
    PlateMeshSettings,
    PlateStiffnessModifiers,
    PlateBehavior,
    PlatePressure,
    WorkAxis,
    WorkPlane,
    EntityGroup,
)
from fers_core.types.pydantic_models import (
    Member as MemberSchema,
    PlateElement as PlateElementSchema,
    PlateSurface as PlateSurfaceSchema,
    PlatePressure as PlatePressureSchema,
    WorkAxis as WorkAxisSchema,
    WorkPlane as WorkPlaneSchema,
    EntityGroup as EntityGroupSchema,
)


def _build_model() -> FERS:
    model = FERS()
    model.reset_counters()
    steel = Material(name="Steel", e_mod=210e9, g_mod=80.77e9, density=7850, yield_stress=235e6)
    section = Section(name="S", material=steel, i_y=1e-6, i_z=1e-5, j=1e-8, area=2e-3)

    n1 = Node(0.0, 0.0, 0.0)
    n2 = Node(5.0, 0.0, 0.0)
    cable = Member(
        start_node=n1,
        end_node=n2,
        section=section,
        member_type=MemberType.CABLE,
        pretension=1500.0,
        unstretched_length=4.98,
    )
    model.add_member_set(MemberSet(members=[cable]))

    corners = [Node(0, 0, 0), Node(1, 0, 0), Node(1, 1, 0), Node(0, 1, 0)]
    surface = PlateSurface(
        name="Deck",
        boundary_nodes=corners,
        material=steel,
        thickness=0.01,
        behavior=PlateBehavior.SHELL,
        mesh=PlateMeshSettings(target_size=5.0),
        offset=0.0,
        stiffness_modifiers=PlateStiffnessModifiers(bending=0.8, membrane=1.0, shear=0.9),
    )
    model.add_plate_surface(surface)
    model.add_plate(PlateElement(nodes=corners[:3], material=steel, thickness=0.02))

    model.add_work_axis(WorkAxis(name="X", origin_x=0, direction_x=1))
    model.add_work_plane(WorkPlane(name="Ground", normal_z=1))
    model.add_entity_group(
        EntityGroup(name="Frame", member_ids=[cable.id], node_ids=[n1.id, n2.id])
    )

    lc = LoadCase(name="Pressure")
    model.add_load_case(lc)
    PlatePressure(load_case=lc, magnitude=750.0, surface_id=surface.id, projected=True)
    return model


def test_new_features_conform_to_pydantic_schema():
    data = _build_model().to_dict(include_results=False)

    member = data["member_sets"][0]["members"][0]
    MemberSchema(**member)
    assert member["member_type"] == "Cable"
    assert member["pretension"] == 1500.0
    assert member["unstretched_length"] == 4.98

    for el in data["plate_elements"]:
        PlateElementSchema(**el)
    for surf in data["plate_surfaces"]:
        PlateSurfaceSchema(**surf)
    for wa in data["work_axes"]:
        WorkAxisSchema(**wa)
    for wp in data["work_planes"]:
        WorkPlaneSchema(**wp)
    for eg in data["entity_groups"]:
        EntityGroupSchema(**eg)
    for pp in data["load_cases"][0]["plate_pressures"]:
        PlatePressureSchema(**pp)


def test_new_features_round_trip():
    model = _build_model()
    data = model.to_dict(include_results=False)

    model.reset_counters()
    rebuilt = FERS.from_dict(data)
    data2 = rebuilt.to_dict(include_results=False)

    for key in (
        "nodes",
        "member_sets",
        "plate_elements",
        "plate_surfaces",
        "work_axes",
        "work_planes",
        "entity_groups",
        "load_cases",
    ):
        assert data[key] == data2[key], f"round-trip mismatch in {key}"


def test_self_weight_analysis_options_round_trip():
    model = FERS()
    opts = model.settings.analysis_options
    opts.enable_self_weight = True
    opts.gravity_direction = (0.0, -1.0, 0.0)
    opts.gravity_factor = -9.81
    opts.self_weight_load_case_id = 1

    d = opts.to_dict()
    assert d["enable_self_weight"] is True
    assert d["gravity_direction"] == [0.0, -1.0, 0.0]
    assert d["gravity_factor"] == -9.81
    assert d["self_weight_load_case_id"] == 1

    from fers_core.settings.anlysis_options import AnalysisOptions

    rebuilt = AnalysisOptions.from_dict(d)
    assert rebuilt.enable_self_weight is True
    assert rebuilt.gravity_direction == (0.0, -1.0, 0.0)
    assert rebuilt.gravity_factor == -9.81
    assert rebuilt.self_weight_load_case_id == 1
