# Changelog

## 0.1.78

Pins engine `fers_calculations==0.2.51`. If you use linear buckling on models
with reaction-dependent base springs (`stiffness_curve` supports), **α_cr
rises** — the eigenproblem now linearizes those springs at the reference
reactions (the loaded state the static solve converges to) instead of at
force = 0, which had entered nearly rigid rack base plates as nearly pinned.
Models without StiffnessCurve supports are unaffected. Also: exactly singular
operators (unconstrained DOFs / mechanisms) now return a structured error
instead of crashing the process. No schema change — no regenerated types.

## 0.1.77

Pins engine `fers_calculations==0.2.50`, which fixes two silent,
non-conservative correctness bugs. If you use linear buckling or EC3 member
buckling, **α_cr and unity checks can change** — see the engine's 0.2.50
changelog. Both changes move results toward the conservative side.

### Changed

- **Pin `fers_calculations==0.2.50`** (was `0.2.48`). Two fixes matter here:
  P-Delta settings (`pdelta_suppress_axes`, `pdelta_mode`,
  `pdelta_formulation`) no longer leak into linear buckling and inflate α_cr
  (measured up to 4.9×); and EC3 `L_cr` for a member-set with no
  `buckling_restraints` now uses the full member-set chain length instead of
  the single FE member length, so buckling checks on meshed columns are no
  longer mesh-dependent (measured UC 0.15 → 0.93 on a 12-element column).
- **`types/pydantic_models.py` regenerated** from the 0.2.50 schema. New
  output-only fields: `ResultsBundle.engine_version`,
  `BucklingResults.warnings`. Both additive — `schema_version` stays 2.

### Notes

- The engine version is now queryable at runtime:
  `import fers_calculations; fers_calculations.__version__`. Note this is the
  *engine* version, distinct from this package's version — `pip show FERS`
  reports the wrapper, which is what makes a capability check confusing.

## 0.1.76

### Added
- **`AnalysisOptions.result_filter`** + **`ResultBlock`** enum (engine ≥
  0.2.48): whitelist of result blocks the engine should emit. `None`
  (default) keeps today's full output; the smallest set that still feeds a
  full unity-check pipeline is `[ResultBlock.LOCAL_ENVELOPES,
  ResultBlock.LOCAL_END_FORCES, ResultBlock.LOCAL_DISPLACEMENTS,
  ResultBlock.NODE_DISPLACEMENTS, ResultBlock.REACTIONS]`, which shrinks large
  responses ~60% (the fix for the `result-filtering` OOM feedback). A token
  names the block it *keeps*, not the check it serves — dropping
  `LOCAL_END_FORCES`/`LOCAL_DISPLACEMENTS` silently zeroes
  start-node-force/chord-deflection checks; dropping `NODE_DISPLACEMENTS` is a
  hard `KeyError`. Older engines ignore the field. Unity checks always
  evaluate on the full results regardless of the filter;
  `member_displacements` stays governed by `include_member_deflected_shape`.
- The engine wheel also gained `fers_calculations.calculate_to_file(
  json_data, output_path, api_key=None)` — solve and stream the result JSON
  to a file so the response string never lives in the Python heap; composes
  with `result_filter`.

### Changed
- **Pin `fers_calculations==0.2.48`.** Schema loosening in 0.2.48: the ten
  scalar `MemberResult` blocks are now `Optional` in the generated result
  models (they are absent only when explicitly filtered out; unfiltered
  output is unchanged). Regenerated `types/pydantic_models.py` accordingly so
  `FERS.from_json` accepts a filtered response (previously raised ~64k
  "Field required" validation errors).

## 0.1.75

### Changed
- **Pin `fers_calculations==0.2.47`** (was `0.2.45`; 0.2.46 was published but
  never pinned by a `fers` release). 0.2.47 fixes the second-order
  load-combination warm start on models with tension-only / compression-only
  members: with `solve_loadcases: true`, combination solves were seeded from a
  superposition of the nonlinear load-case displacements and could converge —
  reported as clean success — onto a spurious equilibrium branch (Solvinq
  rack 1962: a tension-only diagonal carried 3.6× the correct force, a false
  structural FAIL vs SkyCiv). Such models now cold-start each combination and
  agree with the `solve_loadcases: false` answer; results on affected
  tension-only braced models **change (become correct)**. New advisory
  diagnostic `solver_diagnostics.unilateral_engagement_flips` + an
  `unilateral_engagement_flip` warning identify engagement flips.

### Migration note (P-Delta mode, fers_core ≤ 0.1.69 → ≥ 0.1.70)
- `AnalysisOptions` could not express `pdelta_mode` before **0.1.70** — any
  consumer that migrated from a hand-rolled wire (which typically wrote
  `"pdelta_mode": "IN_PLANE_ONLY"`) to fers_core builder objects on ≤ 0.1.69
  **silently switched to the engine default `FULL`** (all-direction P-Delta
  amplification). The two modes diverge exactly on rack-style tension-only
  braced structures. For commercial-solver parity set it explicitly:
  `AnalysisOptions(pdelta_mode=PdeltaMode.IN_PLANE_ONLY)`. The same applies to
  `nonlinear_method` / `pdelta_formulation` (engine defaults `COROTATIONAL` /
  `CONSISTENT`; only emitted when explicitly set).

- Upstream 0.2.46 completes the EC3
  §6.3 member-buckling checks: the §6.3.3 member-buckling interaction is
  implemented per Annex A (Method 1) and validated against ECCS N°119 Worked
  Example 4; buckling lengths (`L_cr`, `l_LTB`, `l_T`) are now derived from the
  `buckling_restraints` spacing — **results change:** models that already carry
  buckling restraints now get the shorter, correct `L_cr` instead of the full
  system length; §6.3.3 is evaluated in code axes, fixing the χ_LT pairing for
  sections whose strong bending axis is local z; §6.3.1.4 torsional and
  torsional-flexural buckling is added, with the new
  `MemberSet.buckling_length_t` wire field to control the torsional buckling
  length; the equivalent uniform moment factors implement Annex B
  Tables B.1–B.3 in full, replacing the interim `Cm = 1.0` stopgap; and
  `Ec3SteelSpec` gains `cmy` / `cmz` / `cm_lt` overrides.

## 0.1.74

### Changed
- **Pin `fers_calculations==0.2.45`** (was `0.2.44`). Pin-bump-only release (no
  library changes): 0.2.44 understated end-peaked unity-check demands by up to
  ~25% (member-end sections were skipped when selecting the governing section)
  and, due to an inverted compression gate, never ran the EC3 §6.3.1/§6.3.3
  buckling checks on compressed members; 0.2.45 carries the fixes. The
  `fers_calculations` 0.2.44 publish that 0.1.73 was gated on has since
  shipped.

## 0.1.73

### Added
- **First-class modal & buckling analysis settings.** `ModalAnalysisSettings` and
  `BucklingAnalysisSettings` (`from fers_core import ...`) map to the solver's
  `analysis.modal` / `analysis.buckling` wire objects — set them via
  `calc.analysis.modal = ModalAnalysisSettings(num_modes=6)` (or the
  `modal_analysis` / `buckling_analysis` attributes) and `to_dict()` emits them;
  `from_dict()` round-trips them. `mass_formulation` is normalized to the canonical
  uppercase tokens (`"CONSISTENT"`/`"LUMPED"`, new `MassFormulation` enum) so the
  document passes the generated-schema gate, and the buckling `reference` accepts a
  `LoadCase`/`LoadCombination` object, a tagged dict, or a `(kind, id)` tuple and is
  normalized to the externally-tagged `{"LoadCase": id}` / `{"LoadCombination": id}`
  form. Optionals (`tolerance`, `max_iterations`) are omitted when unset.
- **`ResultsBundle` now carries modal/buckling results.** Solver `results.modal` /
  `results.buckling` (previously dropped in `from_pydantic`) are exposed as plain
  dicts on `resultsbundle.modal` / `resultsbundle.buckling` (`None` when the
  analysis was not requested) and survive `to_dict()` / `from_raw_dict()`.
- `tests/functionality/test_modal_buckling_settings.py` — exact wire shapes,
  reference normalization, round-trips, schema conformance, and an end-to-end
  modal solve on a cantilever through the installed `fers_calculations` wheel.

### Changed
- The NAFEMS harness (`tests/nafems/nafems_harness.py`) now attaches the modal
  request through the first-class API instead of injecting raw dicts into the
  wire JSON (the `weight = 0` belt-and-braces guard remains).
- **Pin `fers_calculations==0.2.44`** (was `0.2.43`). Upstream, the Kirchhoff/DKT
  plate element is rewritten to the canonical Batoz–Bathe–Ho formulation and
  validated (exact constant-curvature patch test; SS square plate within 0.31%
  at 16×16; clamped within 2%; converging), so `theory="Kirchhoff"` is no longer
  grossly under-stiff. `Auto` still resolves to Mindlin/DSG3 as the
  general-purpose default. The engine also gains a NAFEMS FV3 free-free
  regression test. Stale "Kirchhoff/DKT is unreliable" and "plate modal is
  unsupported" notes in the NAFEMS reference templates were refreshed
  accordingly. **This release is gated on the `fers_calculations` 0.2.44
  publish** (unreleased at the time of writing; CI publishes on merge).

## 0.1.72

### Fixed
- **Unity checks now conform to the solver schema.** `generic_check` places
  `report_template` on the `UnityCheckDefinition` (top level) instead of inside the
  `GenericSpec` (which the solver serialises with `deny_unknown_fields` and would
  reject), and `ec3_steel_check` exposes the missing `c2` / `c3` / `z_g` LTB factors.
  Every check is validated against the generated `UnityCheckDefinition` at author time.
- **Analysis enums.** `AnalysisOrder` and `RigidStrategy` serialise the canonical solver
  tokens (`LINEAR`/`NONLINEAR`, `LinearMpc`/`RigidMember`) instead of the legacy
  spellings. The solver accepts both via serde aliases, so this is backward compatible.
- **`LoadCombination.to_dict()`** now serialises `limit_state` as its string value
  (e.g. `"ULS"`) instead of the raw `LimitState` enum, so combinations that carry a
  limit state pass the schema-validation gate and are correctly typed on the wire.

### Added
- **`create_beam(...)` convenience builder** (`from fers_core import create_beam`).
  A ready-to-solve single-span beam from a few keyword args: named section
  (`"IPE180"`, via the section library) or a `Section`; a steel grade or a `Material`;
  `simply_supported` / `cantilever` / `fixed`; a UDL and/or point load. Returns a
  `FERS` you can `run_analysis()` straight away. First-order 2D analysis for
  predictable, textbook-matching results.
- **`check_beam(...)` EC3 member check** (`from fers_core import check_beam`). Builds a
  single-span beam with a ULS load combination and an EN 1993-1-1 (Ec3Steel) unity
  check, ready to `run_analysis()` then read `unity_check_results()`. Covers
  cross-section resistance (bending, shear, N+M) and lateral-torsional buckling
  (§6.3.2), verified against hand calculations (IPE300, 6 m, 10 kN/m → bending 0.41,
  LTB governs at 0.86). Requires `fers_calculations >= 0.2.42` (the major-axis LTB fix).
- **Section elastic/plastic moduli.** `Section` now computes and carries
  `wel_y` / `wel_z` / `wpl_y` / `wpl_z` (via `sectionproperties`), so named sections are
  ready for EC3 checks. Verified against published tables (IPE180 Wel,y = 146 cm³,
  Wpl,y = 166 cm³). `scripts/export_sections.py` includes them in the exported JSON.
- `FERS.validate_schema()` validates the assembled input against the generated pydantic
  `FERS` model — the single source of truth generated from the engine's OpenAPI.
  `run_analysis(validate=True)` (the default) runs this gate before solving, so any
  drift between a hand-written `to_dict()` and the schema fails fast with a clear error;
  pass `validate=False` to skip.
- `tests/functionality/test_schema_conformance.py` — round-trips every shipped example
  model plus surface-load, spring-curve, and unity-check models through the schema gate.

## 0.1.70

### Added
- **Member deflected shape.** `AnalysisOptions.include_member_deflected_shape`
  requests the engine's sampled deflected polyline; `MemberResult.member_displacements`
  now carries it (parsed from the result), and `ResultRenderer` /
  `MemberResult.render_deformed_shape` draw this **load-exact** shape in preference to
  the simplified client-side cubic-Hermite reconstruction, with automatic fallback when
  it is absent (older engine, mode shapes, or the option off).
- New example `examples/104_visual_member_deflected_shape.py`.

### Changed
- Pin `fers_calculations==0.2.41` (was `0.2.40`, which was never published to PyPI).

### Notes
- `fers_core/types/pydantic_models.py` gained `MemberDisplacementSample` +
  `MemberResult.member_displacements`. This was a surgical add; a full regen of the
  pydantic models from the engine's 0.2.41 `openapi.json` is recommended to also pick
  up the other 0.2.41 schema/docstring updates.
