from fers_core import (
    FERS,
    Node,
    PlateSurface,
    PlateMeshSettings,
    PlateStiffnessModifiers,
    PlateBehavior,
)

from tests.common_functions import build_steel_s235


def build_plate_surface_model() -> FERS:
    steel = build_steel_s235()
    model = FERS()
    corners = [
        Node(0.0, 0.0, 0.0),
        Node(2.0, 0.0, 0.0),
        Node(2.0, 1.0, 0.0),
        Node(0.0, 1.0, 0.0),
    ]
    model.add_plate_surface(
        PlateSurface(
            name="Deck",
            material=steel,
            thickness=0.012,
            boundary_nodes=corners,
            behavior=PlateBehavior.SHELL,
            mesh=PlateMeshSettings(target_size=10.0),
            stiffness_modifiers=PlateStiffnessModifiers(bending=0.9),
        )
    )
    return model


def test_plate_surface_serializes_boundary_node_ids():
    model = build_plate_surface_model()

    data = model.to_dict(include_results=False)

    assert len(data["plate_surfaces"]) == 1
    surface = data["plate_surfaces"][0]
    assert surface["boundary_node_ids"] == [1, 2, 3, 4]
    assert surface["behavior"] == "Shell"
    assert surface["mesh"]["target_size"] == 10.0
    assert surface["stiffness_modifiers"]["bending"] == 0.9
    # Boundary nodes must appear in the top-level nodes array.
    node_ids = {n["id"] for n in data["nodes"]}
    assert {1, 2, 3, 4}.issubset(node_ids)


def test_plate_surface_round_trips():
    model = build_plate_surface_model()

    rebuilt = FERS.from_dict(model.to_dict(include_results=False))

    assert len(rebuilt.plate_surfaces) == 1
    surface = rebuilt.plate_surfaces[0]
    assert [n.id for n in surface.boundary_nodes] == [1, 2, 3, 4]
    assert surface.behavior == PlateBehavior.SHELL
    assert surface.material.name == "Steel"


def test_plate_surface_local_mesh_generates_plate_elements():
    model = build_plate_surface_model()

    generated = model.generate_plate_meshes()

    # A quad surface ear-clips into two triangles.
    assert len(generated) == 2
    assert len(model.plates) == 2
    assert all(element.source_surface_id == model.plate_surfaces[0].id for element in generated)
    assert model.plate_surfaces[0].generated_plate_element_ids == [
        element.id for element in generated
    ]

    data = model.to_dict(include_results=False)
    assert len(data["plate_elements"]) == 2
    assert data["plate_elements"][0]["source_surface_id"] == data["plate_surfaces"][0]["id"]
