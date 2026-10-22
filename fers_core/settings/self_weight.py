"""The rule that generated self-weight must reach the load combinations."""

from typing import Any, Optional


def self_weight_outside_combinations(document: dict[str, Any]) -> Optional[str]:
    """Why a model's self-weight reaches none of its load combinations, or None.

    ``document`` is shaped like :meth:`FERS.to_dict`. Without
    ``self_weight_load_case_id`` the solver puts the self-weight into a load case
    it creates, with the highest load-case id + 1, and a combination includes that
    case only by listing the id. One combination that includes the case is
    enough, and a factor of 0 counts: leaving it out of the others is a choice.
    The solver applies the same rule and warns with
    ``self_weight_not_in_combinations``.
    """
    analysis = document.get("analysis") or {}
    options = analysis.get("options") or {}
    combinations = analysis.get("load_combinations") or []
    if not options.get("enable_self_weight") or not combinations:
        return None
    named = options.get("self_weight_load_case_id")
    target = named
    if target is None:
        target = max((case.get("id", 0) for case in analysis.get("load_cases") or []), default=0) + 1
    for combination in combinations:
        for factor in combination.get("load_case_factors") or []:
            if factor.get("load_case_id") == target:
                return None
    if named is None:
        where = (
            f"the load case the solver creates for it (id {target}), "
            "because self_weight_load_case_id is not set"
        )
    else:
        where = f"load case {target}, its self_weight_load_case_id"
    return (
        f"Self-weight is on (enable_self_weight), but no load combination includes {where}, "
        "so every combination would be solved without self-weight. Set self_weight_load_case_id "
        "to a load case the combinations include, such as G; in Python, "
        'model.create_load_case("G", self_weight=True) creates G that way.'
    )
