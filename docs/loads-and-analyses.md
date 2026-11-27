# Self-weight, seismic analysis and reports

## A member's self-weight

The solver works out each member's self-weight, density·area·g, and puts it in
the load case that `self_weight_load_case_id` names. A load combination carries
the self-weight only if it includes that case, so give it your permanent-load
case: `create_load_case("G", self_weight=True)` creates G and sets both options.

```python
from fers_core.builders import create_beam

model = create_beam(6.0, "IPE300", udl=5_000.0, load_case_name="Q")   # 5 kN/m imposed load
imposed = model.load_cases[0]
dead = model.create_load_case("G", self_weight=True)                   # G takes the self-weight
model.create_load_combination("ULS", {dead: 1.35, imposed: 1.5}, limit_state="ULS")
model.run_analysis()

uls = model.resultsbundle.loadcombinations["ULS"]
print(round(sum(r.nodal_forces.fy for r in uls.reaction_nodes.values()), 1))   # 48357.4
```

The ULS reactions are 1.5 × 30 kN plus 1.35 × the beam's 2.49 kN. With
`enable_self_weight` set and no `self_weight_load_case_id`, the solver puts the
self-weight in a load case of its own, "Self-weight", which combinations built
from your load cases do not include. `run_analysis` refuses such a model when it
has combinations, rather than solve every one of them without self-weight, and
the solver warns with `self_weight_not_in_combinations` on each combination. A
model without combinations solves, and its "Self-weight" case is a result of its
own, as below.

The solver also works out each member's mass for modal and seismic analysis from
the section. A member that carries more, such as cladding or a services run, can
override both:

```python
from fers_core.builders import create_beam

model = create_beam(5.0, "IPE180")                  # no load but its own weight
model.settings.analysis_options.enable_self_weight = True
for member in model.members:
    member.weight_override = 1500.0                 # N/m, gravity included
model.run_analysis()

self_weight = model.resultsbundle.loadcases["Self-weight"]
print(round(sum(r.nodal_forces.fy for r in self_weight.reaction_nodes.values()), 1))   # 7500.0
```

The solver applies 1500 N/m in place of the section's 184 N/m, and takes
1500 / 9.81 kg/m as the member's mass. `weight_override` is in the model's
force/length units. `Member.weight` is a different thing: the member's mass as
the SDK computes it, density·area·length, which is never sent to the solver.

## Seismic analysis

`add_seismic_analysis` asks the solver for a modal response-spectrum analysis
(the default), the lateral-force method, or both. The spectrum helpers build
EN 1998-1 design spectra. Accelerations are in m/s² and periods in seconds,
whatever the model's units; nodal masses are in kg.

```python
from fers_core import (
    FERS, Member, MemberSet, MaterialLibrary, NodalMass, NodalSupport, Node, Section,
    SeismicAnalysisSettings,
)

model = FERS()                                                    # first: it restarts the ids
steel = MaterialLibrary.S235()
column = Section.from_name("HEB200", steel)
nodes = [Node(0.0, float(height), 0.0) for height in range(7)]    # a 6 m mast
nodes[0].nodal_support = NodalSupport()                           # fixed base
model.add_member_set(MemberSet(members=[Member(a, b, section=column) for a, b in zip(nodes, nodes[1:])]))
model.add_nodal_mass(NodalMass(nodes[-1], 2000.0))                # 2 t of equipment on top

model.add_seismic_analysis(
    SeismicAnalysisSettings.eurocode_spectrum(ag=2.5, ground_type="C", q=1.5),
    directions=["X"],
    num_modes=4,
)
model.run_analysis()

x = model.resultsbundle.seismic["modal_response_spectrum"]["per_direction"][0]
print(f"{x['participating_mass_ratio']:.0%} of the mass, base shear {x['base_shear'] / 1000:.1f} kN")
```

`mass_sources=[(load_case, psi)]` turns gravity load cases into seismic mass
(ψE = 1.0 for permanent loads). `direct_spectrum` takes S, T_B, T_C and T_D
directly for a national annex, and `custom_spectrum` a table of periods and
accelerations. The results are plain dicts in `resultsbundle.seismic`, one
entry per method. `fers_core/examples/151_Seismic_Response_Spectrum.py` runs a
portal frame through both methods.

## Unity-check reports

The solver can embed one HTML report of every unity check in the result:

```python
from fers_core.builders import check_beam

model = check_beam(5.0, "IPE300", udl=10000.0)
model.settings.analysis_options.include_report_html = True
model.run_analysis()
html = model.unity_report_html()                    # a complete HTML page
```

`render_unity_reports = True` also fills each checked member's
`rendered_report` from its check's `report_template`, and adds those narratives
to the HTML report. Both are off by default, which keeps the result small.
