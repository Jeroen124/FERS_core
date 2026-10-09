"""
810 — Result Requests
=====================
Asks the solver for only the results a design check reads (engine 0.2.68):
member envelopes and the beam's start forces for the ULS combinations, the eave
displacements for SLS, and the ULS reactions. Nothing else comes back, and what
was not asked for reads as None, not zero.

Key features shown:
  • ResultRequest(block, members=..., nodes=..., limit_state=..., components=..., end=...)
  • limit_state on each LoadCombination, which requests select by
  • member_results / displacement_nodes / reaction_nodes, None where nothing was asked for
  • model.resultsbundle.selections: the (result_sets, ids, fields, components) arrays
  • a request the solver cannot meet is refused before the solve
"""

from fers_core import (
    FERS,
    AnalysisOrder,
    Material,
    Member,
    MemberSet,
    NodalLoad,
    NodalSupport,
    Node,
    ResultBlock,
    ResultRequest,
    Section,
)
from fers_core.loads.enums import LimitState
from fers_core.result_requests import nodes_of
from fers_core.unity_checks import classification


# =============================================================================
# Step 1: The portal frame of example 809, members classified for selecting
# =============================================================================
model = FERS()
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850, yield_stress=355e6)
column_section = Section.from_name("HEA200", steel)
beam_section = Section.from_name("IPE300", steel)

foot_left, eave_left = Node(0, 0, 0), Node(0, 4, 0)
eave_right, foot_right = Node(6, 4, 0), Node(6, 0, 0)
foot_left.nodal_support = NodalSupport()
foot_right.nodal_support = NodalSupport()

left_column = Member(
    start_node=foot_left, end_node=eave_left, section=column_section, classification="column"
)
beam = Member(start_node=eave_left, end_node=eave_right, section=beam_section, classification="beam")
right_column = Member(
    start_node=eave_right, end_node=foot_right, section=column_section, classification="column"
)
model.add_member_set(MemberSet(members=[left_column, beam, right_column]))

dead = model.create_load_case(name="Dead")
wind = model.create_load_case(name="Wind")
NodalLoad(node=eave_left, load_case=dead, magnitude=-20e3, direction=(0, 1, 0))
NodalLoad(node=eave_right, load_case=dead, magnitude=-20e3, direction=(0, 1, 0))
NodalLoad(node=eave_left, load_case=wind, magnitude=8e3, direction=(1, 0, 0))

# Requests select combinations by limit_state, as unity checks do; the solver
# does not read `situation`.
uls = model.create_load_combination("ULS 1", {dead: 1.35, wind: 1.5}, situation="ULS", check="ALL")
uls.limit_state = LimitState.ULS
sls = model.create_load_combination("SLS 1", {dead: 1.0, wind: 1.0}, situation="SLS", check="ALL")
sls.limit_state = LimitState.SLS

options = model.settings.analysis_options
options.order = AnalysisOrder.LINEAR


# =============================================================================
# Step 2: Ask for what the checks read
# =============================================================================
columns, beams = classification("column"), classification("beam")
options.result_requests = [
    ResultRequest(
        ResultBlock.LOCAL_ENVELOPES,
        members=[columns, beams],
        limit_state="ULS",
        components=["fx", "my", "mz"],
    ),
    ResultRequest(
        ResultBlock.LOCAL_END_FORCES,
        members=beams,
        limit_state="ULS",
        end="start",
        components=["fy", "mz"],
    ),
    ResultRequest(
        ResultBlock.NODE_DISPLACEMENTS,
        nodes=nodes_of(beams),
        limit_state="SLS",
        components=["dx", "dy"],
    ),
    ResultRequest(ResultBlock.REACTIONS, limit_state="ULS"),
]
model.run_analysis()


# =============================================================================
# Step 3: Read them as usual
# =============================================================================
uls_results = model.resultsbundle.loadcombinations["ULS 1"]
sls_results = model.resultsbundle.loadcombinations["SLS 1"]

result = uls_results.member_results[str(beam.id)]
print(f"Beam, ULS: max Mz = {result.local_maximums.mz / 1e3:.1f} kNm")
print(f"Beam, ULS: Fy at the start = {result.local_start_forces.fy / 1e3:.1f} kN")
# Not requested, so None rather than a zero a check could pass on:
print("Beam, ULS: torsion envelope =", result.local_maximums.mx)
print("Beam, ULS: forces at the end =", result.local_end_forces.fy)

sway = sls_results.displacement_nodes[str(eave_right.id)].dx
print(f"Right eave, SLS: sway = {sway * 1000:.2f} mm")
print("Right eave, SLS: rotation =", sls_results.displacement_nodes[str(eave_right.id)].rz)
print("Displacements for ULS were not asked for:", dict(uls_results.displacement_nodes))

reaction = uls_results.reaction_nodes[str(foot_left.id)].nodal_forces
print(f"Left foot, ULS: Fy = {reaction.fy / 1e3:.1f} kN")


# =============================================================================
# Step 4: The arrays behind them
# =============================================================================
# One entry per request and group of result sets; `values` is a read-only numpy
# array shaped (result_sets, ids, fields, components), with each axis listed.
for selection in model.resultsbundle.selections:
    print(
        f"{selection['block']:<20} {selection['group']:<17} sets {selection['result_sets']} "
        f"ids {selection['ids']} fields {selection['fields']} components {selection['components']}"
        f" -> {selection['values'].shape}"
    )

envelopes = model.resultsbundle.selections[0]
components = envelopes["components"]
bending = abs(envelopes["values"][..., [components.index("my"), components.index("mz")]])
for position, member_id in enumerate(envelopes["ids"]):
    largest = bending[:, position].max()
    print(f"Member {member_id}: largest bending moment over the ULS combinations {largest / 1e3:.1f} kNm")


# =============================================================================
# Step 5: A request that cannot be met is refused before the solve
# =============================================================================
options.result_requests = [ResultRequest(ResultBlock.REACTIONS, limit_state="ALS")]
try:
    model.run_analysis()
except RuntimeError as error:
    print("Refused:", str(error).strip().splitlines()[-1].lstrip(" -"))
