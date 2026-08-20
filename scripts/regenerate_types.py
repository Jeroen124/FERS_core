"""Regenerate ``fers_core/types/pydantic_models.py`` from the solver's schema.

``fers_core/types/pydantic_models.py`` is not hand-written: it is generated from
the engine's OpenAPI document and is what ``FERS.validate_schema()`` validates
against. Until now there was no committed way to regenerate it and no check that
it matched the pinned engine, so the coupling between "which engine we pin" and
"which schema we validate against" was maintained by memory alone. That is
exactly how the two-different-pins bug happened, and how this file came to be
labelled 0.2.52 while the pin said 0.2.53.

Usage, from the repository root::

    python scripts/regenerate_types.py                     # sibling engine checkout
    python scripts/regenerate_types.py --engine-repo ../FERS_calculations
    python scripts/regenerate_types.py --openapi path/to/openapi.json --engine-version 0.2.54

The engine's own CI already generates and commits ``types/openapi.json`` and
``types/pydantic_models.py`` on every release, so the sibling-checkout path is
usually a copy plus a stamped header rather than a fresh codegen. Pass
``--force-codegen`` to run ``datamodel-codegen`` regardless, which is what you
want when the two repos are on different generator versions.

After running, ``tests/functionality/test_engine_pin_consistency.py`` should pass.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "fers_core" / "types" / "pydantic_models.py"
DEFAULT_ENGINE_REPO = REPO_ROOT.parent / "FERS_calculations"

# The line this script stamps into the generated file, and the one the drift
# test reads. Kept as a comment so the file stays importable and the stamp
# survives any formatter.
VERSION_MARKER = "# engine-version:"


def engine_version_from_repo(engine_repo: Path) -> str:
    """Read the version from the engine's Cargo.toml (its source of truth)."""
    cargo = engine_repo / "Cargo.toml"
    if not cargo.is_file():
        sys.exit(f"No Cargo.toml at {cargo}. Pass --engine-repo or --engine-version.")
    for line in cargo.read_text(encoding="utf-8").splitlines():
        match = re.match(r'^version\s*=\s*"([^"]+)"', line.strip())
        if match:
            return match.group(1)
    sys.exit(f"Could not find a version in {cargo}.")


def run_codegen(openapi: Path) -> str:
    """Run datamodel-codegen exactly as the engine's release workflow does."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "pydantic_models.py"
        cmd = [
            "datamodel-codegen",
            "--input",
            str(openapi),
            "--input-file-type",
            "openapi",
            "--output",
            str(out),
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--disable-timestamp",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            sys.exit("datamodel-codegen not found. Install it with:\n  pip install datamodel-code-generator")
        except subprocess.CalledProcessError as exc:
            sys.exit(f"datamodel-codegen failed:\n{exc.stderr}")
        return out.read_text(encoding="utf-8")


def stamp(source: str, engine_version: str) -> str:
    """Replace or insert the engine-version marker in the generated header."""
    lines = source.splitlines()
    stamped = f"{VERSION_MARKER} {engine_version}"
    for i, line in enumerate(lines):
        if line.startswith(VERSION_MARKER):
            lines[i] = stamped
            return "\n".join(lines) + "\n"
    # No marker yet: put it directly under datamodel-codegen's own header block,
    # which is the leading run of comment lines.
    insert_at = 0
    while insert_at < len(lines) and lines[insert_at].startswith("#"):
        insert_at += 1
    lines.insert(insert_at, stamped)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine-repo",
        type=Path,
        default=DEFAULT_ENGINE_REPO,
        help="path to the FERS_calculations checkout (default: sibling directory)",
    )
    parser.add_argument(
        "--openapi",
        type=Path,
        default=None,
        help="path to an openapi.json, instead of taking it from the engine repo",
    )
    parser.add_argument(
        "--engine-version",
        default=None,
        help="engine version to stamp (default: read from the engine's Cargo.toml)",
    )
    parser.add_argument(
        "--force-codegen",
        action="store_true",
        help="always run datamodel-codegen, even when the engine repo already has a generated file",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether the target is up to date and exit non-zero if not; write nothing",
    )
    args = parser.parse_args()

    engine_version = args.engine_version or engine_version_from_repo(args.engine_repo)

    if args.openapi is not None:
        source = run_codegen(args.openapi)
    else:
        prebuilt = args.engine_repo / "types" / "pydantic_models.py"
        openapi = args.engine_repo / "types" / "openapi.json"
        if prebuilt.is_file() and not args.force_codegen:
            source = prebuilt.read_text(encoding="utf-8")
        elif openapi.is_file():
            source = run_codegen(openapi)
        else:
            sys.exit(
                f"Found neither {prebuilt} nor {openapi}.\n"
                "Point --engine-repo at a FERS_calculations checkout, or pass --openapi."
            )

    new_text = stamp(source, engine_version)
    old_text = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""

    if new_text == old_text:
        print(f"Up to date: {TARGET.relative_to(REPO_ROOT)} (engine {engine_version})")
        return 0

    if args.check:
        print(
            f"OUT OF DATE: {TARGET.relative_to(REPO_ROOT)} does not match engine "
            f"{engine_version}. Run: python scripts/regenerate_types.py"
        )
        return 1

    # No .bak: the file is committed, so git already is the safety net, and a
    # stray backup next to a generated module is one import away from confusion.
    TARGET.write_text(new_text, encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(REPO_ROOT)} from engine {engine_version}")
    print("Now update the pin in pyproject.toml and requirements.txt to match, then run the suite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
