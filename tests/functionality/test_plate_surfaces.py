from fers_core import FERS, PlateSurface, PlateVertex

from tests.common_functions import build_steel_s235


def build_plate_surface_model() -> FERS:
    steel = build_steel_s235()
    model = FERS()
    model.add_plate_surface(
        PlateSurface(
            name="Deck",
            material=steel,
            thickness=0.012,
            mesh_size=10.0,
            polygon=[
                PlateVertex(0.0, 0.0, 0.0),
                PlateVertex(2.0, 0.0, 0.0),
                PlateVertex(2.0, 1.0, 0.0),
                PlateVertex(0.0, 1.0, 0.0),
            ],
        )
    )
    model.generate_plate_meshes()
    return model


def test_plate_surface_is_serialized_with_generated_plate_mesh():
    model = build_plate_surface_model()

    data = model.to_dict(include_results=False)

    assert len(data["plate_surfaces"]) == 1
    assert len(data["plates"]) == 2
    assert data["materials"][0]["name"] == "Steel"
    assert data["plates"][0]["source_surface"] == data["plate_surfaces"][0]["id"]


def test_plate_surface_round_trips_with_mesh():
    model = build_plate_surface_model()

    rebuilt = FERS.from_dict(model.to_dict(include_results=False))

    assert len(rebuilt.plate_surfaces) == 1
    assert len(rebuilt.plates) == 2
    assert rebuilt.plate_surfaces[0].generated_plate_ids == [1, 2]
    assert rebuilt.plates[0].material.name == "Steel"
    assert len(rebuilt.plates[0].nodes) == 3
