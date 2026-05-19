import os
from fers_core import FERS, AnalysisOrder, Material, PlateSurface, PlateVertex


# =============================================================================
# Example 141: Plate Surface with Automatic Mesh Generation
# =============================================================================
#
# A flat rectangular concrete slab (2 m × 1 m, 120 mm thick) is defined as a
# PlateSurface polygon.  FERS automatically triangulates the polygon into plate
# finite elements when ``generate_plate_meshes()`` is called.
#
# This example demonstrates:
#   • Defining a PlateSurface from corner vertices
#   • Controlling mesh density via ``mesh_size``
#   • Inspecting the generated plate elements after meshing
#   • Serialising the model to JSON
# =============================================================================

# ── Model setup ───────────────────────────────────────────────────────────────

model = FERS()
model.settings.analysis_options.order = AnalysisOrder.LINEAR

concrete = Material(
    name="Concrete C30",
    e_mod=33e9,
    g_mod=13.75e9,
    density=2500,
    yield_stress=30e6,
)

slab = PlateSurface(
    name="Rectangular Slab",
    material=concrete,
    thickness=0.120,  # 120 mm
    mesh_size=0.25,  # target element size in metres
    polygon=[
        PlateVertex(0.0, 0.0, 0.0),
        PlateVertex(2.0, 0.0, 0.0),
        PlateVertex(2.0, 1.0, 0.0),
        PlateVertex(0.0, 1.0, 0.0),
    ],
)

model.add_plate_surface(slab)

# ── Mesh generation ───────────────────────────────────────────────────────────

model.generate_plate_meshes()

print("Plate surface meshing complete")
print(f"  Plate surfaces defined : {len(model.plate_surfaces)}")
print(f"  Triangular elements    : {len(model.plates)}")
print(f"  Surface name           : {model.plate_surfaces[0].name}")
print(f"  Thickness              : {model.plate_surfaces[0].thickness * 1000:.0f} mm")

# ── Save to JSON ──────────────────────────────────────────────────────────────

file_path = os.path.join("json_input_solver", "141_Plate_Surface_Mesh.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
model.save_to_json(file_path, indent=4)
print(f"\nModel saved to {file_path}")
