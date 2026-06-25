# Changelog

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
