# Changelog

## 0.1.88

> **0.1.87 carried no changes of its own** — it was a bare version bump on top of
> 0.1.86 and has no entry below, because there is nothing to describe. The pin
> stayed at engine `0.2.58`.

Pins engine `fers_calculations==0.2.59`. Additive: no existing API moves.

### Changed, via the engine

Engine 0.2.59 finishes the moment-rotation connector work. Nothing in this
package's API moves, but two behaviours you can reach from it do:

- **`CurveEndBehaviour.YIELDING` now redistributes on an indeterminate frame.**
  The connector holds its plateau and the moment it cannot carry appears
  elsewhere. Earlier engines could not converge that case at all: the secant was
  read at the end moment, which means inverting `M(phi)` across a near-flat
  plateau, and it oscillated. It is read at the rotation there now.

  On a *determinate* span nothing can redistribute — statics fixes the connector
  moment at `F * lever` whatever the connector does — so a demand above the cap
  has no solution. The solver reports that instead of returning a very large
  deflection, and the message names the connector.

- **Reactions change on any model with a connector on a span-loaded member.**
  Two engine fixes land here. The curve was being driven by a member-end moment
  computed without the equivalent nodal loads, so it was short by the fixed-end
  moment; and the load vector was condensed through the connector's initial
  stiffness rather than its converged one. Global moment equilibrium was missing
  by the difference. The connector moment itself was already right — it is the
  reactions that move.

  Only models with a moment-rotation or stiffness curve on a loaded span are
  affected. A constant `rotational_release_m*` was never involved.

### Unchanged, worth stating

`rotational_release_mx/_my/_mz` — the plain constant rotational spring — is
untouched by all of this and behaves exactly as before. It shares no code path
with the curve evaluation: a hinge DOF without a curve resolves straight to its
release value.

## 0.1.86

Pins engine `fers_calculations==0.2.58`. Additive: no existing API moves.

### Changed

- **`CurveEndBehaviour.FAILURE` is accepted.** This builder refused it, mirroring
  the solver, which refused it too. Engine 0.2.58 supports it — it latches the
  break per member end and per DOF instead of re-reading it from the current
  moment — so the client-side rejection is gone. A curve carrying `FAILURE` now
  round-trips unchanged.

  A structure with no equilibrium without the connector — a determinate one never
  has — comes back with a `hinge_connector_failed` error in the results rather
  than a deflection. Use `YIELDING` for a connector that stops taking *more*
  moment but keeps carrying what it has.

### Added, via the engine

- **`MemberResult.member_displacement_peak`** — a member's true peak transverse
  deflection, as `(x_frac, displacement)`. `member_displacements` is a display
  grid of 11 stations and its *maximum* is quantised by that grid; scanning it for
  the worst sag under-reports, always unconservatively. The new field reduces the
  same curve on the grid it was integrated on, so it does not depend on how finely
  the member was meshed. See `examples/104_visual_member_deflected_shape.py`.

- Zero or negative material and section properties are now refused by the engine
  with a message naming the offending id, instead of surfacing much later as a
  non-convergence that has nothing to do with the cause.

## 0.1.85

> **This release carries 0.1.84 as well.** 0.1.84 pinned engine `==0.2.56`, which
> was squashed into the 0.2.57 engine release and never published — so 0.1.84
> could not build and was never released either. Both entries describe real
> changes; they both ship here.

Pins engine `fers_calculations==0.2.57` and adds the builder for native
moment-rotation connectors. Additive: no existing API moves.

**Engine 0.2.57** accepts a beam-end connector as its moment-rotation diagram,
`M(phi)`, rather than only as stiffness against end force. See the engine CHANGELOG.

### Added

- **`MomentRotationCurve` and `CurveEndBehaviour`**, plus
  `MemberHinge(moment_rotation_mx=..., _my=..., _mz=...)`.

  `StiffnessCurveConfig` describes a connector as `k(M)`, which the solver
  interpolates linearly in `M` while the real characteristic is linear in `phi` —
  so the two agree only at the tabulated points. An integrator measured 9.6 % in
  deflection between them and had to densify each curve to ~50–100 points to get
  within 0.03 %. Prefer `MomentRotationCurve` wherever you have a test curve; the
  four tabulated points now reproduce the closed form exactly.

  Rotation is in **radians** in every unit system. Connector looseness — EN 15512's
  free play before the connector takes any moment — needs no special field: it is a
  flat first segment, `[[0, 0], [0.002, 0], ...]`.

  Validated on construction (ascending rotations, non-decreasing moments, a
  symmetric curve starting at the origin) so a malformed diagram is refused where it
  was written rather than at solve time. The solver validates again on its side.

- **End behaviours**: `CONTINUOUS` (default), `STOP` and `YIELDING`. `FAILURE` is
  present in the enum for schema stability but is **refused by both this builder and
  the solver** — failure is irreversible, and the solver's secant linearization
  carries no path-dependent state, so a released connector re-engages on the next
  iterate and the solve degenerates without reporting it. Use `YIELDING` for a
  connector that stops taking more moment.

### Notes

- `tests/functionality/test_engine_pin_consistency.py` fails until 0.2.57 is on
  PyPI. That is the gate working as intended — publish the engine first.

## 0.1.84

> **Never published**, and its pin points at a version that does not exist.
> Engine 0.2.56 was squashed into the 0.2.57 release, so no artifact was built
> under either number here. Everything below shipped inside 0.1.85, which pins
> `==0.2.57`. Install that.

Pins engine `fers_calculations==0.2.56` and corrects example 104, which had been
advertising a guarantee the engine did not yet keep. No model API moves.

**Engine 0.2.56** makes `member_displacements` load-exact. Until 0.2.55 it was a
cubic-Hermite interpolation of the end DOFs, so a member carrying a span load
under-reported its own mid-span sag by `w·L⁴/(384·E·I)` — 20 % on a single simply
supported element. The same reconstruction sat behind the `MemberDeflection`
serviceability check, which therefore reported 80 % of the real sag on an
undivided UDL span. It also makes `ModeShape.period` and
`SeismicModeContribution.period` nullable: a rigid-body mode has no finite
period, and the engine had been emitting a `null` its own types could not read
back. See the engine CHANGELOG.

### Fixed

- **`examples/104_visual_member_deflected_shape.py` documented a property the
  engine did not have.** It described `member_displacements` as "load-exact" and
  "quartic-accurate under member loads" while the array was the very Hermite
  reconstruction it claimed to replace — and its assertions only checked
  `x/L = 0` and `x/L = 1`, which are nodal values and exact by construction under
  either scheme. The example passed while demonstrating nothing about the
  interior.

  It now states which engine version the guarantee arrived in, and checks every
  station against the textbook cantilever-under-UDL curve
  `w(x) = −q·x²(6L² − 4Lx + x²)/24EI`. It also prints what a Hermite curve would
  have reported at mid-span (−9.387 mm against the true −9.974 mm on this model,
  ~6 % short), so the difference the example exists to show is on screen rather
  than asserted out of sight.

### Notes

- No Python-side API change accompanies the nullable `period`: nothing in
  `fers_core` reads that field outside the generated models, which regenerate
  from the engine's OpenAPI.
- `tests/functionality/test_engine_pin_consistency.py` fails until 0.2.56 is on
  PyPI. That is the gate working as intended — publish the engine first.

## 0.1.81

Pins engine `fers_calculations==0.2.54`, adds the analysis-request builders and
signed stiffness curves, and puts a guard on the engine/schema coupling. No
model API moves; the generated schema is byte-identical to 0.1.80's apart from
the version stamp, because 0.2.54 changed no schema.

**Engine 0.2.54** cuts the peak memory of a solve by roughly 4x (826 MB -> 203 MB
on a 1058-member model) and adds `FERS_MAX_PARALLEL_SOLVES` to trade wall clock
against peak. It also settles the "native memory leak" report: there is no leak,
the engine frees everything after every solve. See the engine CHANGELOG.

### Added

- **`FERS.add_buckling_analysis()` / `FERS.add_modal_analysis()`** -- request an
  eigenvalue analysis in one call, following the `add_load_case` /
  `add_member_set` convention::

      model.add_buckling_analysis(reference=combo, num_modes=5)
      model.add_modal_analysis(num_modes=10, stiffness_reference=combo,
                               include_geometric_stiffness=True)

  `BucklingAnalysisSettings` already accepted a `LoadCase` or `LoadCombination`
  directly, so the wire's externally-tagged reference dict never had to be
  written by hand. What was missing was the last step: knowing the request has to
  be assigned to `model.analysis.buckling`. Both forwarders accept every keyword
  of the underlying settings class and keep its author-time validation, so a bad
  reference still fails immediately rather than in the solver.

- **`signed` on `StiffnessCurveConfig`** (and on `SupportCondition.spring_curve`)
  -- an asymmetric curve, with different stiffness in tension and compression,
  was unreachable from the SDK even though the engine has supported it for many
  releases and the generated models carry the field. A base plate that bears hard
  and lifts soft is now expressible.

  The flag is omitted from `to_dict()` when false, so symmetric curves serialize
  byte-identically and no existing document, fixture or test changes. A symmetric
  curve carrying negative force values now warns rather than raising: those points
  are evaluated at `abs(force)` and can never be reached, but the engine accepts
  them and example `131_StiffnessCurve_Cantilever.json` contains them, so raising
  would make the SDK stricter than the contract it wraps.

- **`scripts/regenerate_types.py`** regenerates `fers_core/types/pydantic_models.py`
  from a sibling `FERS_calculations` checkout (or any `openapi.json`) and stamps
  the engine version into its header. There was no committed way to do this
  before.

- **`tests/functionality/test_engine_pin_consistency.py`** asserts four things
  agree: the pins in `pyproject.toml` and `requirements.txt`, the stamp on the
  generated models, the engine actually installed in the environment running the
  tests, and the compiled extension's `__version__` against its distribution
  metadata.

  This is not hypothetical hygiene. The generated models were still stamped
  0.2.52 against a 0.2.53 pin, and the check for the *installed* engine fails on
  a machine where `fers_calculations 0.2.43` is installed against a 0.2.53 pin --
  ten releases and a dozen correctness fixes behind, with nothing in a green run
  to say so.

  **Note the release ordering it enforces:** this version pins an engine that
  must be on PyPI first. Until `fers_calculations 0.2.54` publishes, that check
  fails by design.


## 0.1.80

Pins engine `fers_calculations==0.2.53` and surfaces its bounded licence
handshake. No solver behaviour changes; nothing in the model API moves.

**No FERS call can hang on the network any more.** Engine 0.2.53 fixes a licence
handshake that could block forever (it stalled one integrator's unattended batch
run for ~6 hours at 0 % CPU). Two changes here make that reachable and useful
from the SDK:

- `run_analysis()` gains `api_key=` and `license_timeout=`. Both default to
  `None`, which keeps today's behaviour exactly — without an API key the engine
  makes no network call at all. `license_timeout` is seconds; on expiry the
  engine raises `fers_calculations.FersTimeoutError` **before the solve starts**,
  so retrying is safe.

- **`FersTimeoutError` is no longer flattened.** `run_analysis()` wrapped every
  exception in `RuntimeError(f"Failed to run calculation: {e}")`, which would
  have turned the new typed error back into something you can only detect by
  string-matching. It is now re-raised unchanged, while every other failure keeps
  its existing `RuntimeError` wrapper. This is what makes a batch loop able to
  tell "transient stall, retry" from "bad model, skip".

**New:** `run_analysis_to_file(output_path, ...)` — wraps the engine's
`calculate_to_file`, which has existed since 0.2.48 but was not reachable from
the SDK. The result JSON is streamed straight to disk instead of passing through
the Python heap, which is what makes multi-hundred-megabyte results survivable.
`self.resultsbundle` is deliberately left untouched.

**Also fixed, same failure class:** `FersCloudClient` called
`urllib.request.urlopen(req)` with no timeout, so a stalled cloud request blocked
forever — the same defect as the engine's, against the same `/api/sdk/me`
endpoint. It now defaults to 30 s (`FersCloudClient(timeout=...)` to change it)
and raises `CloudAPIError` on expiry. Read timeouts surface bare rather than
wrapped in `URLError`, so they previously escaped the client's error hierarchy
entirely; they are now caught explicitly.

**Documented:** the README previously described no API at all. It now covers
solving, `api_key`, `license_timeout`, `FersTimeoutError` and
`FERS_LICENSE_TIMEOUT` — including why the timeout and the definitive-failure
arms must be caught separately. New example
`fers_core/examples/203_Premium_Batch_Solve.py` shows the unattended-batch
pattern this release exists for: retry on `FersTimeoutError`, skip and record on
`RuntimeError`, and always report what was skipped. It runs without an API key
(at Free tier), so it is executable as-is.

**Not changed:** `run_analysis_from_file()` takes neither new argument, because
the engine's `calculate_from_file` accepts no API key and makes no network call —
both would be inert there. `license_timeout` bounds the licence handshake, never
the solve; for a hard ceiling on a whole solve, keep using a killable subprocess.

## 0.1.79

Pins engine `fers_calculations==0.2.52` and exposes its new eigen-analysis
surface from Python. Regenerated types.

**Correctness — read this if you use `stiffness_curve` hinges or supports.**
0.2.52 fixes bugs that affected ordinary *static* results, not just buckling:

- second-order equilibrium was enforced at the **zero-force** hinge stiffness
  while the tangent used the curve secant — the converged solution belonged to
  the wrong structure (3.7× deflection error on a softening connector);
- StiffnessCurve **support reactions were reported at `k(0)·u`** — a base plate
  that converged nearly rigid reported its nearly-pinned reaction;
- **hinge stiffness curves were never unit-normalized**, so non-SI models
  consumed both curve axes in raw user units.

Models without stiffness curves are unaffected.

**Also fixed here:** `requirements.txt` still pinned `0.2.50` while
`pyproject.toml` pinned `0.2.51`, so the engine you got depended on which file
installed it. Both now agree.

**New in `BucklingAnalysisSettings`:**

- `references=[...]` and `all_combinations=True` — analyse many reference loads
  in one call, each with its own linearization and geometric stiffness. Exactly
  one reference form may be given; passing two raises rather than silently
  resolving by precedence (`from_dict` still resolves stored documents the way
  the solver does).
- `member_effective_lengths=True` and `participation_threshold` — per-member
  critical-load-method buckling lengths with relevant-mode assignment.

**New in `ModalAnalysisSettings`:**

- `stiffness_reference` — linearize StiffnessCurve supports/hinges (and
  tension/compression engagement) at a load state rather than at force = 0.
- `include_geometric_stiffness=True` — preloaded (stress-stiffened) modal
  analysis. Requires `stiffness_reference`; raises at author time without it,
  mirroring the solver's own guard.

All new fields are omitted from the wire when unset, so existing documents and
call sites are unchanged.

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
  reported as clean success — onto a spurious equilibrium branch (on a braced
  rack model a tension-only diagonal carried 3.6× the correct force, a false
  structural FAIL). Such models now cold-start each combination and
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
