import os
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad
from fers_core.supports.supportcondition import SupportCondition


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
section = Section(
    name="IPE 180 Beam Section", material=Steel_S235, i_z=10.63e-6, i_y=0.819e-6, j=0.027e-6, area=0.00196
)

# Create member
beam1 = Member(start_node=node1, end_node=node2, section=section)
beam2 = Member(start_node=node2, end_node=node3, section=section)

# Creating a boundary conditions (by default all 6 d.o.f. are constraint)
wall_support = NodalSupport()
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
node2.nodal_support = fix_z_support
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
file_path = os.path.join("json_input_solver", "911_double_cantilever.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
# Perform the analysis using the saved JSON model file
print("Running the analysis...")
calculation_1.run_analysis()
result_loadcase = calculation_1.results.loadcases["End Load"]

d_node_2 = result_loadcase.displacement_nodes["2"]
d_node_3 = result_loadcase.displacement_nodes["3"]
dy_fers_2 = result_loadcase.displacement_nodes["2"].dy
dx_fers_3 = result_loadcase.displacement_nodes["3"].dx

# # Print results
print("Displacement at mid (node2):")
print(f"dy = {dy_fers_2:.6f} m")

# print("\nReaction forces at fixed end (node1):")
# print(f"Fy = {node1.reaction_force[1]:.2f} kN")
# print(f"Mz = {node1.reaction_moment[2]:.2f} kN·m")

# # Calculate and print maximum bending stress
# i_z = beam.moment_of_inertia_z
# y_max = beam.height / 2
# M_max = abs(node1.reaction_moment[2])
# sigma_max = M_max * y_max / i_z

# print(f"\nMaximum bending stress: {sigma_max:.2f} MPa")
