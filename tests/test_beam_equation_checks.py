import pytest
import beam_equation_checks as bec

# Grab all the callables you exposed in __init__.py
ANALYSES = [getattr(bec, name) for name in bec.__all__]


@pytest.mark.parametrize("analysis_func", ANALYSES)
def test_analysis_passes(analysis_func):
    """
    Each analysis function should return either:
      - a truthy value (e.g. True), or
      - a dict containing {"status": True}
    """
    result = analysis_func()

    # Allow plain True/False returns or dicts with a "status" key
    if isinstance(result, dict) and "status" in result:
        assert result["status"], f"{analysis_func.__name__} returned status=False"
    else:
        assert bool(result), f"{analysis_func.__name__} returned falsey ({result!r})"
