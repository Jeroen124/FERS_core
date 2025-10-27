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
node4 = Node(5, 0, -1)  # Rope end
node5 = Node(5, 0, 1)  # Rope end

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

rope_1 = Member(start_node=node3, end_node=node4, section=section, member_type="TENSION")
rope_2 = Member(start_node=node3, end_node=node5, section=section, member_type="TENSION")

# Creating a boundary conditions (by default all 6 d.o.f. are constraint)
simply_supported = NodalSupport(
    displacement_conditions={
        "X": SupportCondition.fixed(),
        "Y": SupportCondition.fixed(),
        "Z": SupportCondition.fixed(),
    },
    rotation_conditions={
        "X": SupportCondition.free(),
        "Y": SupportCondition.free(),
        "Z": SupportCondition.free(),
    },
)

# Assigning the nodal_support to the correct node.
node1.nodal_support = simply_supported
node2.nodal_support = simply_supported
node4.nodal_support = simply_supported
node5.nodal_support = simply_supported

# =============================================================================
# Now that the geometrical part is created. Lets create the model and the loadcases
# =============================================================================
# Create a memberset holding the beam
membergroup = MemberSet(members=[beam1, beam2])
ropegroup = MemberSet(members=[rope_1, rope_2])

# Adding the memberset to the model
calculation_1.add_member_set(*[membergroup, ropegroup])

# Create a loadcase for the end load
end_load_case_x = calculation_1.create_load_case(name="End Load x")
end_load_case_y = calculation_1.create_load_case(name="End Load y")
end_load_case_z = calculation_1.create_load_case(name="End Load z")

# Apply end load at node2 1 kN downward force (global y-axis) to the loadcase
nodal_load = NodalLoad(node=node3, load_case=end_load_case_x, magnitude=-100, direction=(1, 0, 0))
nodal_load = NodalLoad(node=node3, load_case=end_load_case_y, magnitude=-10000, direction=(0, 1, 0))
nodal_load = NodalLoad(node=node3, load_case=end_load_case_z, magnitude=-100, direction=(0, 0, 1))

ultimate_persistent_combination = calculation_1.create_load_combination(
    name="A simple combination",
    load_cases_factors={
        end_load_case_x: 1,
        end_load_case_y: 1,
        end_load_case_z: 1,
    },
    situation="ULS",
    check="ALL",
)

# Run analysis
calculation_1.settings.analysis_options.order = AnalysisOrder.LINEAR

file_path = os.path.join("json_input_solver", "093_Loadcombinations_hooked_cantilever.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
calculation_1.save_to_json(file_path, indent=4)

# Step 3: Run FERS calculation
# ----------------------------
# Perform the analysis using the saved JSON model file
print("Running the analysis...")
calculation_1.run_analysis()
result_loadcase_1 = calculation_1.resultsbundle.loadcases["End Load x"]
result_loadcase_2 = calculation_1.resultsbundle.loadcases["End Load y"]
result_loadcombination = calculation_1.resultsbundle.loadcombinations["A simple combination"]

dy_node_3_loadcase_1 = result_loadcase_1.displacement_nodes["3"].dy
dy_node_3_loadcase_2 = result_loadcase_2.displacement_nodes["3"].dy

expected_deformation_loadcases = dy_node_3_loadcase_1 + 2 * dy_node_3_loadcase_2
dy_node_3_loadcombination = result_loadcombination.displacement_nodes["3"].dy
