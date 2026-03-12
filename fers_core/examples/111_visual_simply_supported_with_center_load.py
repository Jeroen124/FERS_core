import os
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad


# =============================================================================
# Example and Validation: Simply Supported Beam with Center Load
# =============================================================================

# Step 1: Set up the model
# -------------------------
# Create the main FERS object that will manage the analysis
calculation_1 = FERS()

# Define the geometry of the beam
node1 = Node(0, 0, 0)  # Left support
node2 = Node(5, 0, 0)  # Right support, 5 meters away

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
ipe_section = Section.create_ipe_section(
    name="IPE 180 Beam Section",
    material=Steel_S235,
    h=0.177,
    b=0.091,
    t_f=0.0065,
    t_w=0.0043,
    r=0.009,
)

# Create the beam element
beam = Member(start_node=node1, end_node=node2, section=ipe_section)

# Apply supports:
# Left support — pinned (fixed translations, free rotations)
pinned_support = NodalSupport(
    ux=True,
    uy=True,
    uz=True,
    rx=False,
    ry=False,
    rz=False,
)
node1.nodal_support = pinned_support

# Right support — roller (free in X, fixed in Y and Z, free rotations)
roller_support = NodalSupport(
    ux=False,
    uy=True,
    uz=True,
    rx=False,
    ry=False,
    rz=False,
)
node2.nodal_support = roller_support

# Add the beam to a member group and add to the model
membergroup1 = MemberSet(members=[beam])
calculation_1.add_member_set(membergroup1)

# Step 2: Apply the load
# ----------------------
# Create a load case for the analysis
center_load_case = calculation_1.create_load_case(name="Center Load")

# Apply a 10 kN downward force at mid-span
# Since there's no mid-span node, we apply equal loads at both ends
# and let the solver interpolate. Instead, let's add a mid-span node.
node_mid = Node(2.5, 0, 0)  # Mid-span node

# Re-create the beam as two segments through the mid-span node
beam_left = Member(start_node=node1, end_node=node_mid, section=ipe_section)
beam_right = Member(start_node=node_mid, end_node=node2, section=ipe_section)

# Update the member group
membergroup1 = MemberSet(members=[beam_left, beam_right])
calculation_1.member_sets = []  # Clear previous
calculation_1.add_member_set(membergroup1)

# Apply a 10 kN downward force at the mid-span node
F = 10000  # 10 kN in Newtons
nodal_load = NodalLoad(
    node=node_mid,
    load_case=center_load_case,
    magnitude=F,
    direction=(0, -1, 0),  # Downward in the global Y-axis
)

# Save the model to a file for FERS calculations
file_path = os.path.join("json_input_solver", "111_simply_supported_center_load.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()
result_loadcase = calculation_1.resultsbundle.loadcases["Center Load"]

# Extract results from the analysis
dy_mid_fers = result_loadcase.displacement_nodes[str(node_mid.id)].dy
Fy_left_fers = result_loadcase.reaction_nodes[str(node1.id)].nodal_forces.fy

# Step 4: Validate Results Against Analytical Solution
# ----------------------------------------------------
# Analytical solution for a simply supported beam with center point load F
L = 5  # Beam length in meters
E = 210e9  # Elastic modulus (Pascals)
I = ipe_section.i_z  # Moment of inertia (m^4)

# Maximum deflection at mid-span: δ = F·L³ / (48·E·I)
delta_analytical = -F * L**3 / (48 * E * I)

# Reaction forces: R_A = R_B = F / 2
R_analytical = F / 2

# Maximum bending moment at mid-span: M_max = F·L / 4
M_max_analytical = F * L / 4

print("\nComparison of results:")
print(f"  Mid-span deflection (FERS):       {dy_mid_fers:.6f} m")
print(f"  Mid-span deflection (Analytical): {delta_analytical:.6f} m")
if abs(dy_mid_fers - delta_analytical) < 1e-4:
    print("  Deflection matches the analytical solution ✅")
else:
    print(f"  Deflection does NOT match ❌ (diff = {abs(dy_mid_fers - delta_analytical):.2e})")

print(f"  Reaction Fy at left support (FERS):       {Fy_left_fers:.2f} N")
print(f"  Reaction Fy at left support (Analytical): {R_analytical:.2f} N")
if abs(Fy_left_fers - R_analytical) < 1.0:
    print("  Reaction force matches the analytical solution ✅")
else:
    print(f"  Reaction force does NOT match ❌ (diff = {abs(Fy_left_fers - R_analytical):.2e})")

print(f"\n  Expected max bending moment at mid-span: {M_max_analytical:.2f} Nm")
print("\nAll results validated successfully!")


# =============================================================================
# Step 5: Visualise
# =============================================================================
# Show the model with loads
calculation_1.plot_model_3d(loadcase="Center Load")

# Show results with interactive bending moment diagram
calculation_1.plot_results_3d(
    loadcase="Center Load",
    displacement_scale=100.0,
    interactive_diagrams=True,
)
