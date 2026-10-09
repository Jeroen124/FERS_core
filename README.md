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

### Only the results you read (engine 0.2.68)

`AnalysisOptions(result_filter=[...])` keeps or drops whole result blocks.
`result_requests` goes further. Each `ResultRequest` names a block and narrows
it to chosen members or nodes, load combinations, components and one member
end:

```python
from fers_core import ResultBlock, ResultRequest
from fers_core.result_requests import nodes_of
from fers_core.unity_checks import classification

columns, beams = classification("column"), classification("beam")
model.settings.analysis_options.result_requests = [
    ResultRequest(ResultBlock.LOCAL_ENVELOPES, members=[columns, beams],
                  limit_state="ULS", components=["fx", "my", "mz"]),
    ResultRequest(ResultBlock.NODE_DISPLACEMENTS, nodes=nodes_of(beams),
                  limit_state="SLS", components=["dx", "dz"]),
    ResultRequest(ResultBlock.REACTIONS, limit_state="ULS"),
]
model.run_analysis()
```

The values load into the same `member_results`, `displacement_nodes` and
`reaction_nodes`, so code that reads them keeps working. **Anything that was not
requested reads as `None`, not zero.** A check that reads a value nobody asked
for therefore fails instead of passing on a zero.

- `members` takes the unity checks' selectors: `classification(...)`,
  `members([...])`, `member_sets([...])` and `all_members()`. Several selectors
  form a union.
- `nodes` takes `nodes([...])`, or `nodes_of(*selectors)` for the end nodes of
  the selected members.
- Load combinations are matched on their `limit_state`, as unity checks match
  them, or by `load_combination_ids`. To select by limit state, set
  `limit_state` on each `LoadCombination`; the solver does not read `situation`.
- A request with neither `limit_state` nor `load_combination_ids` also covers
  the load cases.
- `end="start"` or `end="end"` keeps one end of the end-force and
  end-displacement blocks.
- The solver refuses a request it cannot meet, before it starts. That includes
  `section_forces`, `internal_force_series`, a component the block does not
  have, a limit state no combination carries, and `result_filter` set as well.

The values themselves are on `model.resultsbundle.selections`, one entry per
request and group of result sets. Each entry's `values` is a read-only numpy
array shaped `(result_sets, ids, fields, components)`, with each axis listed
beside it:

```python
sel = model.resultsbundle.selections[0]
sel["group"]                     # "loadcombinations" or "loadcases"
sel["result_sets"], sel["ids"]   # combination names, member or node ids
sel["fields"], sel["components"] # e.g. ["local_maximums", "local_minimums"], ["fx", "my", "mz"]
my = sel["values"][..., sel["components"].index("my")]   # every set, member and field
```

`save_to_json` writes the selections back as the solver wrote them, so a saved
result reloads unchanged. `fers_core/examples/810_Result_Requests.py` runs this
end to end.

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
