import os
from fers_core import (
    FERS,
    AnalysisOrder,
    LoadCase,
    Material,
    Node,
    NodalSupport,
    Plate,
    SurfaceLoad,
    SurfaceLoadVertex,
)


# =============================================================================
# Example 142: Plate Strip with Surface Pressure Load
# =============================================================================
#
# A cantilevered plate strip (2 m long × 0.2 m wide, 30 mm steel) is modelled
# as a grid of triangular plate elements and loaded with a uniform pressure of
# 1 kN/m² acting in the −Z direction.
#
# The analytical reference for tip deflection of a cantilever with a uniform
# distributed load (UDL) is:
#
#   δ = q · L⁴ / (8 · E · I)
#
# where q = 1000 N/m² × 0.20 m = 200 N/m (load per unit length of strip),
#       L = 2.0 m, E = 210 GPa, I = b·t³/12 = 0.20 × 0.03³ / 12.
#
# This example demonstrates:
#   • Building a plate mesh manually with triangular Plate elements
#   • Applying a SurfaceLoad (pressure) over a polygon region
#   • Running a linear analysis and reading plate + node results
# =============================================================================

# ── Geometry parameters ───────────────────────────────────────────────────────

LENGTH = 2.0  # strip length [m]
WIDTH = 0.20  # strip width  [m]
THICKNESS = 0.03  # plate thickness [m]
NX = 20  # number of element columns along the length
PRESSURE = 1000.0  # surface pressure [N/m²]

# ── Model setup ───────────────────────────────────────────────────────────────

model = FERS()
model.settings.analysis_options.order = AnalysisOrder.LINEAR

steel = Material(
    name="Steel S235",
    e_mod=210e9,
    g_mod=80.769e9,
    density=7850,
    yield_stress=235e6,
)

fixed_support = NodalSupport()

# ── Build node grid ───────────────────────────────────────────────────────────
# Two rows of nodes (Y=0 and Y=WIDTH) marching along X.
# Left column (X=0) is fully fixed.

columns: list[tuple[Node, Node]] = []
for ix in range(NX + 1):
    x = LENGTH * ix / NX
    support = fixed_support if ix == 0 else None
    bottom = Node(X=x, Y=0.0, Z=0.0, nodal_support=support)
    top = Node(X=x, Y=WIDTH, Z=0.0, nodal_support=support)
    columns.append((bottom, top))

# ── Build triangular plate elements ──────────────────────────────────────────
# Each quad cell is split into two triangles.

for ix in range(NX):
    n00, n01 = columns[ix]
    n10, n11 = columns[ix + 1]
    model.add_plate(
        Plate(
            nodes=[n00, n10, n11],
            material=steel,
            thickness=THICKNESS,
            local_x_direction=(1.0, 0.0, 0.0),
        ),
        Plate(
            nodes=[n00, n11, n01],
            material=steel,
            thickness=THICKNESS,
            local_x_direction=(1.0, 0.0, 0.0),
        ),
    )

# ── Apply surface pressure load ───────────────────────────────────────────────

load_case = LoadCase(name="Pressure")
SurfaceLoad(
    load_case=load_case,
    polygon=[
        SurfaceLoadVertex(0.0, 0.0, 0.0),
        SurfaceLoadVertex(LENGTH, 0.0, 0.0),
        SurfaceLoadVertex(LENGTH, WIDTH, 0.0),
        SurfaceLoadVertex(0.0, WIDTH, 0.0),
    ],
    magnitude=PRESSURE,
    direction=(0.0, 0.0, -1.0),
)
model.add_load_case(load_case)

# ── Save model ────────────────────────────────────────────────────────────────

file_path = os.path.join("json_input_solver", "142_Plate_Strip_Surface_Load.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
model.save_to_json(file_path, indent=4)

# ── Run analysis ──────────────────────────────────────────────────────────────

print("Running analysis...")
model.run_analysis()

results = model.resultsbundle.loadcases["Pressure"]

# ── Extract results ───────────────────────────────────────────────────────────

# Total reaction force in Z (sum of all fixed-end nodes)
total_reaction_fz = sum(node.nodal_forces.fz for node in results.reaction_nodes.values())

# Tip deflection: average of the two free-corner nodes (right edge)
right_bottom_id, right_top_id = columns[-1][0].id, columns[-1][1].id
tip_dz = 0.5 * (
    results.displacement_nodes[str(right_bottom_id)].dz + results.displacement_nodes[str(right_top_id)].dz
)

# Analytical reference
q = PRESSURE * WIDTH  # N/m
E = steel.e_mod
I = WIDTH * THICKNESS**3 / 12  # m⁴
tip_dz_analytical = -q * LENGTH**4 / (8 * E * I)

total_load = PRESSURE * LENGTH * WIDTH  # N

print(f"\nPlate strip results")
print(f"  Elements             : {len(model.plates)}")
print(f"  Total applied load   : {total_load:.1f} N")
print(f"  Total reaction Fz    : {abs(total_reaction_fz):.1f} N")

print(f"\n  Tip deflection (FERS)       : {tip_dz:.6f} m")
print(f"  Tip deflection (analytical) : {tip_dz_analytical:.6f} m")

rel_error = abs(tip_dz - tip_dz_analytical) / abs(tip_dz_analytical) * 100
print(f"  Relative error              : {rel_error:.1f} %")

if rel_error < 5.0:
    print("\nTip deflection within 5 % of analytical solution \u2705")
else:
    print(f"\nWARNING: tip deflection deviates {rel_error:.1f} % from analytical \u26a0\ufe0f")

print(f"\nModel saved to {file_path}")
