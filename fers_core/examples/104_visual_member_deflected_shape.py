import os
from fers_core import (
    AnalysisOrder,
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    DistributedLoad,
)


# =============================================================================
# Example: load-exact member deflected shape (member_displacements)
# =============================================================================
# The solver can return, per member, a sampled deflected shape
# (`member_displacements`). Enable it with
# `analysis_options.include_member_deflected_shape = True`; the ResultRenderer
# then draws that curve instead of the client-side cubic-Hermite reconstruction.
#
# Requires fers_calculations >= 0.2.56. Between 0.2.40 and 0.2.55 the array
# existed but was itself a Hermite reconstruction, so under a span load it
# under-rendered the mid-span sag by w*L^4/(384*E*I) — the very thing this
# example claimed it fixed. Since 0.2.56 the shape is integrated from the
# member's internal force field and is exact, shear deformation included.
#
# The difference only shows up *between* the nodes: a finite-element solution has
# exact nodal displacements whatever the reconstruction does, so the endpoints
# always agreed. That is why the checks below deliberately sample the interior.

# Step 1: Set up the model
# -------------------------
calculation_1 = FERS()
calculation_1.settings.analysis_options.order = AnalysisOrder.LINEAR

# Ask the solver for the per-member sampled deflected shape.
calculation_1.settings.analysis_options.include_member_deflected_shape = True

node1 = Node(0, 0, 0)  # Fixed end
node2 = Node(5, 0, 0)  # Free end, 5 m away

Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=1.01e-6, i_z=13.21e-6, j=0.027e-6, area=0.00196
)

beam = Member(start_node=node1, end_node=node2, section=section)

wall_support = NodalSupport()
node1.nodal_support = wall_support

calculation_1.add_member_set(MemberSet(members=[beam]))

# Step 2: Apply a uniform distributed load (1000 N/m, downward)
# ------------------------------------------------------------
load_case = calculation_1.create_load_case(name="Uniform Load")
DistributedLoad(
    member=beam,
    load_case=load_case,
    magnitude=1000.0,
    direction=(0, -1, 0),
)

file_path = os.path.join("json_input_solver", "104_member_deflected_shape.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Solve
# -------------
print("Running the analysis...")
calculation_1.run_analysis()
results = calculation_1.resultsbundle.loadcases["Uniform Load"]

# Step 4: Inspect the sampled deflected shape
# -------------------------------------------
member_result = results.member_results[str(beam.id)]
samples = member_result.member_displacements  # list of (x_frac, (dx, dy, dz))

if not samples:
    raise RuntimeError(
        "member_displacements is empty — check that "
        "include_member_deflected_shape is set and fers_calculations >= 0.2.40."
    )

print(f"\nEngine returned {len(samples)} deflected-shape stations for member {beam.id}:")
for x_frac, (dx, dy, dz) in samples:
    print(f"  x/L = {x_frac:0.2f}   disp = ({dx: .6e}, {dy: .6e}, {dz: .6e}) m")

# Consistency: the end station (x/L = 1) must match the free-end node displacement,
# and the start station (x/L = 0) must be ~zero at the fixed support.
end_disp = results.displacement_nodes[str(node2.id)]
x_last, d_last = samples[-1]
x_first, d_first = samples[0]

tol = 1e-6 * (abs(end_disp.dy) + 1.0)
assert abs(x_first - 0.0) < 1e-9 and abs(x_last - 1.0) < 1e-9, "stations should span x/L = 0..1"
assert abs(d_first[1]) < tol, "start station should be ~0 at the fixed support"
assert abs(d_last[1] - end_disp.dy) < tol, "end station must equal the free-end node displacement"

print("\nConsistency checks:")
print(f"  start station dy = {d_first[1]: .6e} m   (fixed end, expected ~0) ✅")
print(f"  end   station dy = {d_last[1]: .6e} m   vs free-end node dy = {end_disp.dy: .6e} m ✅")

# The endpoints above are nodal values, so they were exact even when the curve
# between them was not. The interior is where the reconstruction is actually on
# trial — check every station against the textbook cantilever-under-UDL curve
#
#     w(x) = -q * x^2 * (6L^2 - 4Lx + x^2) / (24 EI)
#
# and against what a cubic Hermite would have produced, which falls short by the
# clamped-clamped term q*x^2*(L-x)^2/(24EI): 0.59 mm at mid-span here, about 6%.
q, span, e_mod, i_strong = 1000.0, 5.0, 210e9, 13.21e-6


def cantilever_udl(x):
    return -q * x**2 * (6 * span**2 - 4 * span * x + x**2) / (24 * e_mod * i_strong)


def hermite_shortfall(x):
    return q * x**2 * (span - x) ** 2 / (24 * e_mod * i_strong)


worst = max(abs(d[1] - cantilever_udl(xf * span)) for xf, d in samples)
assert worst < 1e-9, f"interior stations must lie on the analytic curve (worst {worst:.2e} m)"

mid_frac, mid = min(samples, key=lambda s: abs(s[0] - 0.5))
mid_x = mid_frac * span
print(f"  worst interior error vs closed form = {worst:.2e} m ✅")
print(
    f"  mid-span dy = {mid[1]: .6e} m   "
    f"(a Hermite curve would report {mid[1] + hermite_shortfall(mid_x): .6e} m)"
)

# Step 5: Visualise
# -----------------
# The deformed shape follows the engine's load-exact polyline, with an automatic
# fall back to client-side Hermite when member_displacements is absent — older
# engines, mode shapes, or the option simply being off.
#
# Interactive window:
calculation_1.plot_results_3d(loadcase="Uniform Load")
#
# Headless / save a picture instead:
#   from fers_core.visualization.result_renderer import ResultRenderer
#   renderer = ResultRenderer(calculation_1)
#   renderer.active_loadcase = "Uniform Load"
#   renderer.screenshot("deflected_shape.png")

# =============================================================================
# Notes for Users
# =============================================================================
# Set `include_member_deflected_shape = True` to get the per-member deflected
# polyline in the results (`MemberResult.member_displacements`).
#
# From 0.2.56 the curve is integrated from the member's own internal force field,
# so it is exact under any span load and includes shear deformation wherever the
# section carries a shear area. A member with no span load short-circuits to the
# end-DOF cubic, which is exact there — the two agree to machine precision.
#
# Stations are evenly spaced, except on a member the solver split internally at a
# mid-span point load: each segment is sampled over its own share of the parent's
# range and the segments are concatenated, so the slope kink lands exactly on the
# split. `x_frac` increases monotonically either way.
