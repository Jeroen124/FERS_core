# FERS: structural analysis in Python

FERS is a finite-element solver for 3D frames, trusses and plates, with
Eurocode 3 member checks. This repository is its Python package and the `fers`
command. The solver is a compiled engine, `fers_calculations`, that the package
installs; it runs on your machine with no account and no network call, free for
non-commercial use up to 100 members.

It computes linear and second-order (P-Delta) static analysis, natural
frequencies, elastic buckling load factors (α_cr), response-spectrum seismic
analysis, and EN 1993-1-1 steel member checks, flexural and lateral-torsional
buckling included.

```bash
pip install FERS
```

```python
from fers_core import check_beam

# IPE200 in S235, simply supported over 6 m, 10 kN/m. SI units: m, N, Pa.
# check_beam adds an EN 1993-1-1 member check on a ULS combination of 1.35 x the load.
model = check_beam(6.0, "IPE200", udl=10_000.0)
model.settings.analysis_options.include_member_deflected_shape = True
model.run_analysis()

beam = model.resultsbundle.loadcases["Q"].member_results["1"]
x_frac, (_, dy, _) = beam.member_displacement_peak
ec3 = model.unity_check_results()[0]
print(f"M {beam.local_minimums.mz / 1e3:.1f} kNm, sag {dy * 1e3:.1f} mm at x/L {x_frac:.2f}")
print(f"EC3 utilization {ec3['max_utilization']:.2f}")
```

```text
M -45.0 kNm, sag -41.8 mm at x/L 0.50
EC3 utilization 2.87
```

The sag is 41.3 mm of bending (5wL⁴/384EI) plus 0.4 mm of shear deformation,
which the engine includes. The beam fails: the ULS moment of 60.75 kNm exceeds
its bending resistance of 51.9 kNm, and with nothing restraining its compression
flange, lateral-torsional buckling takes the utilization to 2.87.

## How it is checked

FERS is written by a structural engineer, with AI coding tools. A release goes
to PyPI only after the test suite passes against the engine version it pins.
That suite includes:

- closed-form beam results: cantilevers, simply supported and fixed-ended beams
  under point, uniform and triangular loads and end moments
  ([tests/beam_equation_checks](https://github.com/Jeroen124/FERS_core/tree/main/tests/beam_equation_checks));
- nine NAFEMS benchmarks: free vibration of frames, a deep beam, a ring and a
  plate (FV1, FV2, FV3, FV5, FV6, FVP), an elliptic membrane (LE1), warping
  torsion of a Z-section (LE5) and a skew plate (LE6)
  ([tests/nafems](https://github.com/Jeroen124/FERS_core/tree/main/tests/nafems)).
  Each one's target, result and error is on
  [ferscloud.com/nafems](https://ferscloud.com/nafems), solved live in your
  browser.

## Building a model

`check_beam`, `create_beam` and `create_frame` build common models in one call.
To build one by hand, create the `FERS` object first, then its nodes, members
and loads. Creating a `FERS` restarts the id counters, so a node made before it
would share an id with one made after it, and the solver refuses node ids that
do not run from 1 without gaps.

`fers examples list` lists the numbered examples in `fers_core/examples`, from
single beams checked against their textbook formulas to a 3D shed.

## Reading results

```python
case = model.resultsbundle.loadcases["Q"]       # or .loadcombinations["ULS 1"]

case.displacement_nodes["2"].dy                  # dx dy dz rx ry rz warp
case.reaction_nodes["1"].nodal_forces.fy         # fx fy fz mx my mz bw
beam = case.member_results["1"]
beam.local_maximums.mz, beam.local_minimums.mz   # envelope along the member, member axes
```

Load cases and combinations are keyed by name, nodes and members by their id as
a string. Read a frame's bending moments from the `local_*` forces: outside the
XY plane the global `mz` is not the bending moment.
[docs/results.md](https://github.com/Jeroen124/FERS_core/blob/main/docs/results.md)
covers the rest: read-only result tables, saving and loading, and asking the
solver for only the results you need.

## From the terminal and from coding agents

```bash
fers validate model.json                 # the failing field, and keys the engine ignores
fers solve model.json --out results.json
fers check model.json                    # each unity check's utilization and a verdict
```

Each command prints one line, or JSON with `--json`, and its exit code says
whether the numbers can be used: 4 means solved but do not use them, 6 a check
that fails.
[docs/command-line.md](https://github.com/Jeroen124/FERS_core/blob/main/docs/command-line.md)
has every command and exit code.

For AI agents there is a skill (`fers skill --install .`), an
[MCP server](https://ferscloud.com/mcp), and a Claude Code plugin with both:
`/plugin install fers --marketplace Jeroen124/FERS_core`.

## More

- [Hinges](https://github.com/Jeroen124/FERS_core/blob/main/docs/hinges.md):
  scissor hinges for a continuous beam that turns on what it crosses, and
  member hinges in global or user axes.
- [Self-weight, seismic analysis and reports](https://github.com/Jeroen124/FERS_core/blob/main/docs/loads-and-analyses.md).
- [API keys, solve tokens and timeouts](https://github.com/Jeroen124/FERS_core/blob/main/docs/keys-and-timeouts.md).
- Plots, section properties meshed from your own dimensions and DXF import are
  extras: `pip install "FERS[plot]"`, `"FERS[sections]"`, `"FERS[dxf]"`, or
  `"FERS[all]"`. Catalogue sections (`IPE200`, `HEB300`, `UB 457x191x67`,
  `W14X30`, ...) need none.

## Licence

This package, `FERS`, is open source under the BSD 3-Clause License (`LICENSE`).

The solver engine it installs, `fers_calculations`, is licensed separately,
under the PolyForm Strict License 1.0.0: free for any non-commercial purpose,
such as study, teaching, research and hobby projects. Commercial use needs a
paid [FERS Cloud plan](https://ferscloud.com/pricing), which includes the
commercial licence.
