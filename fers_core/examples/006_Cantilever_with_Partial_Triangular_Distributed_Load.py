import os
from fers_core import (
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
# Example and Validation: Cantilever Beam with Uniform Distributed Load
# =============================================================================

# Step 1: Set up the model
# -------------------------
# Create the main FERS object that will manage the analysis
calculation_1 = FERS()

# Define the geometry of the beam
node1 = Node(0, 0, 0)  # Fixed end of the beam
node2 = Node(5, 0, 0)  # Free end of the beam, 5 meters away

# Define the material properties (Steel S235)
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Define the beam cross-section (IPE 180)
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_y=0.819e-6, i_z=10.63e-6, j=0.027e-6, area=0.00196
)


# Create the beam element
beam = Member(start_node=node1, end_node=node2, section=section)

# Apply a fixed support at the fixed end (node1)
wall_support = NodalSupport()
node1.nodal_support = wall_support

# Add the beam to a member group
membergroup1 = MemberSet(members=[beam])

# Add the member group to the calculation model
calculation_1.add_member_set(membergroup1)

# Step 2: Apply the load
# ----------------------
# Create a load case for the analysis
load_case_1 = calculation_1.create_load_case(name="Triangular Load")
load_case_2 = calculation_1.create_load_case(name="Inverse Triangular Load")

# Apply a uniform distributed load (e.g., w = 1000 N/m) downward along the entire beam
distributed_load = DistributedLoad(
    member=beam,
    load_case=load_case_1,
    magnitude=1000.0,  # 1000 N/m (example triangular load)
    direction=(0, -1, 0),  # Downward in the global Y-axis
    start_frac=0,  # Start at 0% of the member length
    end_frac=0.6,  # End at 60% of the member length
)

distributed_load = DistributedLoad(
    member=beam,
    load_case=load_case_2,
    magnitude=1000.0,  # 1000 N/m (example triangular load)
    direction=(0, -1, 0),  # Downward in the global Y-axis
    start_frac=0.3,  # Start at 30% of the member length
    end_frac=0.7,  # End at 70% of the member length
)

# Save the model to a file for FERS calculations
file_path = os.path.join("json_input_solver", "006_Cantilever_with_Triangular_Distributed_Load.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
print("Running the analysis...")
calculation_1.run_analysis()
results_triangular = calculation_1.resultsbundle.loadcases["Triangular Load"]
results_inverse = calculation_1.resultsbundle.loadcases["Inverse Triangular Load"]

# Extract results from the analysis
# Displacement at the free end in the y-direction
dy_fers_triangular = results_triangular.displacement_nodes["2"].dy
dy_fers_triangular_inverse = results_inverse.displacement_nodes["2"].dy
# Reaction moment at the fixed end
Fy_fers_triangular = results_triangular.reaction_nodes["1"].nodal_forces.fy
Fy_fers_triangular_inverse = results_inverse.reaction_nodes["1"].nodal_forces.fy

Mz_fers_triangular = results_triangular.reaction_nodes["1"].nodal_forces.mz
Mz_fers_triangular_inverse = results_inverse.reaction_nodes["1"].nodal_forces.mz

# Step 4: Validate Results Against Analytical Solution
# ----------------------------------------------------
# Analytical solution parameters for a cantilever with a uniform load 'w' over length L
w = 1000.0  # N/m (same as above)
L = 5  # Beam length in meters
E = 210e9  # Elastic modulus (Pascals)
I = 10.63e-6  # Moment of inertia (m^4)

# The maximum moment at the fixed end is:
Shear_max_analytical_triangular = w * (1 / 2) * L * (0.6 - 0)
Shear_max_analytical_inverse = w * (1 / 2) * L * (0.7 - 0.3)

M_max_analytical_triangular = Shear_max_analytical_triangular * ((0 + 0.6) * L * (1 / 3))
M_max_analytical_inverse = Shear_max_analytical_inverse * ((0.3 + (2 / 3) * (0.7 - 0.3)) * L)


print(f"Reaction force at fixed end (FERS): {Fy_fers_triangular:.6f} Nm")
print(f"Reaction force at fixed end (Analytical): {Shear_max_analytical_triangular:.6f} Nm")
if abs(Fy_fers_triangular - Shear_max_analytical_triangular) < 1e-3:
    print("Reaction force matches the analytical solution ✅")
else:
    print("Reaction force does NOT match the analytical solution ❌")

print()


print(f"Reaction force at fixed end (FERS): {Fy_fers_triangular_inverse:.6f} Nm")
print(f"Reaction force at fixed end (Analytical): {Shear_max_analytical_inverse:.6f} Nm")
if abs(Fy_fers_triangular_inverse - Shear_max_analytical_inverse) < 1e-3:
    print("Reaction force matches the analytical solution ✅")
else:
    print("Reaction force does NOT match the analytical solution ❌")

print()

print(f"Reaction moment at fixed end (FERS): {Mz_fers_triangular:.6f} Nm")
print(f"Reaction moment at fixed end (Analytical): {M_max_analytical_triangular:.6f} Nm")
if abs(Mz_fers_triangular - M_max_analytical_triangular) < 1e-3:
    print("Reaction moment matches the analytical solution ✅")
else:
    print("Reaction moment does NOT match the analytical solution ❌")

print()

print(f"Reaction moment at fixed end (FERS): {Mz_fers_triangular_inverse:.6f} Nm")
print(f"Reaction moment at fixed end (Analytical): {M_max_analytical_inverse:.6f} Nm")
if abs(Mz_fers_triangular_inverse - M_max_analytical_inverse) < 1e-3:
    print("Reaction moment matches the analytical solution ✅")
else:
    print("Reaction moment does NOT match the analytical solution ❌")

# =============================================================================
# Notes for Users
# =============================================================================
# This script demonstrates how to set up and analyze a cantilever beam with a uniform distributed load.
# It validates the FERS results against the classical analytical solutions for deflection and moment.
# You can adapt this script for your own models or include it in a CI/CD pipeline for regression testing.
