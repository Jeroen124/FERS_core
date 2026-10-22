from fers_core.builders import create_beam


# =============================================================================
# Example: self-weight in the load combinations
# =============================================================================
# The solver loads every member with its own weight, density·area·g, in the load
# case that `self_weight_load_case_id` names. A combination carries the
# self-weight only if it includes that case, so let the permanent-load case G
# take it: `create_load_case("G", self_weight=True)` creates G and sets both
# options.

span, imposed_load = 6.0, 5_000.0  # m, N/m downward
model = create_beam(span, "IPE300", udl=imposed_load, load_case_name="Q")
imposed = model.load_cases[0]
dead = model.create_load_case("G", self_weight=True)
model.create_load_combination("ULS", {dead: 1.35, imposed: 1.5}, limit_state="ULS")
model.create_load_combination("SLS", {dead: 1.0, imposed: 1.0}, limit_state="SLS")
model.run_analysis()

# The hand sum: the beam's weight as the solver works it out, plus the line load.
section = model.members[0].section
weight = section.material.density * section.area * 9.81 * span
print(f"self-weight of the beam: {weight:.1f} N")
for name, (g, q) in {"ULS": (1.35, 1.5), "SLS": (1.0, 1.0)}.items():
    results = model.resultsbundle.loadcombinations[name]
    reactions = sum(r.nodal_forces.fy for r in results.reaction_nodes.values())
    expected = g * weight + q * imposed_load * span
    print(f"{name}: reactions {reactions:.1f} N, by hand {expected:.1f} N")
    assert abs(reactions - expected) < 1e-6 * expected


# Without G: `enable_self_weight` alone puts the self-weight in a "Self-weight"
# case of the solver's own, which no combination built from Q includes. Every
# combination would be solved without it, so run_analysis refuses the model.
# -------------------------------------------------------------------------------
bare = create_beam(span, "IPE300", udl=imposed_load, load_case_name="Q")
bare.settings.analysis_options.enable_self_weight = True
bare.create_load_combination("ULS", {bare.load_cases[0]: 1.5}, limit_state="ULS")
try:
    bare.run_analysis()
    raise AssertionError("a model whose combinations all leave out the self-weight must be refused")
except ValueError as refusal:
    print(f"refused: {refusal}")
