import os
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad
from fers_core.supports.supportcondition import SupportCondition
import math

# =============================================================================
# Creating a cantilever with an end_load
# =============================================================================
# Create analysis object
calculation_1 = FERS()


# Create nodes
node1 = Node(0, 0, 0)  # Fixed end
node2 = Node(5, 0, 0)  # Free end
node3 = Node(5, 5, 0)  # Free end

# Create material
Steel_S235 = Material(name="Steel", e_mod=210e9, g_mod=80.769e9, density=7850, yield_stress=235e6)

# Create a section
# For example IPE 180: https://eurocodeapplied.com/design/en1993/ipe-hea-heb-hem-design-properties
ipe_section = Section.create_ipe_section(
    name="IPE 180 Beam Section",
    material=Steel_S235,
    h=0.177,
    b=0.091,
    t_f=0.0065,
    t_w=0.0043,
    r=0.009,
)

# Create member
beam1 = Member(start_node=node1, end_node=node2, section=ipe_section)
beam2 = Member(start_node=node2, end_node=node3, section=ipe_section, rotation_angle=math.pi / 2)

# Creating a boundary conditions (by default all 6 d.o.f. are constraint)
wall_support = NodalSupport(
    rotation_conditions={
        "X": SupportCondition.free(),
        "Y": SupportCondition.free(),
        "Z": SupportCondition.free(),
    }
)
fix_z_support = NodalSupport(
    displacement_conditions={
        "X": SupportCondition.free(),
        "Y": SupportCondition.free(),
        "Z": SupportCondition.fixed(),
    },
    rotation_conditions={
        "X": SupportCondition.free(),
        "Y": SupportCondition.free(),
        "Z": SupportCondition.free(),
    },
)


# Assigning the nodal_support to the correct node.
node1.nodal_support = wall_support
node2.nodal_support = wall_support
node3.nodal_support = fix_z_support

# =============================================================================
# Now that the geometrical part is created. Lets create the model and the loadcases
# =============================================================================
# Create a memberset holding the beam
membergroup1 = MemberSet(members=[beam1])
membergroup2 = MemberSet(members=[beam2])

# Adding the memberset to the model
calculation_1.add_member_set(*[membergroup1, membergroup2])

# Create a loadcase for the end load
end_load_case = calculation_1.create_load_case(name="End Load")

# Apply end load at node2 1 kN downward force (global y-axis) to the loadcase
nodal_load = NodalLoad(node=node3, load_case=end_load_case, magnitude=-1000, direction=(1, 0, 0))

# Run analysis
file_path = os.path.join("json_input_solver", "181_Visual_Double_cantilever.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
# Perform the analysis using the saved JSON model file
print("Running the analysis...")
calculation_1.run_analysis()
result_loadcase = calculation_1.results.loadcases["End Load"]

dx_fers_3 = result_loadcase.displacement_nodes["3"].dx
expected_dx_fers_3 = -0.074714  # From other FEM software

# Compare FERS results with analytical solutions
print("\nComparison of results:")
print(f"Deflection at free end (FERS): {dx_fers_3:.6f} m")
print(f"Deflection at free end (Analytical): {expected_dx_fers_3:.6f} m")
if abs(dx_fers_3 - expected_dx_fers_3) < 1e-6:
    print("Deflection matches the analytical solution ✅")
else:
    print("Deflection does NOT match the analytical solution ❌")

print()

# print("\nReaction forces at fixed end (node1):")
# print(f"Fy = {node1.reaction_force[1]:.2f} kN")
# print(f"Mz = {node1.reaction_moment[2]:.2f} kN·m")

# # Calculate and print maximum bending stress
# i_z = beam.moment_of_inertia_z
# y_max = beam.height / 2
# M_max = abs(node1.reaction_moment[2])
# sigma_max = M_max * y_max / i_z

# print(f"\nMaximum bending stress: {sigma_max:.2f} MPa")
