# Reading results

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

`start_node_forces`, `end_node_forces`, `maximums` and `minimums` are in the
global frame; the `local_*` forces, `section_forces` and `internal_force_series`
are in the member's own axes, with `mz` the strong-axis moment. Read a frame's
moments from the local ones: outside the XY plane the global `mz` is not the
bending moment, and in a frame in the YZ plane it reads 0.

`member_results` and `displacement_nodes` are read-only tables rather than dicts
of objects, which keeps a large result small in memory. They read like dicts:
`[]`, `get`, `in`, `len`, `.items()`, and iteration in the solver's order. Each
lookup builds a fresh object, and nothing in it can be changed:

```python
beam.local_maximums.mz = 0.0                     # AttributeError: read-only
editable = case.member_results.copy()            # a plain dict of editable objects
editable["4"].local_maximums.mz = 0.0            # fine
```

`section_forces`, `internal_force_series` and `member_displacements` come back
as tuples. To test for a table, use `isinstance(x, collections.abc.Mapping)`,
not `dict`. `reaction_nodes` and `plate_results` are plain dicts.

## Saving and loading

```python
from fers_core import FERS

model.save_to_json("beam.json")                  # the model and its results
model = FERS.from_json("beam.json")
```

`FERS.from_json` reads any file the solver or the SDK wrote, one entry at a
time, so loading a result takes at most about twice the file's size in memory.
For a large model, let the solver write the file itself; the result then never
passes through Python as one string:

```python
model.run_analysis_to_file("beam_results.json")
solved = FERS.from_json("beam_results.json")
```

Saving a loaded model writes back everything the solver reads, with the same
ids, including what the file defines but nothing uses yet. Objects created after
loading get ids the loaded model does not use, so saving never lets a new object
replace a loaded one.

`fers_core/examples/809_Reading_Results.py` runs all of this end to end.

## Asking for only the results you read

`AnalysisOptions(result_filter=[...])` keeps or drops whole result blocks.
`result_requests` goes further: each `ResultRequest` names a block and narrows
it to chosen members or nodes, load combinations, components and one member end.

```python
from fers_core import ResultBlock, ResultRequest
from fers_core.builders import check_beam
from fers_core.result_requests import nodes_of
from fers_core.unity_checks import classification

model = check_beam(5.0, "IPE300", udl=10000.0)    # one "Beam", one ULS combination
beams = classification("Beam")
model.settings.analysis_options.result_requests = [
    ResultRequest(ResultBlock.LOCAL_ENVELOPES, members=[beams],
                  limit_state="ULS", components=["fx", "my", "mz"]),
    ResultRequest(ResultBlock.NODE_DISPLACEMENTS, nodes=nodes_of(beams),
                  limit_state="ULS", components=["dy"]),
    ResultRequest(ResultBlock.REACTIONS, limit_state="ULS"),
]
model.run_analysis()
```

The values load into the same `member_results`, `displacement_nodes` and
`reaction_nodes`, so code that reads them keeps working. **Anything that was not
requested reads as `None`, not zero**, so a check that reads a value nobody
asked for fails instead of passing on a zero.

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
- The solver refuses a request it cannot meet before it starts: `section_forces`,
  `internal_force_series`, a component the block does not have, a limit state no
  combination carries, or `result_filter` set as well.

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
