"""The engine pin, the installed engine, and the generated models must agree.

Three things have to stay in step and nothing checked any of them:

1. ``pyproject.toml`` and ``requirements.txt`` both pin the engine. A bump that
   updated one and not the other meant the engine you got depended on which file
   installed it.
2. ``fers_core/types/pydantic_models.py`` is generated from the engine's OpenAPI
   document and is what ``FERS.validate_schema()`` validates against. If the pin
   moves and the models do not, the SDK validates new documents against an old
   contract.
3. The engine actually installed in the environment running the tests. This is
   the one that bites quietly: a suite passing against an engine ten patches
   behind the pin proves much less than it appears to, and there is nothing in a
   green run to say so.

All three are cheap to check and each has already gone wrong at least once.

To fix a failure here, run ``python scripts/regenerate_types.py`` and reinstall
the pinned engine into the environment you are testing in.
"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version as installed_version
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
GENERATED_MODELS = REPO_ROOT / "fers_core" / "types" / "pydantic_models.py"

PIN_RE = re.compile(r"fers[_-]calculations\s*==\s*([0-9][^\"'\s,]*)")
MARKER_RE = re.compile(r"^#\s*engine-version:\s*(\S+)\s*$", re.MULTILINE)


def _pin_from(path: Path) -> str:
    assert path.is_file(), f"{path} is missing"
    match = PIN_RE.search(path.read_text(encoding="utf-8"))
    assert match, f"No exact fers_calculations pin found in {path.name}"
    return match.group(1)


@pytest.fixture(scope="module")
def declared_pin() -> str:
    return _pin_from(PYPROJECT)


def test_pyproject_and_requirements_pin_the_same_engine(declared_pin):
    assert _pin_from(REQUIREMENTS) == declared_pin, (
        "pyproject.toml and requirements.txt pin different engine versions, so which "
        "engine you get depends on which file installed it. Update both together."
    )


def test_generated_models_were_generated_from_the_pinned_engine(declared_pin):
    text = GENERATED_MODELS.read_text(encoding="utf-8")
    match = MARKER_RE.search(text)
    assert match, (
        f"{GENERATED_MODELS.name} carries no `# engine-version:` marker. "
        "Regenerate it with: python scripts/regenerate_types.py"
    )
    assert match.group(1) == declared_pin, (
        f"{GENERATED_MODELS.name} was generated from engine {match.group(1)} but the pin "
        f"is {declared_pin}. validate_schema() is therefore checking documents against a "
        "different contract than the engine that will solve them. "
        "Run: python scripts/regenerate_types.py"
    )


def test_the_installed_engine_matches_the_pin(declared_pin):
    try:
        actual = installed_version("fers_calculations")
    except PackageNotFoundError:  # pragma: no cover - environment problem, not a code path
        pytest.fail(
            "fers_calculations is not installed in this environment, so nothing here is "
            f"exercising the real solver. Install the pin: pip install fers_calculations=={declared_pin}"
        )
    if actual != declared_pin:
        # Two very different situations produce this, and conflating them sends
        # the reader to the wrong fix.
        raise AssertionError(
            "\n".join(
                [
                    f"Installed engine is {actual} but the pin is {declared_pin}.",
                    "Two things look like this, and they have different fixes:",
                    "  (a) The environment is stale, so every test that solves is"
                    " exercising the wrong solver and a green run does not mean what it"
                    f" looks like. Fix: pip install fers_calculations=={declared_pin}",
                    "  (b) The pin is ahead of what is published, because this release is"
                    " waiting on the engine. That is the intended ordering: publish"
                    f" fers_calculations {declared_pin} first, then this. The check goes"
                    " green on a re-run once it is on PyPI, and nothing here should be"
                    " merged before then.",
                ]
            )
        )


def test_the_engine_module_agrees_with_its_package_metadata():
    """`__version__` comes from the compiled extension, the metadata from the wheel.

    They disagree when a stale build is shadowing an installed wheel, which looks
    exactly like a passing suite until results differ.
    """
    fers_calculations = pytest.importorskip("fers_calculations")
    module_version = getattr(fers_calculations, "__version__", None)
    if module_version is None:
        pytest.fail(
            "The installed fers_calculations exposes no __version__, which means it "
            "predates the attribute and is far older than any supported pin."
        )
    assert module_version == installed_version("fers_calculations"), (
        f"The compiled extension reports {module_version} but the installed distribution "
        f"is {installed_version('fers_calculations')} - a stale build is shadowing the wheel."
    )
