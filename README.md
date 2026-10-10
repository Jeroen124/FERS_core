# FERS_core

**FERS_core** is an open-source Finite Element Method (FEM) library written in Rust with a Python interface. It provides the foundational tools and components necessary for performing FEM analysis. This core package is designed for users who need a reliable and efficient FEM solver.

## Features

- Basic Finite Element Method (FEM) solvers
- Mesh generation and manipulation tools
- Support for various types of finite elements
- Easy-to-use Python interface for integration with existing workflows
- Designed for high performance with Rust

## Installation

You can install `FERS_core` via pip:

```bash
pip install FERS
```

## Solving a model

```python
from fers_core.builders import create_beam

model = create_beam(5.0, "IPE180", udl=5000.0)    # 5 m span, 5 kN/m downward
model.run_analysis()
print(model.resultsbundle)
```

Building a model by hand, create the `FERS` object first, then its nodes,
members and loads. Creating a `FERS` restarts the id counters, so a node made
before it would share an id with one made after it, and the solver refuses
node ids that do not run from 1 without gaps.

## Reading results

`run_analysis()` puts the results on `model.resultsbundle`. Load cases and load
combinations are keyed by name. Within each, nodes and members are keyed by
their id as a string, because results round-trip through JSON.

```python
case = model.resultsbundle.loadcases["Load"]    # or .loadcombinations["ULS 1"]

case.displacement_nodes["5"].dy                  # dx dy dz rx ry rz warp
case.reaction_nodes["1"].nodal_forces.fy         # fx fy fz mx my mz bw
beam = case.member_results["4"]
beam.local_maximums.mz, beam.local_minimums.mz   # envelope along the member
beam.local_start_forces.fy                       # end forces, member axes
```

Since 0.1.98, `member_results` and `displacement_nodes` are read-only tables
rather than dicts of objects. That is what keeps a large result small in
memory. They read like dicts: `[]`, `get`, `in`, `len`, `.items()`, and
iteration in the solver's order. Each lookup builds a fresh object, and nothing
in it can be changed:

```python
beam.local_maximums.mz = 0.0                     # AttributeError: read-only
editable = case.member_results.copy()            # a plain dict of editable objects
editable["4"].local_maximums.mz = 0.0            # fine
```

`section_forces`, `internal_force_series` and `member_displacements` come back
as tuples. To test for a table, use `isinstance(x, collections.abc.Mapping)`,
not `dict`. `reaction_nodes` and `plate_results` are plain dicts, as before.

### Saving and loading

```python
from fers_core import FERS

model.save_to_json("beam.json")                  # the model and its results
model = FERS.from_json("beam.json")
```

`FERS.from_json` reads any file the solver or the SDK wrote, one entry at a
time. A typical result needs less memory than its file to load, and at most
about twice the file's size; before 0.1.98 it needed 15 to 20 times. For a
large model, let the solver write the file itself. The result then never
passes through Python as one string:

```python
model.run_analysis_to_file("beam_results.json")
solved = FERS.from_json("beam_results.json")
```

`fers_core/examples/809_Reading_Results.py` runs all of this end to end.

Saving a loaded model writes back everything the solver reads, with the same
ids. That includes what the file defines but nothing uses yet, such as a section
an editor keeps in its library. Nodes, members and the rest created after
loading get ids the loaded model does not use, so saving never lets a new object
replace a loaded one.

## A member's self-weight

The solver works out each member's self-weight, density·area·g, and its mass for
modal and seismic analysis from the section. A member that carries more, such as
cladding or a services run, can override both:

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

## Premium solves and timeouts

Without an API key the solver runs at Free-tier limits (100 members) and makes
**no network call at all**. Passing `api_key` raises those limits:

```python
model.run_analysis(api_key=KEY)
```

A key means each solve first verifies the licence with ferscloud.com, so that
handshake is bounded. If the licence server does not answer within
`license_timeout` seconds (default 30) the call raises `FersTimeoutError`
**before the solve starts** — so retrying is always safe:

```python
import fers_calculations

try:
    model.run_analysis(api_key=KEY, license_timeout=60)
except fers_calculations.FersTimeoutError:
    ...   # transient stall — retry or skip this model
except RuntimeError:
    ...   # definitive — bad key, non-premium account, or a rejected model
```

Keeping those two arms apart is the point: retrying a `RuntimeError` fails
identically, while collapsing both into `except Exception` turns a retryable
blip into a lost result. See `fers_core/examples/203_Premium_Batch_Solve.py`
for the full unattended-batch pattern.

`FersTimeoutError` subclasses the built-in `TimeoutError`, so a plain
`except TimeoutError` catches it too.

Set `FERS_LICENSE_TIMEOUT` (seconds) to change the default without editing any
call sites. It must be a real environment variable — `.env` files are not read
by the engine.

> `license_timeout` bounds the **licence handshake, not the solve**. A solve is
> native code with no cancellation point, so no in-process timeout can interrupt
> it. For a hard ceiling on total wall time per model, run each solve in a
> killable subprocess — that also reclaims its memory.

Requires engine `fers_calculations >= 0.2.53`.
