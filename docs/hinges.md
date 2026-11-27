# Hinges

## Scissor hinges: a continuous beam that turns on what it crosses

A rail running over beams and resting on each one is continuous along its
length, but free to turn on every beam. A `MemberHinge` releases one member end,
so releasing both rail ends at a beam splits the rail into two spans. Put the
rail's members in a member set of their own and give the set a `ScissorHinge`
instead. No link member or extra node is needed:

```python
from fers_core import FERS, DistributedLoad, Material, Member, MemberSet, NodalSupport, Node, ScissorHinge, Section
from fers_core.supports.supportcondition import SupportCondition as C

model = FERS()
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
rail_section = Section(name="rail", material=steel, i_y=1e-6, i_z=1e-6, j=1e-7, area=1e-3)
beam_section = Section(name="beam", material=steel, i_y=1e-4, i_z=1e-4, j=1e-4, area=5e-3)

turns = {"X": C.fixed(), "Y": C.free(), "Z": C.free()}
a, m, b = Node(0.0, 0.0, 0.0), Node(1.0, 0.0, 0.0), Node(2.0, 0.0, 0.0)
a.nodal_support = NodalSupport(rotation_conditions=turns)
b.nodal_support = NodalSupport(
    displacement_conditions={"X": C.free(), "Y": C.fixed(), "Z": C.fixed()}, rotation_conditions=turns
)
beam_start, beam_end = Node(1.0, 0.0, -0.5), Node(1.0, 0.0, 0.5)
beam_start.nodal_support = beam_end.nodal_support = NodalSupport()  # clamped

rail_1 = Member(start_node=a, end_node=m, section=rail_section)
rail_2 = Member(start_node=m, end_node=b, section=rail_section)
model.add_member_set(MemberSet(
    members=[rail_1, rail_2],
    scissor_hinge=ScissorHinge(rotational_release_y=0.0, rotational_release_z=0.0),
))
model.add_member_set(MemberSet(members=[
    Member(start_node=beam_start, end_node=m, section=beam_section),
    Member(start_node=m, end_node=beam_end, section=beam_section),
]))

span = model.create_load_case(name="span")
DistributedLoad(member=rail_1, load_case=span, magnitude=1000.0, end_magnitude=1000.0, direction=(0, -1, 0))
model.run_analysis()
mz = model.resultsbundle.loadcases["span"].member_results[str(rail_1.id)].local_end_forces.mz
print(f"{abs(mz):.1f} Nm")  # 62.4; a knife edge gives qL²/16 = 62.5, a rigid joint 122.6
```

- **Where it applies:** at every node where a member of the set meets a member
  outside the set, or a plate. There the set's members stay joined to each
  other and move relative to the node along and about the released axes.
  Nothing is released where the set meets only itself or a support, so the
  continuous beam's members belong in a set of their own; a set holding every
  member meets nothing, and the solver refuses it.
- **Only some of those nodes:** `MemberSet(scissor_hinge_nodes=[...])` lists
  where the hinge applies, for a beam that turns on some of the members it
  meets and is joined to the rest.
- **Each value** works as a `MemberHinge` release does: `None` holds it, `0.0`
  frees it, and a positive value is a spring between the set and the node, in
  force per length for a translation (`translational_release_x/_y/_z`) and
  moment per radian for a rotation (`rotational_release_x/_y/_z`).
- **The axes are global** unless the hinge names its own:
  `ScissorHinge(..., axes=ReleaseAxes.user(x=..., y=...))` takes the first axis
  along `x`, the second along `y` made perpendicular to it, and the third as
  their cross product, as a frame turned in plan needs.
- **Supports and nodal loads** at a released node act on the node, meaning the
  members outside the set. A node's reported displacement is theirs; the set's
  own motion there is in its members' `local_displacement_start_node` and
  `local_displacement_end_node`.
- **Two hinged sets crossing** with nothing else are each released from the
  node, so every axis either one releases is free between them.
- **A set of one member** gives a release about the hinge's axes at that
  member's ends.
- **Second order:** as with member hinges, a model with scissor hinges takes the
  corotational correction only when `NonlinearMethod.COROTATIONAL` is named.

A rail that may also slide over its posts frees that translation. Here it slides
over the first post only, so the second takes its share of the pull:

```python
from fers_core import (
    FERS, DistributedLoad, Material, Member, MemberPointLoad, MemberSet, NodalSupport, Node,
    ScissorHinge, Section,
)

model = FERS()
steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
frame = Section(name="frame", material=steel, i_y=4e-6, i_z=4e-6, j=1e-7, area=2e-3)
anchor, top_1, top_2 = Node(0.0, 0.0, 0.0), Node(2.0, 0.0, 0.0), Node(4.0, 0.0, 0.0)
foot_1, foot_2 = Node(2.0, -1.5, 0.0), Node(4.0, -1.5, 0.0)
anchor.nodal_support = foot_1.nodal_support = foot_2.nodal_support = NodalSupport()

rail_1 = Member(start_node=anchor, end_node=top_1, section=frame)
rail_2 = Member(start_node=top_1, end_node=top_2, section=frame)
model.add_member_set(MemberSet(
    members=[rail_1, rail_2],
    scissor_hinge=ScissorHinge(translational_release_x=0.0),  # slides along X
    scissor_hinge_nodes=[top_1],                               # over the first post only
))
for foot, top in ((foot_1, top_1), (foot_2, top_2)):
    model.add_member_set(MemberSet(members=[Member(start_node=foot, end_node=top, section=frame)]))

pull = model.create_load_case(name="pull")
DistributedLoad(member=rail_1, load_case=pull, magnitude=2000.0, end_magnitude=2000.0, direction=(0, -1, 0))
MemberPointLoad(member=rail_2, load_case=pull, position=0.5, magnitude=1000.0, direction=(1, 0, 0))
model.run_analysis()
reactions = model.resultsbundle.loadcases["pull"].reaction_nodes
takes = [abs(reactions[str(foot.id)].nodal_forces.fx) for foot in (foot_1, foot_2)]
print(f"post 1 takes {takes[0]:.1f} N, post 2 {takes[1]:.1f} N")  # 0.2 N and 67.2 N
```

A model that uses scissor hinges is written with `schema_version` 3, which an
older engine refuses rather than solve every connection as rigid. Without them,
a model is written as before.

`fers_core/examples/054_Scissor_Hinge_Rail_On_Beam.py` compares the rigid
connection, member hinges, the scissor hinge and a spring, and
`fers_core/examples/055_Scissor_Hinge_Sliding_Rail_And_Release_Axes.py` slides
the rail, limits the hinge to one post, and turns the frame in plan.

## Member hinges in global or user axes

A `MemberHinge` releases its rotations about its member's own axes. A beam at an
angle in plan, pinned about the girder it hangs from, needs a pin about the
girder's axis instead, which in the beam's own axes mixes its bending with its
torsion. `rotation_axes` names the axes the rotational releases, their stiffness
curves and their moment-rotation diagrams use:

```python
from fers_core import MemberHinge, ReleaseAxes

pin_about_x = MemberHinge(rotational_release_mx=0.0, rotation_axes=ReleaseAxes.GLOBAL)
```

`ReleaseAxes.LOCAL` (the default) keeps the member's axes; `ReleaseAxes.user(x, y)`
names a frame as above. A curve on such a hinge reads the end moment about the
same axes; the member's results stay in its local axes. Translational releases
stay member-local. A model whose member hinges release in other axes is written
with `schema_version` 3 as well. Release axes are fixed in space, so a
corotational solve does not turn them with the structure.
