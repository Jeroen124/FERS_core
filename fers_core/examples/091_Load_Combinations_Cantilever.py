import os
from fers_core import Node, Member, FERS, Material, Section, MemberSet, NodalSupport, NodalLoad, AnalysisOrder
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
end_load_case_1 = calculation_1.create_load_case(name="End Load 1")
end_load_case_2 = calculation_1.create_load_case(name="End Load 2")

# Apply end load at node2 1 kN downward force (global y-axis) to the loadcase
nodal_load = NodalLoad(node=node3, load_case=end_load_case_1, magnitude=-100, direction=(1, 0, 0))
nodal_load = NodalLoad(node=node3, load_case=end_load_case_2, magnitude=-100, direction=(1, 0, 0))

ultimate_persistent_combination = calculation_1.create_load_combination(
    name="A simple combination",
    load_cases_factors={
        end_load_case_1: 1,
        end_load_case_2: 2,
    },
    situation="SLS",
    check="ALL",
)

# Run analysis
calculation_1.settings.analysis_options.order = AnalysisOrder.LINEAR

file_path = os.path.join("json_input_solver", "091_Loadcombinations_cantilever.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
# Perform the analysis using the saved JSON model file
print("Running the analysis...")
calculation_1.run_analysis()
result_loadcase_1 = calculation_1.resultsbundle.loadcases["End Load 1"]
result_loadcase_2 = calculation_1.resultsbundle.loadcases["End Load 2"]
result_loadcombination = calculation_1.resultsbundle.loadcombinations["A simple combination"]

dy_node_3_loadcase_1 = result_loadcase_1.displacement_nodes["3"].dy
dy_node_3_loadcase_2 = result_loadcase_2.displacement_nodes["3"].dy

expected_deformation_loadcases = dy_node_3_loadcase_1 + 2 * dy_node_3_loadcase_2
dy_node_3_loadcombination = result_loadcombination.displacement_nodes["3"].dy

# # Print results
print("Displacement from loadcase 1 (node3):")
print(f"dy = {dy_node_3_loadcase_1:.6f} m")

print("Displacement from loadcase 2 (node3):")
print(f"dy = {dy_node_3_loadcase_2:.6f} m")

print("\nComparison of results:")
print(f"Deflection at end node (Loadcombination): {dy_node_3_loadcombination:.6f} m")
print(f"Deflection based on loadcases: {expected_deformation_loadcases:.6f} m")
if abs(dy_node_3_loadcombination - expected_deformation_loadcases) < 1e-6:
    print("Deflection matches the analytical solution ✅")
else:
    print("Deflection does NOT match the analytical solution ❌")


# print("\nReaction forces at fixed end (node1):")
# print(f"Fy = {node1.reaction_force[1]:.2f} kN")
# print(f"Mz = {node1.reaction_moment[2]:.2f} kN·m")

# # Calculate and print maximum bending stress
# i_z = beam.moment_of_inertia_z
# y_max = beam.height / 2
# M_max = abs(node1.reaction_moment[2])
# sigma_max = M_max * y_max / i_z

# print(f"\nMaximum bending stress: {sigma_max:.2f} MPa")
