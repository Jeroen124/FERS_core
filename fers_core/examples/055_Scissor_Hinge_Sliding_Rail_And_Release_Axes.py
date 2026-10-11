"""
055 — Scissor Hinge: a Sliding Rail, a Turned Rack, and Release Axes
====================================================================
A rail resting on posts may slide along them as well as turn. A ScissorHinge
(engine 0.2.68) frees translations too, can be limited to some of the nodes the
rail meets, and can name its own axes, as a rack turned in plan needs. A
MemberHinge can release its rotations about global or user axes as well.

The model: a rail 1-2-3 along X over two posts (tops 2 and 3, fixed feet),
anchored at node 1, carrying 2 kN/m and pulled 1 kN along itself between the
posts.

Key features shown:
  • ScissorHinge(translational_release_x=0.0): the rail slides over the posts
  • MemberSet(..., scissor_hinge_nodes=[...]): hinged at one post only
  • ScissorHinge(axes=ReleaseAxes.user(x, y)): the same rack turned in plan
  • MemberHinge(rotation_axes=ReleaseAxes.GLOBAL): a skew beam freed about Z
"""

from math import cos, radians, sin

from fers_core import (
    FERS,
    AnalysisOrder,
    DistributedLoad,
    Material,
    Member,
    MemberHinge,
    MemberPointLoad,
    MemberSet,
    NodalSupport,
    Node,
    ReleaseAxes,
    ScissorHinge,
    Section,
)


def turn(angle, x, y, z):
    """A point turned about the vertical (Y) by ``angle`` radians."""
    return (x * cos(angle) + z * sin(angle), y, -x * sin(angle) + z * cos(angle))


def rail_over_posts(hinge=None, hinged_at=None, angle=0.0):
    model = FERS()
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
    # Alike about both axes: a vertical post's frame does not turn with the rack.
    frame = Section(name="frame", material=steel, i_y=4e-6, i_z=4e-6, j=1e-7, area=2e-3)

    anchor = Node(*turn(angle, 0.0, 0.0, 0.0))
    anchor.nodal_support = NodalSupport()
    tops = [Node(*turn(angle, x, 0.0, 0.0)) for x in (2.0, 4.0)]
    feet = [Node(*turn(angle, x, -1.5, 0.0)) for x in (2.0, 4.0)]
    for foot in feet:
        foot.nodal_support = NodalSupport()

    rail_1 = Member(start_node=anchor, end_node=tops[0], section=frame)
    rail_2 = Member(start_node=tops[0], end_node=tops[1], section=frame)
    model.add_member_set(
        MemberSet(
            members=[rail_1, rail_2],
            classification="Rail",
            scissor_hinge=hinge,
            scissor_hinge_nodes=None if hinged_at is None else [tops[i] for i in hinged_at],
        )
    )
    for top, foot in zip(tops, feet):
        model.add_member_set(MemberSet(members=[Member(start_node=foot, end_node=top, section=frame)]))

    case = model.create_load_case(name="pull")
    for rail in (rail_1, rail_2):
        DistributedLoad(
            member=rail, load_case=case, magnitude=2000.0, end_magnitude=2000.0, direction=(0, -1, 0)
        )
    MemberPointLoad(
        member=rail_2, load_case=case, position=0.5, magnitude=1000.0, direction=(1, 0, 0), axes="local"
    )
    model.run_analysis()
    result = model.resultsbundle.loadcases["pull"]
    along = (cos(angle), 0.0, -sin(angle))  # the rail's direction

    def post_share(foot):
        f = result.reaction_nodes[str(foot.id)].nodal_forces
        return f.fx * along[0] + f.fy * along[1] + f.fz * along[2]

    # round(...) + 0.0 prints a residual of -1e-12 as 0.0, not -0.0.
    shares = [round(post_share(foot), 1) + 0.0 for foot in feet]
    return shares, result.member_results[str(rail_1.id)].local_start_forces.fx


print("How much of the rail's 1 kN pull each post's foot takes:\n")

posts, _ = rail_over_posts()
print(f"Rail fixed to both posts:            {posts[0]:8.1f} N  {posts[1]:8.1f} N")

sliding = ScissorHinge(translational_release_x=0.0)
posts, axial = rail_over_posts(sliding)
print(f"Rail sliding over both posts:        {posts[0]:8.1f} N  {posts[1]:8.1f} N")
print(f"  so the anchor takes it all; rail force at the anchor {axial:.1f} N")

# Only the first post lets it slide; the rail is fixed to the second.
posts, _ = rail_over_posts(ScissorHinge(translational_release_x=0.0), hinged_at=[0])
print(f"Sliding over the first post only:    {posts[0]:8.1f} N  {posts[1]:8.1f} N")

# The same rack turned 30 degrees in plan: its hinge names the rail's own axes.
angle = radians(30)
rails_axes = ReleaseAxes.user(x=turn(angle, 1.0, 0.0, 0.0), y=(0.0, 1.0, 0.0))
posts, axial_turned = rail_over_posts(ScissorHinge(translational_release_x=0.0, axes=rails_axes), angle=angle)
print(f"Turned 30 degrees, sliding in its own axes: {posts[0]:.1f} N  {posts[1]:.1f} N")
print(f"  rail force at the anchor {axial_turned:.1f} N, as square to the globe")


# A purlin at 30 degrees in plan between two girders that run along X, pinned
# to them about the girders' axis, global X. In its own axes that pin would
# mix its torsion with its bending.
def purlin(pin):
    model = FERS()
    model.settings.analysis_options.order = AnalysisOrder.LINEAR
    steel = Material(name="S355", e_mod=210e9, g_mod=81e9, density=7850.0, yield_stress=355e6)
    section = Section(name="purlin", material=steel, i_y=2e-6, i_z=8e-6, j=2e-7, area=2e-3)
    ends = [Node(0.0, 0.0, 0.0), Node(*turn(angle, 4.0, 0.0, 0.0))]
    for end in ends:
        end.nodal_support = NodalSupport()  # the girders, taken as rigid
    middle = Node(*turn(angle, 2.0, 0.0, 0.0))
    halves = [
        Member(start_node=ends[0], end_node=middle, section=section, start_hinge=pin),
        Member(start_node=middle, end_node=ends[1], section=section, end_hinge=pin),
    ]
    model.add_member_set(MemberSet(members=halves))
    case = model.create_load_case(name="snow")
    for half in halves:
        DistributedLoad(
            member=half, load_case=case, magnitude=1000.0, end_magnitude=1000.0, direction=(0, -1, 0)
        )
    model.run_analysis()
    return model.resultsbundle.loadcases["snow"].displacement_nodes[str(middle.id)].dy


about_its_own_axis = purlin(MemberHinge(rotational_release_mz=0.0))
about_the_girders = purlin(MemberHinge(rotational_release_mx=0.0, rotation_axes=ReleaseAxes.GLOBAL))
print()
print("A purlin at 30 degrees in plan, pinned at both girders, under 1 kN/m:")
print(f"  pinned about its own horizontal axis: midspan {about_its_own_axis * 1000:.3f} mm")
print(f"  pinned about the girders' axis (X):   midspan {about_the_girders * 1000:.3f} mm")
