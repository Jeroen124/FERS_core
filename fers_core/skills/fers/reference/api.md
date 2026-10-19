# FERS Python API: models that run as written

Each model block runs on its own after `pip install FERS` and prints what it
computed; a test runs them all. SI units throughout: m, N, Pa.

## A steel beam, checked to EN 1993-1-1

```python
from fers_core import check_beam

# IPE200 in S235, simply supported over 6 m, 10 kN/m characteristic.
# check_beam adds a ULS combination of 1.35 x the load and an EC3 member check.
model = check_beam(6.0, "IPE200", udl=10_000.0)
model.settings.analysis_options.include_member_deflected_shape = True
model.run_analysis()

beam = model.resultsbundle.loadcases["Q"].member_results["1"]
x_frac, (_, dy, _) = beam.member_displacement_peak
ec3 = model.unity_check_results()[0]
print(f"M {beam.local_minimums.mz / 1e3:.1f} kNm, sag {dy * 1e3:.1f} mm, EC3 {ec3['max_utilization']:.2f}")
```

`support` is `"simply_supported"`, `"cantilever"` or `"fixed"`; `point_load` (N) and
`point_position` (fraction of the span) add a point load. `create_beam` takes the same
arguments without the check and splits the span into 8 elements, so nodal results
exist along it (its load case is `"Load"`).

## A column in compression

```python
from fers_core import check_strut

# HEA200 in S235, 3 m, 400 kN; buckling length factors per axis (local z is strong).
model = check_strut(3.0, "HEA200", axial_load=400_000.0, k_y=1.0, k_z=1.0)
model.run_analysis()
print(f"EC3 {model.unity_check_results()[0]['max_utilization']:.2f}")
```

## A portal frame built by hand

```python
from fers_core import (
    FERS, AnalysisOrder, DistributedLoad, MaterialLibrary, Member, MemberSet, NodalLoad,
    NodalSupport, Node, Section,
)
from fers_core.unity_checks import all_members, ec3_steel_check

model = FERS()  # create it first: it restarts the id counters
model.settings.analysis_options.order = AnalysisOrder.LINEAR
steel = MaterialLibrary.get("S235")
hea200, ipe300 = Section.from_name("HEA200", steel), Section.from_name("IPE300", steel)

# 6 m wide, 4 m tall, in the XY plane (Y up), fixed at both bases.
a, b = Node(0, 0, 0, nodal_support=NodalSupport()), Node(6, 0, 0, nodal_support=NodalSupport())
c, d = Node(0, 4, 0), Node(6, 4, 0)
girder = Member(start_node=c, end_node=d, section=ipe300)
for start, end in ((a, c), (b, d)):
    # rotation_angle=90: the column bends about its strong axis in the XY plane.
    # Sway frame: in-plane buckling about local z with L_cr = 2 x 4 m.
    column = Member(start_node=start, end_node=end, section=hea200, rotation_angle=90)
    model.add_member_set(MemberSet(members=[column], effective_length_factor_z=2.0))
model.add_member_set(MemberSet(members=[girder]))

dead, wind = model.create_load_case(name="G"), model.create_load_case(name="W")
DistributedLoad(member=girder, load_case=dead, magnitude=10_000.0, direction=(0, -1, 0))
NodalLoad(node=c, load_case=wind, magnitude=5_000.0, direction=(1, 0, 0))
model.create_load_combination("ULS", {dead: 1.35, wind: 1.5}, limit_state="ULS")
model.create_load_combination("SLS", {dead: 1.0, wind: 1.0}, limit_state="SLS")
model.add_unity_check(ec3_steel_check("ec3", "EN 1993-1-1", applies_to=all_members(), limit_state="ULS"))
model.run_analysis()

sls = model.resultsbundle.loadcombinations["SLS"]
print(f"sway {sls.displacement_nodes[str(c.id)].dx * 1000:.2f} mm")
print(f"left base Fy {sls.reaction_nodes[str(a.id)].nodal_forces.fy / 1000:.2f} kN")
print(f"EC3 {model.unity_check_results()[0]['max_utilization']:.2f}")
```

Supports: `NodalSupport()` is fully fixed. A pin frees the rotations,
`NodalSupport(rotation_conditions={"X": "Free", "Y": "Free", "Z": "Free"})`; a roller
also frees a translation, `displacement_conditions={"X": "Free"}`. A member of
`member_type="Truss"` carries axial force only.

## Handing the model to the user

```python
model.save_to_json("model.json")  # the input, plus the results once solved
```

Without a way to run FERS, give the user `model.json` and tell them to open
https://ferscloud.com/studio, File → Import JSON..., which solves it in their browser.
`fers validate model.json` checks a file before you hand it over.
