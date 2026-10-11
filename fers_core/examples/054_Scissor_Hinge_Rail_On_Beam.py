"""
054 — Scissor Hinge: a Rail on a Beam
=====================================
A rail runs continuously over a cross beam and rests on it: one beam along its
length, free to turn on the beam. Put the rail's members in a member set of
their own and give the set a ScissorHinge (engine 0.2.68): where the rail meets
the beam, it stays continuous and turns relative to the beam about the released
global axes. Four members, no link member, no extra node.

The model: two 1 m rail spans A-M-B along X, a beam through M along Z clamped
at both ends, and 1 kN/m on span A-M. On a knife edge the rail carries qL^2/16
over M; this beam yields a little.

Key features shown:
  • MemberSet(members=..., scissor_hinge=ScissorHinge(...))
  • 0.0 frees a rotation, None holds it, a positive value is a rotational spring
  • what the rigid connection and member hinges give instead
"""

from fers_core import (
    FERS,
    AnalysisOrder,
    DistributedLoad,
    Material,
    Member,
    MemberHinge,
    MemberSet,
    NodalSupport,
    Node,
    ScissorHinge,
    Section,
)
from fers_core.supports.supportcondition import SupportCondition

L, Q = 1.0, 1000.0  # m, N/m


def rail_on_beam(rail_hinge=None, member_hinges=False):
    model = FERS()
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
    rail_section = Section(name="rail", material=steel, i_y=1e-6, i_z=1e-6, j=1e-7, area=1e-3)
    beam_section = Section(name="beam", material=steel, i_y=1e-4, i_z=1e-4, j=1e-4, area=5e-3)

    # A pinned, B a roller along X; both hold the rail's twist.
    rotations = {"X": SupportCondition.fixed(), "Y": SupportCondition.free(), "Z": SupportCondition.free()}
    a = Node(0.0, 0.0, 0.0)
    a.nodal_support = NodalSupport(rotation_conditions=rotations)
    b = Node(2 * L, 0.0, 0.0)
    b.nodal_support = NodalSupport(
        displacement_conditions={
            "X": SupportCondition.free(),
            "Y": SupportCondition.fixed(),
            "Z": SupportCondition.fixed(),
        },
        rotation_conditions=rotations,
    )
    m = Node(L, 0.0, 0.0)
    beam_start, beam_end = Node(L, 0.0, -0.5), Node(L, 0.0, 0.5)
    beam_start.nodal_support = beam_end.nodal_support = NodalSupport()  # clamped

    # A member along X has local z = global Z, so vertical bending is about Z.
    pin = MemberHinge(rotational_release_mz=0.0) if member_hinges else None
    rail_1 = Member(start_node=a, end_node=m, section=rail_section, end_hinge=pin)
    rail_2 = Member(start_node=m, end_node=b, section=rail_section, start_hinge=pin)
    model.add_member_set(MemberSet(members=[rail_1, rail_2], classification="Rail", scissor_hinge=rail_hinge))
    model.add_member_set(
        MemberSet(
            members=[
                Member(start_node=beam_start, end_node=m, section=beam_section),
                Member(start_node=m, end_node=beam_end, section=beam_section),
            ],
            classification="Beam",
        )
    )

    case = model.create_load_case(name="span 1")
    DistributedLoad(member=rail_1, load_case=case, magnitude=Q, end_magnitude=Q, direction=(0, -1, 0))
    model.run_analysis()
    result = model.resultsbundle.loadcases["span 1"].member_results[str(rail_1.id)]
    return abs(result.local_end_forces.mz), result


print(f"Knife edge: rail moment over M = qL^2/16 = {Q * L**2 / 16:.1f} Nm\n")

rigid, _ = rail_on_beam()
print(f"Rail joined rigidly to the beam:       {rigid:6.1f} Nm  (the beam's torsion clamps it)")
split, _ = rail_on_beam(member_hinges=True)
print(f"Member hinges on both rail ends at M:  {split:6.1f} Nm  (two separate spans)")

# Free about Z (the rail bends vertically over the beam) and Y (it turns in
# plan); X is left out, so the rail's twist stays tied to the beam.
scissor = ScissorHinge(rotational_release_y=0.0, rotational_release_z=0.0)
moment, result = rail_on_beam(rail_hinge=scissor)
print(f"Scissor hinge on the rail set:         {moment:6.1f} Nm  (a continuous rail on the beam)")

# The rail turns at M; the node's own rotation is the beam's, which takes no torque.
print(f"  rail rotation at M: {result.local_displacement_end_node.rz * 1000:.3f} mrad")

# A positive value is a linear rotational spring between the rail and the beam.
sprung, _ = rail_on_beam(rail_hinge=ScissorHinge(rotational_release_z=4.0e5))
print(f"Scissor hinge, 400 kNm/rad about Z:    {sprung:6.1f} Nm  (between the two)")
