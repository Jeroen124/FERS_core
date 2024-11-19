import os
from FERS_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad

# =============================================================================
# Define Parameters for the Cantilever Beam
# =============================================================================

# Material properties
e_mod = 200e9  # Modulus of Elasticity (Pa)
g_mod = 77e9  # Shear Modulus (Pa)
density = 7850  # Density (kg/m³)
yield_stress = 235e6  # Yield Stress (Pa)

# Beam geometry and section properties
length = 5  # Beam length (m)
area = 1960e-6  # Cross-sectional area (m²)
i_y = 10.63e-6  # Moment of inertia about the y-axis (m⁴)
i_z = 0.819e-6  # Moment of inertia about the z-axis (m⁴)
j = 2.7e-08  # Torsional constant (m⁴)
section_height = 0.177  # Approximate section height (m)

# Load and support conditions
load_magnitude = -1000  # Downward force at free end (N)
load_direction = (0, -1, 0)  # Global y-axis direction

# =============================================================================
# Model Setup
# =============================================================================

# Create analysis object
calculation_1 = FERS()

# Create nodes
node1 = Node(0, 0, 0)  # Fixed end
node2 = Node(length, 0, 0)  # Free end

# Create material
Steel_S235 = Material(name="Steel", e_mod=e_mod, g_mod=g_mod, density=density, yield_stress=yield_stress)

# Create a section
section = Section(name="IPE 180 Beam Section", material=Steel_S235, i_y=i_y, i_z=i_z, j=j, area=area)

# Create member
beam = Member(start_node=node1, end_node=node2, section=section)

# Create and assign boundary conditions
wall_support = NodalSupport()  # Fixed in all 6 DOFs
node1.nodal_support = wall_support

# Create a memberset holding the beam
membergroup1 = MemberSet(members=[beam])
calculation_1.add_member_set(membergroup1)

# Create a load case and apply the nodal load at node2
end_load_case = calculation_1.create_load_case(name="End Load")
nodal_load = NodalLoad(
    node=node2, load_case=end_load_case, magnitude=load_magnitude, direction=load_direction
)

# Save the model to a JSON file
file_path = os.path.join("examples", "json_input_solver", "1_cantilever_with_end_load.json")
calculation_1.save_to_json(file_path, indent=4)

# =============================================================================
# Perform Beam Equation Calculations, https://mechanicalc.com/reference/beam-analysis
# =============================================================================

beam_deflection = (load_magnitude * length**3) / (3 * e_mod * i_y)
beam_reaction_force_y = -load_magnitude
beam_reaction_moment_z = abs(load_magnitude * length)
y_max = section_height / 2
beam_sigma_max = (beam_reaction_moment_z * y_max) / i_z


# Perform assertions using beam theory


# =============================================================================
# Print Results
# =============================================================================

print("=== Results ===")
print(f"Deflection at free end (node2): {beam_deflection:.6f} m")
print("Reaction forces at fixed end (node1):")
print(f"  Vertical Reaction Force (R_y): {beam_reaction_force_y:.2f} N")
print(f"  Reaction Moment (M_z): {beam_reaction_moment_z:.2f} N·m")
print("Maximum Bending Stress:")
print(f"  σ_max: {beam_sigma_max / 1e6:.2f} MPa")
