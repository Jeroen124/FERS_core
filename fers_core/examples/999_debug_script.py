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

import ujson
import fers_calculations


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
load_case = calculation_1.create_load_case(name="Uniform Load 1")
load_case = calculation_1.create_load_case(name="Uniform Load 2")

# Apply a uniform distributed load (e.g., w = 1000 N/m) downward along the entire beam
distributed_load = DistributedLoad(
    member=beam,
    load_case=load_case,
    magnitude=1000.0,  # 1000 N/m (example uniform load)
    direction=(0, -1, 0),  # Downward in the global Y-axis
)

# Save the model to a file for FERS calculations
file_path = os.path.join("json_input_solver", "003_Cantilever_with_Uniform_Distributed_Load.json")
input_dict = calculation_1.to_dict()
input_json = ujson.dumps(input_dict)
result_string = fers_calculations.calculate_from_json(input_json)
result_list = ujson.loads(result_string)
