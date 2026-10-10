"""Saving a model and loading it back loses nothing the solver reads.

``kitchen_sink()`` builds one model with every entity of the solver's input
schema and every optional field set to something other than its default. Saving
it, loading it back and saving it again must give the same document. The
coverage guard walks the generated pydantic input models, so a field added to
the solver contract fails here until the SDK reads and writes it.
"""

import types
from enum import Enum
from typing import Union, get_args, get_origin

import pytest
from pydantic import BaseModel, RootModel, TypeAdapter, ValidationError
from pydantic_core import PydanticUndefined

from fers_core import (
    FERS,
    BucklingRestraint,
    DistributedLoad,
    EntityGroup,
    ImperfectionCase,
    LoadCombination,
    Material,
    Member,
    MemberHinge,
    MemberPointLoad,
    MemberPointMoment,
    MemberSet,
    MemberType,
    MomentRotationCurve,
    NodalLoad,
    NodalMass,
    NodalMoment,
    NodalSupport,
    Node,
    OrthotropicPlateMaterial,
    PlateElement,
    PlateMeshDivisions,
    PlateMeshSettings,
    PlateOpening,
    PlatePressure,
    PlateStiffnessModifiers,
    PlateSurface,
    Section,
    SeismicAnalysisSettings,
    ShapePath,
    StiffnessCurveConfig,
    SupportCondition,
    SurfaceLoad,
    SwayImperfection,
    TranslationImperfection,
    WorkAxis,
    WorkPlane,
)
from fers_core.members.moment_rotation import CurveEndBehaviour
from fers_core.members.shapecommand import ShapeCommand
from fers_core.settings.anlysis_options import (
    AnalysisOptions,
    AnalysisOrder,
    Dimensionality,
    NonlinearMethod,
    PdeltaFormulation,
    PdeltaMode,
    ResultBlock,
    RigidStrategy,
)
from fers_core.settings.general_info import GeneralInfo
from fers_core.settings.settings import Settings
from fers_core.settings.units_settings import UnitSettings
from fers_core.supports.stiffness_curve import ForceComponent
from fers_core.types import pydantic_models
from fers_core.unity_checks import ec3_steel_check


def kitchen_sink(buckling: str = "references") -> FERS:
    """One of every entity, every optional field set. ``buckling`` picks which of
    the three mutually exclusive reference forms the buckling request uses."""
    model = FERS()
    model.settings = Settings(
        analysis_options=AnalysisOptions(
            solve_loadcases=False,
            tolerance=1e-4,
            max_iterations=40,
            dimensionality=Dimensionality.THREE_DIMENSIONAL,
            order=AnalysisOrder.NONLINEAR,
            rigid_strategy=RigidStrategy.LINEAR_MPC,
            axial_slack=250.0,
            include_shear_deformation=False,
            include_warping=False,
            include_shear_center_coupling=False,
            nonlinear_method=NonlinearMethod.P_DELTA,
            pdelta_formulation=PdeltaFormulation.SIMPLIFIED,
            pdelta_mode=PdeltaMode.IN_PLANE_ONLY,
            pdelta_suppress_axes=["Z"],
            enable_self_weight=True,
            gravity_direction=(0.0, 0.0, -1.0),
            gravity_factor=9.80665,
            include_member_deflected_shape=True,
            result_filter=[ResultBlock.REACTIONS, ResultBlock.NODE_DISPLACEMENTS],
            include_report_html=True,
            render_unity_reports=True,
        ),
        general_info=GeneralInfo(project_name="Kitchen sink", author="FERS tests", version="2.0"),
        unit_settings=UnitSettings(
            system="metric", length_unit="m", force_unit="N", density_unit="kg/m3", pressure_unit="Pa"
        ),
    )

    steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
    timber = Material(
        name="CLT",
        e_mod=11e9,
        g_mod=0.69e9,
        density=470.0,
        yield_stress=24e6,
        orthotropic_plate=OrthotropicPlateMaterial(
            e_x=11e9, e_y=0.37e9, g_xy=0.69e9, nu_xy=0.05, g_xz=0.05e9, g_yz=0.05e9
        ),
    )
    outline = ShapePath(
        name="arc",
        shape_commands=[
            ShapeCommand("moveTo", y=0.0, z=0.0),
            ShapeCommand("lineTo", y=0.1, z=0.0),
            ShapeCommand(
                "arcTo", y=0.1, z=0.1, r=0.05, center_y=0.05, center_z=0.05, theta0=0.0, theta1=90.0
            ),
            ShapeCommand("closePath"),
        ],
    )
    beam_section = Section(
        name="Beam",
        material=steel,
        i_y=8.0e-6,
        i_z=6.0e-7,
        j=4.0e-8,
        area=2.0e-3,
        h=0.18,
        b=0.09,
        shape_path=outline,
        i_w=3.0e-9,
        y_s=0.001,
        z_s=-0.002,
        wagner_coeff=0.012,
        a_sy=1.0e-3,
        a_sz=0.9e-3,
        wel_y=1.5e-4,
        wel_z=2.0e-5,
        wpl_y=1.7e-4,
        wpl_z=3.0e-5,
        principal_axis_angle=12.0,
        i_yz=1.0e-7,
        centroid_y=0.01,
        centroid_z=0.02,
        ec3={
            "section_class": 2,
            "buckling_curve_y": "A",
            "buckling_curve_z": "B",
            "buckling_curve_lt": "C",
            "a_eff": 1.9e-3,
            "wel_y_eff": 1.4e-4,
            "wel_z_eff": 1.9e-5,
            "z_j": 0.003,
        },
    )

    fixed_base = NodalSupport(
        classification="base",
        displacement_conditions={
            "X": SupportCondition.fixed(),
            "Y": SupportCondition.spring(2.0e7),
            "Z": SupportCondition.positive_only(stiffness=1.0e8),
        },
        rotation_conditions={
            "X": SupportCondition.free(),
            "Y": SupportCondition.negative_only(),
            "Z": SupportCondition.spring_curve(
                ForceComponent.Fz, [[-1000.0, 1.0e5], [0.0, 2.0e5]], signed=True
            ),
        },
        warping_condition=SupportCondition.spring(10.0),
    )
    slab_edge = NodalSupport(displacement_conditions={"Y": "Free"})
    reference_marker = NodalSupport(rotation_conditions={"Z": "Free"})

    curve = [[0.0, 1.0e6], [5.0e4, 5.0e5]]
    spring_hinge = MemberHinge(
        hinge_type="spring",
        translational_release_vx=1.0e9,
        translational_release_vy=2.0e9,
        translational_release_vz=3.0e9,
        rotational_release_mx=1.0e5,
        rotational_release_my=2.0e5,
        rotational_release_mz=3.0e5,
        rotational_release_warp=4.0e5,
        max_tension_vx=1.0e5,
        max_tension_vy=2.0e5,
        max_tension_vz=3.0e5,
        max_moment_mx=1.0e4,
        max_moment_my=2.0e4,
        max_moment_mz=3.0e4,
        max_bimoment_warp=4.0e3,
        stiffness_curve_vx=StiffnessCurveConfig(ForceComponent.N, curve),
        stiffness_curve_vy=StiffnessCurveConfig(ForceComponent.Vy, curve),
        stiffness_curve_vz=StiffnessCurveConfig(ForceComponent.Vz, curve, signed=True),
        stiffness_curve_mx=StiffnessCurveConfig(ForceComponent.Mx, curve),
        stiffness_curve_my=StiffnessCurveConfig(ForceComponent.My, curve),
        stiffness_curve_mz=StiffnessCurveConfig(ForceComponent.Mz, curve),
    )
    connector = MemberHinge(
        hinge_type="connector",
        moment_rotation_mx=MomentRotationCurve([[0.0, 0.0], [0.01, 5.0e3]]),
        moment_rotation_my=MomentRotationCurve(
            [[-0.02, -8.0e3], [0.0, 0.0], [0.02, 9.0e3]],
            symmetric=False,
            start=CurveEndBehaviour.STOP,
            end=CurveEndBehaviour.FAILURE,
        ),
        moment_rotation_mz=MomentRotationCurve([[0.0, 0.0], [0.03, 4.0e3]], end=CurveEndBehaviour.YIELDING),
    )

    base = Node(0.0, 0.0, 0.0, nodal_support=fixed_base)
    knee = Node(0.0, 3.0, 0.0)
    apex = Node(4.0, 3.0, 0.0)
    foot = Node(4.0, 0.0, 0.0, nodal_support=fixed_base)
    anchor = Node(8.0, 0.0, 0.0, nodal_support=fixed_base)
    marker = Node(0.0, 6.0, 0.0, nodal_support=reference_marker)  # only a reference node

    rafter = Member(
        start_node=knee,
        end_node=apex,
        section=beam_section,
        start_hinge=spring_hinge,
        end_hinge=connector,
        classification="rafter",
        rotation_angle=15.0,
        mirror=True,
        chi=0.8,
        reference_node=marker,
        start_offset={"X": 0.01, "Y": 0.02, "Z": 0.03},
        end_offset={"X": -0.01, "Y": -0.02, "Z": -0.03},
        weight_override=1234.5,
    )
    column = Member(start_node=base, end_node=knee, section=beam_section, member_type=MemberType.NORMAL)
    truss = Member(start_node=foot, end_node=apex, section=beam_section, member_type=MemberType.TRUSS)
    tie = Member(start_node=base, end_node=foot, section=beam_section, member_type=MemberType.TENSION)
    strut = Member(start_node=foot, end_node=anchor, section=beam_section, member_type=MemberType.COMPRESSION)
    cable = Member(
        start_node=apex,
        end_node=anchor,
        section=beam_section,
        member_type=MemberType.CABLE,
        pretension=500.0,
        unstretched_length=4.99,
    )
    link = Member(start_node=knee, end_node=Node(0.0, 3.0, 0.5), member_type=MemberType.RIGID)
    # Listed after the rafter, so loading has to resolve it in a second pass.
    rafter.reference_member = strut

    frame = MemberSet(
        members=[rafter, column, truss, tie, strut, cable, link],
        classification="frame",
        buckling_restraints=[
            BucklingRestraint(knee.id, restrains_local_y=True, restrains_local_z=True, restrains_torsion=True)
        ],
        buckling_length_y=6.0,
        buckling_length_z=3.0,
        ltb_length=2.5,
        buckling_length_t=2.0,
        effective_length_factor_y=0.9,
        effective_length_factor_z=0.7,
    )
    model.add_member_set(frame)
    model.add_nodal_mass(NodalMass(knee, 150.0, inertia_x=1.0, inertia_y=2.0, inertia_z=3.0))

    corners = [
        Node(0.0, 0.0, 2.0, nodal_support=slab_edge),
        Node(4.0, 0.0, 2.0),
        Node(4.0, 0.0, 6.0),
        Node(0.0, 0.0, 6.0),
    ]
    hole = [Node(1.0, 0.0, 3.0), Node(2.0, 0.0, 3.0), Node(2.0, 0.0, 4.0)]
    slab = PlateSurface(
        boundary_nodes=corners,
        material=timber,
        thickness=0.2,
        behavior="Membrane",
        theory="Mindlin",
        plane_state="PlaneStrain",
        mesh=PlateMeshSettings(
            element_shape="Quad", target_size=0.5, method="Structured", divisions=PlateMeshDivisions(4, 4)
        ),
        openings=[PlateOpening(boundary_nodes=hole)],
        offset=0.05,
        stiffness_modifiers=PlateStiffnessModifiers(bending=0.5, membrane=0.8, shear=0.9),
        name="floor",
        classification="slab",
        local_x_direction=(1.0, 0.0, 0.0),
        mesh_group_id=7,
    )
    model.add_plate_surface(slab)
    deck = PlateElement(
        nodes=[Node(0.0, 3.0, 2.0), Node(4.0, 3.0, 2.0), Node(4.0, 3.0, 4.0), Node(0.0, 3.0, 4.0)],
        material=steel,
        thickness=0.01,
        classification="deck",
        source_surface=slab,
        local_x_direction=(0.0, 0.0, 1.0),
        behavior="Membrane",
        theory="Kirchhoff",
        plane_state="PlaneStrain",
        offset=0.002,
        stiffness_modifiers=PlateStiffnessModifiers(bending=0.4, membrane=0.6, shear=0.7),
    )
    model.add_plate(deck)
    slab.generated_plate_element_ids = [deck.id]

    axis = WorkAxis(1.0, 2.0, 3.0, 0.48, 0.6, 0.64, name="grid A")
    plane = WorkPlane(1.0, 3.0, 2.0, 0.48, 0.6, 0.64, name="level 1")
    model.add_work_axis(axis)
    model.add_work_plane(plane)
    model.add_entity_group(
        EntityGroup(
            name="everything",
            member_ids=[rafter.id],
            member_set_ids=[frame.id],
            node_ids=[knee.id],
            plate_surface_ids=[slab.id],
            plate_element_ids=[deck.id],
            support_ids=[fixed_base.id],
            work_axis_ids=[axis.id],
            work_plane_ids=[plane.id],
        )
    )

    dead = model.create_load_case("Dead")
    live = model.create_load_case("Live")
    model.settings.analysis_options.self_weight_load_case_id = dead.id
    NodalLoad(knee, dead, 1000.0, (0.0, -1.0, 0.0))
    NodalMoment(apex, dead, 50.0, (0.0, 0.0, 1.0))
    DistributedLoad(
        member=rafter,
        load_case=live,
        magnitude=100.0,
        end_magnitude=200.0,
        direction=(0.0, -1.0, 0.0),
        start_frac=0.1,
        end_frac=0.9,
    )
    MemberPointLoad(
        member=column, load_case=live, magnitude=10.0, direction=(1.0, 0.0, 0.0), position=0.25, axes="local"
    )
    MemberPointMoment(
        member=column, load_case=live, magnitude=5.0, direction=(0.0, 0.0, 1.0), position=0.75, axes="local"
    )
    SurfaceLoad(
        load_case=live,
        polygon=[(0.0, 3.0, 2.0), (4.0, 3.0, 2.0), (4.0, 3.0, 4.0)],
        magnitude=2000.0,
        direction=(0.0, -1.0, 0.0),
        distribution_direction=(1.0, 0.0, 0.0),
    )
    PlatePressure(
        load_case=live, magnitude=3000.0, direction=(0.0, -1.0, 0.0), surface_id=slab.id, projected=True
    )
    PlatePressure(load_case=live, magnitude=1500.0, direction=(0.0, -1.0, 0.0), plate_element_id=deck.id)

    uls = LoadCombination(
        name="ULS 1",
        load_cases_factors={dead: 1.35, live: 1.5},
        situation="Persistent",
        check="ALL",
        limit_state="ULS",
    )
    model.add_load_combination(uls)
    model.add_imperfection_case(
        ImperfectionCase(
            loadcombinations=[uls],
            sway_imperfections=[
                SwayImperfection(
                    magnitude=1 / 200,
                    axis=(0.0, 0.0, 1.0),
                    height_direction=(0.0, 1.0, 0.0),
                    reference_point=(1.0, 0.0, 0.0),
                )
            ],
            translation_imperfections=[
                TranslationImperfection(memberset=[frame], magnitude=0.01, axis=(1.0, 0.0, 0.0))
            ],
        )
    )
    model.add_unity_check(ec3_steel_check("ec3", "EC3 members", load_combination_ids=[uls.id]))

    model.add_modal_analysis(
        num_modes=3,
        mass_formulation="LUMPED",
        tolerance=1e-7,
        max_iterations=80,
        stiffness_reference=uls,
        include_geometric_stiffness=True,
    )
    reference_forms = {
        "references": {"references": [dead, uls]},
        "reference": {"reference": live},
        "all_combinations": {"all_combinations": True},
    }
    model.add_buckling_analysis(
        num_modes=2,
        tolerance=1e-7,
        max_iterations=90,
        member_effective_lengths=True,
        participation_threshold=0.1,
        **reference_forms[buckling],
    )
    model.add_seismic_analysis(
        spectrum_x=SeismicAnalysisSettings.eurocode_spectrum(
            ag=2.5, ground_type="C", spectrum_type="TYPE2", q=1.5, beta=0.25
        ),
        spectrum_y=SeismicAnalysisSettings.direct_spectrum(
            ag=2.0, s=1.15, tb=0.2, tc=0.6, td=2.0, q=2.0, beta=0.15
        ),
        spectrum_z=SeismicAnalysisSettings.custom_spectrum([[0.0, 2.0], [0.5, 5.0], [2.0, 1.0]]),
        method="BOTH",
        num_modes=4,
        directions=["X", "Y", "Z"],
        modal_combination="SRSS",
        directional_combination="PERCENT30",
        damping=0.03,
        mass_sources=[(live, 0.3)],
        include_structural_mass=False,
        mass_formulation="LUMPED",
        stiffness_reference=dead,
        include_geometric_stiffness=True,
        tolerance=1e-7,
        max_iterations=70,
    )
    return model


BUCKLING_FORMS = ["references", "reference", "all_combinations"]


def _save(model: FERS) -> dict:
    return model.to_dict(include_results=False)


def _reload(document: dict) -> dict:
    return _save(FERS.from_dict(document))


def _first_difference(a, b, path="$"):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in list(a) + [k for k in b if k not in a]:
            if key not in a or key not in b:
                return f"{path}.{key}: only in the {'reloaded' if key in b else 'saved'} document"
            found = _first_difference(a[key], b[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: {len(a)} entries saved, {len(b)} after reloading"
        for i, (x, y) in enumerate(zip(a, b)):
            found = _first_difference(x, y, f"{path}[{i}]")
            if found:
                return found
        return None
    if a != b:
        return f"{path}: saved {a!r}, reloaded {b!r}"
    return None


def _dangling_references(document: dict) -> list[str]:
    model = document["model"]
    ids = {key: {entry.get("id") for entry in model.get(key) or []} for key in model if key != "workspace"}
    problems = []

    def need(kind, ref, where):
        if ref is not None and ref not in ids.get(kind, set()):
            problems.append(f"{where} refers to {kind} {ref}, which the document does not define")

    for node in model["nodes"]:
        need("nodal_supports", node.get("nodal_support"), f"node {node['id']}")
    for member in model["members"]:
        where = f"member {member['id']}"
        for key in ("start_node_id", "end_node_id", "reference_node"):
            need("nodes", member.get(key), where)
        need("members", member.get("reference_member"), where)
        need("sections", member.get("section"), where)
        need("member_hinges", member.get("start_hinge"), where)
        need("member_hinges", member.get("end_hinge"), where)
    for section in model["sections"]:
        need("materials", section["material"], f"section {section['id']}")
        need("shape_paths", section.get("shape_path"), f"section {section['id']}")
    for mass in model.get("nodal_masses") or []:
        need("nodes", mass["node"], "a nodal mass")
    for surface in model.get("plate_surfaces") or []:
        where = f"plate surface {surface['id']}"
        need("materials", surface["material"], where)
        for node_id in surface["boundary_node_ids"]:
            need("nodes", node_id, where)
        for opening in surface.get("openings") or []:
            for node_id in opening["boundary_node_ids"]:
                need("nodes", node_id, f"opening {opening['id']} of {where}")
    for plate in model.get("plate_elements") or []:
        need("materials", plate["material"], f"plate element {plate['id']}")
        for node_id in plate["node_ids"]:
            need("nodes", node_id, f"plate element {plate['id']}")
    return problems


@pytest.mark.parametrize("buckling", BUCKLING_FORMS)
def test_kitchen_sink_survives_saving_and_loading(buckling):
    saved = _save(kitchen_sink(buckling))
    difference = _first_difference(saved, _reload(saved))
    assert difference is None, difference


@pytest.mark.parametrize("buckling", BUCKLING_FORMS)
def test_kitchen_sink_conforms_to_the_solver_schema(buckling):
    saved = _save(kitchen_sink(buckling))
    pydantic_models.FERS(**{**saved, "results": None})
    pydantic_models.FERS(**{**_reload(saved), "results": None})


def test_kitchen_sink_refers_only_to_what_it_defines():
    saved = _save(kitchen_sink())
    assert _dangling_references(saved) == []
    assert _dangling_references(_reload(saved)) == []


# ---------------------------------------------------------------------------
# Coverage guard
# ---------------------------------------------------------------------------

# Subtrees the SDK carries as plain dicts and never interprets, so a round trip
# cannot lose a field inside them; the kitchen sink still carries one.
OPAQUE = {pydantic_models.UnityCheckDefinition}

# (schema class, field) -> why the kitchen sink does not set it.
EXEMPT = {
    ("FERS", "results"): "output, not input",
}


def _classes_in(annotation):
    origin = get_origin(annotation)
    if origin is not None:
        for arg in get_args(annotation):
            yield from _classes_in(arg)
    elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation


def _input_fields() -> set[tuple[str, str]]:
    fields, seen = set(), set()

    def visit(annotation):
        for cls in _classes_in(annotation):
            if cls in seen or cls in OPAQUE:
                continue
            seen.add(cls)
            for name, field in cls.model_fields.items():
                if issubclass(cls, RootModel):
                    visit(field.annotation)
                    continue
                fields.add((cls.__name__, name))
                if (cls.__name__, name) not in EXEMPT:
                    visit(field.annotation)

    visit(pydantic_models.FERS)
    return fields


def _is_set(field, value) -> bool:
    if value is None or value == [] or value == {}:
        return False
    if field.default is PydanticUndefined:
        # A required field is always present, so a writer that ignores it still
        # emits something; only a value other than zero or "" shows it is carried
        # through (Member.weight: 0 means no override).
        is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        return not (is_number and value == 0) and value != ""
    default = field.default.value if isinstance(field.default, Enum) else field.default
    return value != default


def _accepts(annotation, value) -> bool:
    try:
        TypeAdapter(annotation).validate_python(value)
    except ValidationError:
        return False
    return True


def _walk(annotation, value, covered):
    if value is None:
        return
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        for arg in get_args(annotation):
            if arg is not type(None) and _accepts(arg, value):
                _walk(arg, value, covered)
                return
        return
    if origin is list:
        for item in value:
            _walk(get_args(annotation)[0], item, covered)
        return
    if origin is dict:
        for item in value.values():
            _walk(get_args(annotation)[1], item, covered)
        return
    if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)) or annotation in OPAQUE:
        return
    if issubclass(annotation, RootModel):
        _walk(annotation.model_fields["root"].annotation, value, covered)
        return
    for name, field in annotation.model_fields.items():
        key = field.alias or name
        if isinstance(value, dict) and key in value:
            if _is_set(field, value[key]):
                covered.add((annotation.__name__, name))
            _walk(field.annotation, value[key], covered)


def test_kitchen_sink_sets_every_input_field():
    covered: set[tuple[str, str]] = set()
    for buckling in BUCKLING_FORMS:
        _walk(pydantic_models.FERS, _save(kitchen_sink(buckling)), covered)
    missing = sorted(_input_fields() - covered - set(EXEMPT))
    assert not missing, (
        "The solver schema has fields the kitchen sink never sets, so nothing checks that "
        "saving and loading keeps them. Set them in kitchen_sink(), or exempt them with a reason:\n"
        + "\n".join(f"  {cls}.{name}" for cls, name in missing)
    )


# ---------------------------------------------------------------------------
# What used to be lost, one at a time
# ---------------------------------------------------------------------------


def _reloaded(model: FERS) -> FERS:
    return FERS.from_dict(_save(model))


def test_section_ec3_block_survives():
    section = _reloaded(kitchen_sink()).get_unique_sections_from_all_member_sets()[0]
    assert section.ec3["buckling_curve_z"] == "B"
    assert section.ec3["section_class"] == 2


def test_member_set_buckling_lengths_survive():
    frame = _reloaded(kitchen_sink()).member_sets[0]
    assert (frame.buckling_length_y, frame.buckling_length_z) == (6.0, 3.0)
    assert (frame.ltb_length, frame.buckling_length_t) == (2.5, 2.0)
    assert (frame.effective_length_factor_y, frame.effective_length_factor_z) == (0.9, 0.7)


def test_nodal_masses_survive():
    (mass,) = _reloaded(kitchen_sink()).nodal_masses
    assert isinstance(mass.node, Node)
    assert (mass.mass, mass.inertia_x, mass.inertia_y, mass.inertia_z) == (150.0, 1.0, 2.0, 3.0)


def test_translation_imperfection_names_its_member_sets_as_the_solver_does():
    saved = _save(kitchen_sink())
    (written,) = saved["analysis"]["imperfection_cases"][0]["translation_imperfections"]
    assert written["memberset_ids"] == [saved["model"]["member_sets"][0]["id"]]
    assert "memberset" not in written


def test_translation_imperfection_reads_the_old_key():
    saved = _save(kitchen_sink())
    written = saved["analysis"]["imperfection_cases"][0]["translation_imperfections"][0]
    written["memberset"] = written.pop("memberset_ids")
    imperfection = FERS.from_dict(saved).imperfection_cases[0].translation_imperfections[0]
    assert [member_set.id for member_set in imperfection.memberset] == written["memberset"]


def test_an_offset_given_on_one_axis_is_zero_on_the_others():
    member = Member(Node(0, 0, 0), Node(1, 0, 0), member_type=MemberType.RIGID, start_offset={"X": 0.1})
    assert member.to_dict()["start_offset"] == {"X": 0.1, "Y": 0.0, "Z": 0.0}


def test_the_solver_accepts_a_translation_imperfection_and_a_one_axis_offset():
    # Both used to be written in a form the solver refused outright; the schema
    # check could not see the offset, which it declares nullable.
    model = FERS()
    steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
    section = Section(name="box", material=steel, i_y=2e-5, i_z=2e-5, j=1e-6, area=5e-3)
    base, top = Node(0.0, 0.0, 0.0, nodal_support=NodalSupport()), Node(0.0, 3.0, 0.0)
    column = Member(base, top, section=section, end_offset={"X": 0.05})
    frame = MemberSet(members=[column])
    model.add_member_set(frame)
    load = model.create_load_case("Load")
    NodalLoad(top, load, 1000.0, (1.0, 0.0, 0.0))
    combination = LoadCombination(name="ULS", load_cases_factors={load: 1.0})
    model.add_load_combination(combination)
    model.add_imperfection_case(
        ImperfectionCase(
            loadcombinations=[combination],
            translation_imperfections=[
                TranslationImperfection(memberset=[frame], magnitude=0.01, axis=(1, 0, 0))
            ],
        )
    )
    model.run_analysis()
    assert model.resultsbundle.loadcombinations["ULS"].displacement_nodes[str(top.id)].dx > 0.0


def test_an_unclassified_member_stays_unclassified():
    model = kitchen_sink()
    model.get_all_members()[1].classification = None
    saved = _save(model)
    assert saved["model"]["members"][1]["classification"] is None
    assert _reload(saved)["model"]["members"][1]["classification"] is None


def test_plate_element_classification_survives():
    (deck,) = _reloaded(kitchen_sink()).plates
    assert deck.classification == "deck"


def test_unknown_option_tokens_are_kept_not_replaced_by_defaults():
    saved = _save(kitchen_sink())
    options = saved["analysis"]["options"]
    options.update(order="THIRD_ORDER", rigid_strategy="Penalty", nonlinear_method="ARC_LENGTH")
    reloaded = _reload(saved)["analysis"]["options"]
    assert (reloaded["order"], reloaded["rigid_strategy"], reloaded["nonlinear_method"]) == (
        "THIRD_ORDER",
        "Penalty",
        "ARC_LENGTH",
    )


def test_a_document_without_a_pressure_unit_is_in_pascal():
    # The solver reads a missing pressureUnit as Pa; loading must not turn it into MPa.
    saved = _save(kitchen_sink())
    del saved["settings"]["unit_settings"]["pressureUnit"]
    assert _reload(saved)["settings"]["unit_settings"]["pressureUnit"] == "Pa"


def test_stiffness_curves_differing_only_in_sign_handling_are_not_equal():
    points = [[0.0, 1.0e5], [10.0, 2.0e5]]
    assert StiffnessCurveConfig(ForceComponent.N, points) != StiffnessCurveConfig(
        ForceComponent.N, points, signed=True
    )


def test_a_reference_member_listed_later_survives():
    rafter = _reloaded(kitchen_sink()).get_all_members()[0]
    assert rafter.reference_member is not None
    assert rafter.reference_member.member_type is MemberType.COMPRESSION


def test_supports_reached_only_through_surfaces_and_reference_nodes_are_written():
    saved = _save(kitchen_sink())
    support_ids = {support["id"] for support in saved["model"]["nodal_supports"]}
    used = {node["nodal_support"] for node in saved["model"]["nodes"] if node["nodal_support"] is not None}
    assert used <= support_ids


def test_unused_library_entries_survive():
    saved = _save(kitchen_sink())
    library = saved["model"]
    library["materials"].append({**library["materials"][0], "id": 90, "name": "spare"})
    library["sections"].append({**library["sections"][0], "id": 91, "name": "spare"})
    library["shape_paths"].append({**library["shape_paths"][0], "id": 92, "name": "spare"})
    library["member_hinges"].append({**library["member_hinges"][0], "id": 93})
    library["nodal_supports"].append({**library["nodal_supports"][0], "id": 94})
    library["nodes"].append({"id": 95, "X": 9.0, "Y": 9.0, "Z": 9.0, "nodal_support": None})
    reloaded = _reload(saved)["model"]
    for key, spare in [
        ("materials", 90),
        ("sections", 91),
        ("shape_paths", 92),
        ("member_hinges", 93),
        ("nodal_supports", 94),
        ("nodes", 95),
    ]:
        assert spare in {entry["id"] for entry in reloaded[key]}, key


def test_seismic_and_report_options_survive():
    reloaded = _reloaded(kitchen_sink())
    seismic = reloaded.seismic_analysis
    assert seismic.method == "BOTH"
    assert seismic.spectrum_z == {"CustomPoints": {"points": [[0.0, 2.0], [0.5, 5.0], [2.0, 1.0]]}}
    assert seismic.mass_sources == [{"load_case_id": reloaded.load_cases[1].id, "psi": 0.3}]
    options = reloaded.settings.analysis_options
    assert options.include_report_html is True
    assert options.render_unity_reports is True


def test_weight_override_maps_to_the_solver_weight_and_back():
    saved = _save(kitchen_sink())
    assert saved["model"]["members"][0]["weight"] == 1234.5
    assert saved["model"]["members"][1]["weight"] == 0.0
    rafter, column = _reloaded(kitchen_sink()).get_all_members()[:2]
    assert rafter.weight_override == 1234.5
    assert column.weight_override is None


def test_weight_is_still_the_member_mass_after_loading():
    model = kitchen_sink()
    column = model.get_all_members()[1]
    reloaded_column = _reloaded(model).get_all_members()[1]
    assert column.weight > 0.0
    assert reloaded_column.weight == pytest.approx(column.weight)


# ---------------------------------------------------------------------------
# Ids after loading
# ---------------------------------------------------------------------------


def test_new_objects_after_loading_never_reuse_a_loaded_id():
    model = FERS.from_dict(_save(kitchen_sink()))
    taken = {
        Node: {node.id for node in model.get_all_nodes()},
        Member: {member.id for member in model.get_all_members()},
        MemberSet: {member_set.id for member_set in model.member_sets},
        Section: {section.id for section in model.get_unique_sections_from_all_member_sets()},
        Material: {material.id for material in model.get_unique_materials_from_all_member_sets()},
        ShapePath: {path.id for path in model.get_unique_shape_paths_from_all_member_sets()},
        MemberHinge: {hinge.id for hinge in model.get_unique_member_hinges_from_all_member_sets()},
        NodalSupport: {support.id for support in model.get_unique_nodal_support_from_all_member_sets()},
        PlateSurface: {surface.id for surface in model.plate_surfaces},
        PlateElement: {plate.id for plate in model.plates},
        LoadCombination: {combination.id for combination in model.load_combinations},
        ImperfectionCase: {case.imperfection_case_id for case in model.imperfection_cases},
    }
    steel = model.get_unique_materials_from_all_member_sets()[0]
    section = model.get_unique_sections_from_all_member_sets()[0]
    start, end = Node(10, 0, 0), Node(11, 0, 0)
    member = Member(start, end, section=section)
    fresh = {
        Node: start.id,
        Member: member.id,
        MemberSet: MemberSet(members=[member]).id,
        Section: Section(name="new", material=steel, i_y=1.0, i_z=1.0, j=1.0, area=1.0).id,
        Material: Material(name="new", e_mod=1.0, g_mod=1.0, density=1.0, yield_stress=1.0).id,
        ShapePath: ShapePath(name="new", shape_commands=[]).id,
        MemberHinge: MemberHinge().id,
        NodalSupport: NodalSupport().id,
        PlateSurface: PlateSurface(
            [Node(0, 9, 0), Node(1, 9, 0), Node(1, 9, 1)], material=steel, thickness=0.1
        ).id,
        PlateElement: PlateElement(
            [Node(0, 8, 0), Node(1, 8, 0), Node(1, 8, 1)], material=steel, thickness=0.1
        ).id,
        LoadCombination: LoadCombination(name="new", load_cases_factors={model.load_cases[0]: 1.0}).id,
        ImperfectionCase: ImperfectionCase(loadcombinations=[]).imperfection_case_id,
    }
    clashes = {cls.__name__: fresh[cls] for cls in fresh if fresh[cls] in taken[cls]}
    assert not clashes, f"new objects took ids the loaded model already uses: {clashes}"
