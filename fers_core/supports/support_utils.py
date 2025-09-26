# fers_core/fers/support_utils.py
import re


def get_condition_type(support_condition) -> str:
    """
    Return a lowercase condition type
    ('fixed', 'free', 'spring', 'positive-only', 'negative-only').
    Uses .to_dict()['type'] or .type; falls back to parsing str(condition).
    """
    if support_condition is None:
        return "fixed"
    try:
        if hasattr(support_condition, "to_dict"):
            d = support_condition.to_dict()
            if isinstance(d, dict) and "type" in d:
                return str(d["type"]).strip().lower()
    except Exception:
        pass
    if hasattr(support_condition, "type"):
        try:
            return str(getattr(support_condition, "type")).strip().lower()
        except Exception:
            pass
    s = str(support_condition).strip().lower()
    m = re.search(r"type\s*=\s*([a-z\-]+)", s)
    if m:
        return m.group(1)
    return s


def condition_type_and_stiffness(condition) -> tuple[str, float | None]:
    """
    Return (ctype, stiffness). Tries .to_dict()['type'], .type, then str().
    """
    if condition is None:
        return "fixed", None

    if hasattr(condition, "to_dict"):
        try:
            d = condition.to_dict()
            ctype = d.get("type", None)
            stiffness = d.get("stiffness", None)
            if ctype is not None:
                return str(ctype).strip().lower(), stiffness
        except Exception:
            pass

    if hasattr(condition, "type"):
        try:
            ctype = getattr(condition, "type")
            return str(ctype).strip().lower(), getattr(condition, "stiffness", None)
        except Exception:
            pass

    s = str(condition).strip().lower()
    m = re.search(r"type\s*=\s*([a-z\-]+)", s)
    if m:
        return m.group(1), None
    return s, None


def format_support_short(nodal_support) -> str:
    """
    Compact string: U[Fx,Fr,k] R[Fr,Fr,Fx].
    """
    mapping = {"fixed": "Fx", "free": "Fr", "spring": "k", "positive-only": "+", "negative-only": "-"}

    def trio(conditions_dict: dict) -> list[str]:
        out = []
        for axis in ("X", "Y", "Z"):
            cond = (
                conditions_dict.get(axis)
                or conditions_dict.get(axis.upper())
                or conditions_dict.get(axis.lower())
            )
            ctype, _ = condition_type_and_stiffness(cond) if cond is not None else ("fixed", None)
            out.append(mapping.get(ctype, ctype[:2]))
        return out

    u = trio(nodal_support.displacement_conditions)
    r = trio(nodal_support.rotation_conditions)
    return f"U[{','.join(u)}] R[{','.join(r)}]"


def choose_marker(nodal_support) -> str:
    """
    Choose a matplotlib marker based on translational constraints.
    - all fixed  -> 's'
    - any spring -> 'D'
    - all free   -> 'o'
    - mixed      -> '*'
    """
    types: list[str] = []
    for axis in ("X", "Y", "Z"):
        cond = nodal_support.displacement_conditions.get(axis)
        ctype, _ = condition_type_and_stiffness(cond) if cond is not None else ("fixed", None)
        types.append(ctype)

    if all(t == "fixed" for t in types):
        return "s"
    if any(t == "spring" for t in types):
        return "D"
    if all(t == "free" for t in types):
        return "o"
    return "*"


def translational_summary(nodal_support) -> str:
    """
    Classify translations: 'all_fixed', 'all_free', 'any_spring', 'mixed'.
    """
    types = []
    for axis in ("X", "Y", "Z"):
        c = nodal_support.displacement_conditions.get(axis)
        types.append(get_condition_type(c))
    if all(t == "fixed" for t in types):
        return "all_fixed"
    if all(t == "free" for t in types):
        return "all_free"
    if any(t == "spring" for t in types):
        return "any_spring"
    return "mixed"


def color_for_condition_type(condition_type: str) -> str:
    """
    Map condition types to a color.
    """
    return {
        "fixed": "crimson",
        "spring": "orange",
        "free": "lightgray",
        "positive-only": "green",
        "negative-only": "purple",
    }.get(condition_type, "black")


def format_support_label(nodal_support) -> str:
    mapping = {"fixed": "F", "free": "R", "spring": "S", "positive-only": "+", "negative-only": "-"}

    def trio(conds: dict) -> list[str]:
        out = []
        for axis in ("X", "Y", "Z"):
            c = conds.get(axis) or conds.get(axis.upper()) or conds.get(axis.lower())
            out.append(mapping.get(get_condition_type(c), "??"))
        return out

    return (
        f"U[{','.join(trio(nodal_support.displacement_conditions))}] "
        f"R[{','.join(trio(nodal_support.rotation_conditions))}]"
    )
