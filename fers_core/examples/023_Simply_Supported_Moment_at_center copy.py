import os
from fers_core import (
    Node,
    Member,
    FERS,
    Material,
    Section,
    MemberSet,
    NodalSupport,
    SupportCondition,
)
from fers_core.loads.nodalmoment import NodalMoment


# =============================================================================
# Example and Validation: Cantilever Beam with End Load
# =============================================================================

# Step 1: Set up the model
# -------------------------
# Create the main FERS object that will manage the analysis
calculation_1 = FERS()

# Define the geometry of the beam
node1 = Node(0, 0, 0)  # Simply supported side of the beam at x=0
node2 = Node(1.5, 0, 0)  # Simply supported side of the beam at x=1.5
node3 = Node(3, 0, 0)  # Intermediate node at x=3
node4 = Node(6, 0, 0)  # Simply supported side of the beam at x=6

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)

# Create the beam element
beam1 = Member(start_node=node1, end_node=node2, section=section)
beam2 = Member(start_node=node2, end_node=node3, section=section)
beam3 = Member(start_node=node3, end_node=node4, section=section)

# Apply a fixed support at the fixed end (node1)

simply_supported_support = NodalSupport(
    rotation_conditions={
        "X": SupportCondition.fixed(),
        "Y": SupportCondition.free(),
        "Z": SupportCondition.free(),
    }
)

node1.nodal_support = simply_supported_support
node4.nodal_support = simply_supported_support

# Add the beam to a member group
membergroup1 = MemberSet(members=[beam1, beam2, beam3])

# Add the member group to the calculation model
calculation_1.add_member_set(membergroup1)

# Step 2: Apply the load
# ----------------------
# Create a load case for the analysis
moment_load_case = calculation_1.create_load_case(name="Intermediate moment")

# Apply a uniform distributed load (e.g., w = 1000 N/m) downward along the entire beam
applied_moment = NodalMoment(
    node=node3,
    load_case=moment_load_case,
    magnitude=1000.0,  # 1000 NNm (example moment)
    direction=(0, 0, 1),  # Negative rotation about the global Z-axis
)

# Save the model to a file for FERS calculations
file_path = os.path.join("json_input_solver", "023_Simply_Supported_Moment_at_center.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
# Perform the analysis using the saved JSON model file
print("Running the analysis...")
calculation_1.run_analysis()
result_loadcase = calculation_1.results.loadcases["Intermediate moment"]

# Extract results from the analysis
dy_fers_intermediate = result_loadcase.displacement_nodes["3"].dy
dy_fers_quarter = result_loadcase.displacement_nodes["2"].dy
Mz_fers_begin_end = result_loadcase.member_results["1"].start_node_forces.mz
Mz_fers_intermediate = result_loadcase.member_results["2"].end_node_forces.mz
Vy_fers_start_node = result_loadcase.reaction_nodes["1"].nodal_forces.fy

# Step 4: Validate Results Against Analytical Solution
# ----------------------------------------------------
# Analytical solution parameters
W = 1000  # Force in Newtons
L = 6  # Length of the beam in meters
E = 210e9  # Modulus of elasticity in Pascals
I = 10.63e-6  # Moment of inertia in m^4
x = L / 2  # Distance to the free end for max deflection and slope
x_quarter = L / 4  # Distance to the free end for max deflection and slope
M0 = 1000  # Nm

# Calculate analytical solutions for deflection and moment
delta_analytical_intermediate = (-(M0 * x) / (24 * L * E * I)) * (L**2 - 4 * x**2)  # Max deflection
delta_analytical_quarter = (-(M0 * x_quarter) / (24 * L * E * I)) * (L**2 - 4 * x_quarter**2)
M_intermediate_node = M0 * (x / L)  # Max moment at intermediate node
Mz_begin_end = 0  # Max moment at the fixed end
Vy_begin_end = M0 / L  # Shear force at the start


# Compare FERS results with analytical solutions
print("\nComparison of results:")
print(f"Deflection at middle node (FERS): {dy_fers_intermediate:.6f} m")
print(f"Deflection at middle node (Analytical): {delta_analytical_intermediate:.6f} m")
if abs(dy_fers_intermediate - delta_analytical_intermediate) < 1e-6:
    print("Deflection matches the analytical solution ✅")
else:
    print("Deflection does NOT match the analytical solution ❌")

print()

print(f"Deflection at middle node (FERS): {dy_fers_quarter:.6f} m")
print(f"Deflection at middle node (Analytical): {delta_analytical_quarter:.6f} m")
if abs(dy_fers_quarter - delta_analytical_quarter) < 1e-6:
    print("Deflection matches the analytical solution ✅")
else:
    print("Deflection does NOT match the analytical solution ❌")

print()

print(f"Shear forces at start node (FERS): {Vy_fers_start_node:.6f} N")
print(f"Shear forces at start node (Analytical): {Vy_begin_end:.6f} N")
if abs(Vy_fers_start_node - Vy_begin_end) < 1e-6:
    print("Shear forces match the analytical solution ✅")
else:
    print("Shear forces do NOT match the analytical solution ❌")

print()

print(f"Bending moment at middle node (FERS): {Mz_fers_intermediate:.6f} Nm")
print(f"Bending moment at middle node (Analytical): {M_intermediate_node:.6f} Nm")
if abs(Mz_fers_intermediate - M_intermediate_node) < 1e-6:
    print("Bending moment matches the analytical solution ✅")
else:
    print("Bending moment does NOT match the analytical solution ❌")

print()


print(f"Reaction moment at begin (FERS): {Mz_fers_begin_end:.6f} Nm")
print(f"Reaction moment at begin (Analytical): {Mz_begin_end:.6f} Nm")
if abs(Mz_fers_begin_end - Mz_begin_end) < 1e-3:
    print("Reaction moment matches the analytical solution ✅")
else:
    print("Reaction moment does NOT match the analytical solution ❌")

print("\nAll results validated successfully!")

# =============================================================================
# Notes for Users
# =============================================================================
# This script is both an example and a validation tool.
# 1. It demonstrates how to set up and analyze a cantilever beam with an end load.
# 2. It validates the FERS results against analytical solutions for deflection and moment.
# 3. Run this script as-is to learn, or integrate it into your CI/CD pipeline for validation.
