# Changelog

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
