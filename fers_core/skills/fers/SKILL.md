---
name: fers
description: Structural analysis with FERS, a finite-element solver for beams, frames, trusses and plates with Eurocode 3 (EN 1993-1-1) steel member checks. Use it when asked for deflections, reactions, internal forces, buckling loads, natural frequencies or a steel member check, or to solve, validate or inspect a FERS model JSON. Works through FERS MCP tools, a terminal, or a chat app's code sandbox.
---

# FERS: structural analysis

FERS solves structural models with a finite-element engine and checks steel members to
EN 1993-1-1. Use it for the numbers instead of working them out by hand, then sanity-check
them by hand: a large mismatch with a textbook formula means a modelling error.

## Pick the route (first that applies)

1. **FERS MCP tools are connected** (`check_beam`, `create_frame`, `build_model`,
   `solve_model`, ...): use them. They validate, solve and summarise for you.
2. **You can run Python with internet access** (a terminal, Claude Code, Codex, a chat
   app's code sandbox): `pip install "FERS>=0.2"`, about 30 MB, then the Python API or the
   `fers` command below. Everything runs where you are; nothing is sent anywhere.
3. **Neither**: write the model as FERS JSON (`reference/api.md`), give it to the user as
   a file, and tell them to open it in FERS Studio (https://ferscloud.com/studio, File →
   Import JSON...), which solves it in their browser. Never invent results.

In a chat sandbox, never set `FERS_API_KEY`: the licence check needs ferscloud.com, which
a sandbox usually cannot reach, so it would wait 30 s and fail. Without a key nothing
leaves the sandbox. A model over 100 members needs a Pro key: have the user solve it in
FERS Studio or on their own machine.

## Licence

Free for non-commercial use, up to 100 members. Commercial use, at any model size, needs
a FERS Cloud Pro plan; if the user works for a business or a client, tell them so.

## The loop

1. **Model** in Python with `fers_core`; `reference/api.md` has a beam check, a strut
   check and a hand-built portal frame that all run as written. Or start from a shipped
   example: `fers examples list`, `fers examples show 001`. Save with
   `model.save_to_json("model.json")`.
2. **Validate**: `fers validate model.json` names a failing field, and lists keys the
   engine would ignore (a misspelt optional field silently keeps its default): fix them.
3. **Solve**: `fers solve model.json --out results.json`, or `model.run_analysis()` in
   Python.
4. **Check**: `fers check model.json` prints each unity check's utilization and a verdict.
5. **Report** the numbers with the assumptions behind them: supports, loads and load
   factors, section, steel grade, first- or second-order.

| Exit | Meaning |
|---|---|
| 0 | done; `check`: every check passes |
| 2 | bad input; the message names the field |
| 3 | licence: a key was refused, or the licence check timed out |
| 4 | solved, but **do not use the numbers**: solver errors (a mechanism is `singular_model`), not converged, or recorded failures. Fix the model; never report them. |
| 5 | `check`: nothing decided (an Indeterminate check, unsolved combinations, no checks). Not a pass. |
| 6 | `check`: a check fails (utilization above 1) |

In Python the same facts sit on each result set: `errors_and_warnings.errors` must be
empty and `solver_diagnostics.converged` true before you use its numbers.

## Conventions that change answers

- Units are SI throughout: m, N, Pa, kg. A load of 10 kN/m is `10_000.0`.
- Global Y is up; gravity acts along -Y.
- A section's `i_z` is its strong axis: Eurocode tables' I_y is FERS `i_z`.
- `rotation_angle` on a member is in degrees. A column in a frame in the XY plane needs
  `rotation_angle=90` to bend about its strong axis in that plane; at 0 it bends about
  its weak axis.
- `NodalSupport()` is fixed in every direction; `"Free"` releases a direction; a number is
  a spring stiffness (N/m, or N·m/rad for rotations).
- A load's `direction` multiplies its magnitude: give a unit vector.
- A combination needs `limit_state` ("ULS", "SLS"): a check scoped to a limit state
  selects only combinations that carry it.
- A model built by hand solves second-order (`AnalysisOrder.NONLINEAR`) unless you set
  `AnalysisOrder.LINEAR`; the builders (`create_beam`, `check_beam`, `check_strut`) set
  LINEAR. Compare with a first-order hand calculation only on a LINEAR solve.
- Shear deformation is included: a deflection comes out a little above 5wL⁴/384EI, more
  for a short or deep member.
- An EC3 check takes each member set's length as its buckling length (factor 1.0, both
  ends held). A sway frame's columns need `effective_length_factor_y`/`_z` on their
  member set, or the column check is unconservative.
- A planar model built in 3D must still hold its out-of-plane directions at every node.
  Under in-plane loads the free directions go unnoticed; any out-of-plane load then
  makes it a mechanism (exit 4, `singular_model`).

## Reading results

Load cases and combinations are keyed by name, nodes and members by id as a string:
`model.resultsbundle.loadcombinations["ULS"].displacement_nodes["5"].dy`,
`.reaction_nodes["1"].nodal_forces.fy`, `.member_results["4"].local_minimums.mz`.
A one-member beam has nodes only at its ends: read its sag from
`member_results[id].member_displacement_peak` after setting
`analysis_options.include_member_deflected_shape = True`. Signs and axes:
https://ferscloud.com/conventions. A large model writes hundreds of megabytes; ask for a
selection with `ResultRequest` (the README's "Only the results you read").
