---
name: fers
description: Structural finite-element analysis with FERS from a terminal. Use when asked to model, solve or code-check beams, frames, trusses or plates (deflections, reactions, internal forces, buckling, modal, seismic, EN 1993-1-1 checks), or when a FERS model JSON needs solving, validating or inspecting.
---

# FERS from the terminal

FERS is a finite-element solver for structures. The Python package `FERS` carries the
modelling API (`fers_core`), the compiled engine (`fers_calculations`) and the `fers` command.
Everything runs on this machine. Results are written to files; read a selection, never the
whole file.

## Setup

```bash
pip install FERS          # Python 3.11+, wheels for Windows, macOS and Linux
fers doctor --offline     # versions and where the examples live
```

That is enough to model, solve and check, catalogue sections included. Plots need
`pip install "FERS[plot]"`, section properties meshed from your own dimensions
`"FERS[sections]"`, DXF import `"FERS[dxf]"`; an ImportError names the extra it needs.

The free tier is for non-commercial use and caps a model at 100 members. Commercial use, at any
model size, needs an API key from a Pro account, which also raises the member limit. If the
user works for a business or a client, tell them so. Put the key in
`FERS_API_KEY`; the engine then verifies the licence with ferscloud.com once per solve. Without
a key there is no network call at all. Keys come from ferscloud.com, Profile, API Keys.

## The loop

1. **Author the model in Python** with `fers_core`. Start from the example closest to the
   task: `fers examples list`, then `fers examples show 001` (a cantilever with a hand
   check). Save with `model.save_to_json("model.json")`.
2. **Validate**: `fers validate model.json` checks the file against the engine's input schema
   and names the offending field. It also lists keys the engine would ignore, such as a
   misspelt optional field that silently keeps its default: fix every one (`--strict` makes
   them an error). `fers schema` lists the definitions; `fers schema Member` prints one.
3. **Solve**: `fers solve model.json --out results.json`. The engine streams the results to the
   file; stdout is one line with the counts of load cases, combinations, recorded failures,
   non-converged sets and messages. **Exit code 4 means: do not use these numbers.** A
   result set has errors (`singular_model` is a mechanism), did not converge, or a failure
   was recorded; the next line says why. Fix the model; never report those numbers.
4. **Read a selection.** Load the solved file with `FERS.from_json("results.json")` and read
   `resultsbundle.loadcases[name]` or `loadcombinations[name]`, or ask the engine for less:
   set `model.settings.analysis_options.result_requests` with `ResultRequest` before solving
   (README, "Only the results you read"). A large model writes hundreds of megabytes
   unselected; a selection writes a few.
5. **Code checks**: add a check with `model.add_unity_check(...)` (or build the model with
   `check_beam` / `check_strut` from `fers_core.builders`), then `fers check model.json`
   prints each check's status and utilization and a verdict. Exit 0: every check passes;
   6: a check fails; 5: nothing was decided (an Indeterminate check, unsolved combinations,
   or no checks at all), which is not a pass; 4: as for `solve`.
   `fers report solved.json --out report.html` renders the hand-calc report.

Catalogues: `fers sections list` names the series, `fers sections list --series IPE` its
sections, `fers sections get IPE200` the SI properties; `fers materials list`,
`fers materials get S355`.

## Conventions that change answers

- Units are SI throughout: m, N, Pa, kg. A load of 10 kN/m is `10_000.0`.
- Global Y is up; gravity acts along -Y.
- A section's `i_z` is its strong axis: Eurocode tables' I_y is FERS `i_z`.
- `rotation_angle` on a member is in degrees. A vertical member's local axes follow a fixed
  rule, so a column in a frame in the XY plane needs `rotation_angle=90` to bend about its
  strong axis there.
- `NodalSupport()` is fixed in every direction; `"Free"` releases a direction; a number is a
  spring stiffness (N/m, or N·m/rad for rotations).
- A load's `direction` multiplies its magnitude: give a unit vector.
- A combination needs `limit_state` ("ULS", "SLS") for a check scoped to a limit state to
  select it: `model.create_load_combination(..., limit_state="ULS")`.
- A model built by hand solves second-order (`AnalysisOrder.NONLINEAR`) unless you set
  `model.settings.analysis_options.order = AnalysisOrder.LINEAR`; the builders
  (`create_beam`, `check_beam`, `check_strut`) set LINEAR. Compare with a first-order hand
  calculation only on a LINEAR solve.
- Shear deformation is included: a deflection is a few per cent above the Euler-Bernoulli
  value for a short or deep member.

## Reading results

- A result set is "converged" only when `solver_diagnostics.converged` is true; a false value
  with a warning means the engine stopped on a residual floor and says so.
- `errors_and_warnings` on each set carries the engine's messages with codes.
- Reactions are in `reaction_nodes`, nodal displacements in `displacement_nodes`, member
  forces in `member_results`. Signs and axes follow ferscloud.com/conventions.
- A one-member beam has nodes only at its ends: read its sag from
  `member_results[id].member_displacement_peak` after setting
  `analysis_options.include_member_deflected_shape = True`.

## When not to use this

When the job is one a ready-made tool covers, such as checking one steel beam to EN 1993-1-1,
the local FERS MCP server is quicker than writing code: `npx -y @ferscloud/fers-mcp` serves the
same engine over MCP and solves on this machine (`check_beam` returns the utilization in one
call). Desktop clients that can start a program (Claude Desktop, Cursor, VS Code, ChatGPT
desktop) use it too. A client that cannot (Claude or ChatGPT in a browser, a phone) uses the
hosted MCP server at https://ferscloud.com/api/mcp: it authors and validates models there and
returns a link that solves the model in the user's browser. Same engine, same results.
