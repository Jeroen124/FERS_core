"""``fers``: the FERS command line.

A thin adapter over the SDK and the engine wheel for shells, scripts, CI jobs
and coding agents. Every large output (solved results, schemas, reports) goes to
a file; stdout carries one line per command, or a JSON object with ``--json``.

Exit codes::

    0  done
    1  the engine refused or failed the solve
    2  bad input: a missing file, invalid JSON, a model that fails the schema
    3  licence: no key where one is needed, a rejected key, a licence timeout
    4  solved, but with recorded failures (``solve_failures`` or
       ``load_case_failures`` in the results)

``FERS_API_KEY`` supplies the API key when ``--api-key`` is not given;
``FERS_LICENSE_TIMEOUT`` is read by the engine. Without a key the engine runs
at free-tier limits and makes no network call.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from importlib import metadata
from pathlib import Path
from typing import Any, Optional

import fers_calculations

EXIT_OK = 0
EXIT_ENGINE = 1
EXIT_INPUT = 2
EXIT_LICENCE = 3
EXIT_PARTIAL = 4

# The engine raises RuntimeError for a solve failure and for a licence failure
# alike; the message tells them apart.
_LICENCE_PATTERN = re.compile(
    r"licen[cs]e|api[ _-]?key|premium|unauthori[sz]ed|forbidden|\b40[13]\b"
    r"|member limit|limit exceeded|exceeds allowed maximum",
    re.IGNORECASE,
)

# Results files up to this size are read back for the summary line; above it
# only the size is reported, which is what a ResultRequest is for.
_SUMMARY_MAX_BYTES = 64 * 1024 * 1024

_VISUAL_EXAMPLE = re.compile(r"^[19]\d{2}_")
_EXAMPLE_FILE = re.compile(r"^\d{3}_.*\.py$")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _emit(as_json: bool, payload: dict[str, Any], line: str) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(line)


def _fail(code: int, message: str, as_json: bool = False) -> int:
    if as_json:
        print(json.dumps({"ok": False, "exit_code": code, "error": message}, indent=2))
    else:
        print(f"error: {message}", file=sys.stderr)
    return code


def _fmt_bytes(n: int) -> str:
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} kB"
    return f"{n / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _read_model_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"no such file: {path}")
    text = path.read_text(encoding="utf-8-sig")
    json.loads(text)
    return text


def _api_key(args: argparse.Namespace) -> Optional[str]:
    key = getattr(args, "api_key", None) or os.environ.get("FERS_API_KEY")
    return key or None


def _engine_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    key = _api_key(args)
    if key:
        kwargs["api_key"] = key
    timeout = getattr(args, "license_timeout", None)
    if timeout is not None:
        kwargs["license_timeout"] = timeout
    return kwargs


def _classify_engine_error(exc: BaseException) -> int:
    if isinstance(exc, fers_calculations.FersTimeoutError):
        return EXIT_LICENCE
    if _LICENCE_PATTERN.search(str(exc)):
        return EXIT_LICENCE
    return EXIT_ENGINE


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _summarise_results_file(path: Path) -> dict[str, Any]:
    """Counts from a solved document: result sets, failures, convergence, messages."""
    size = path.stat().st_size
    summary: dict[str, Any] = {"path": str(path), "bytes": size}
    if size > _SUMMARY_MAX_BYTES:
        summary["note"] = "file too large to summarise; narrow it with result_requests"
        return summary
    with path.open("r", encoding="utf-8-sig") as fh:
        document = json.load(fh)
    results = document.get("results") or {}
    sets = list((results.get("loadcases") or {}).values())
    sets += list((results.get("loadcombinations") or {}).values())
    not_converged = 0
    errors = 0
    warnings = 0
    for result_set in sets:
        diagnostics = result_set.get("solver_diagnostics") or {}
        if diagnostics.get("converged") is False:
            not_converged += 1
        messages = result_set.get("errors_and_warnings") or {}
        errors += len(messages.get("errors") or [])
        warnings += len(messages.get("warnings") or [])
    summary.update(
        {
            "load_cases": len(results.get("loadcases") or {}),
            "load_combinations": len(results.get("loadcombinations") or {}),
            "solve_failures": len(results.get("solve_failures") or []),
            "load_case_failures": len(results.get("load_case_failures") or []),
            "not_converged": not_converged,
            "errors": errors,
            "warnings": warnings,
            "unity_checks": len(results.get("unity_check_results") or []),
        }
    )
    return summary


def _summary_line(summary: dict[str, Any], seconds: float) -> str:
    if "load_cases" not in summary:
        size = _fmt_bytes(summary["bytes"])
        return f"solved in {seconds:.1f} s -> {summary['path']} ({size}; {summary['note']})"
    parts = [
        f"{summary['load_cases']} load cases",
        f"{summary['load_combinations']} combinations",
    ]
    failures = summary["solve_failures"] + summary["load_case_failures"]
    if failures:
        parts.append(f"{failures} recorded failures")
    if summary["not_converged"]:
        parts.append(f"{summary['not_converged']} not converged")
    if summary["errors"]:
        parts.append(f"{summary['errors']} errors")
    if summary["warnings"]:
        parts.append(f"{summary['warnings']} warnings")
    if summary["unity_checks"]:
        parts.append(f"{summary['unity_checks']} unity checks")
    size = _fmt_bytes(summary["bytes"])
    return f"solved: {', '.join(parts)} in {seconds:.1f} s -> {summary['path']} ({size})"


def _sdk_version() -> str:
    try:
        return metadata.version("FERS")
    except metadata.PackageNotFoundError:
        return "unknown"


def _examples_dir() -> Path:
    import fers_core

    return Path(fers_core.__file__).parent / "examples"


def _list_examples(include_visual: bool) -> list[Path]:
    files = sorted(p for p in _examples_dir().iterdir() if _EXAMPLE_FILE.match(p.name))
    if include_visual:
        return files
    return [p for p in files if not _VISUAL_EXAMPLE.match(p.name)]


def _find_example(selector: str) -> Path:
    candidates = [p for p in _list_examples(True) if p.name == selector or p.name.startswith(selector)]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(f"no example matches {selector!r}; try `fers examples list --all`")
    names = ", ".join(p.name for p in candidates)
    raise ValueError(f"{selector!r} matches more than one example: {names}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_solve(args: argparse.Namespace) -> int:
    """Solve a model file with the engine and write the solved document to a file.

    The JSON goes to the engine as it is; the engine validates it. The results
    never pass through this process: the engine streams them to ``--out``
    (default: ``<model>_results.json`` beside the model). Only a summary is
    printed, so a large result does not land in a terminal or an agent's context.
    """
    model = Path(args.model)
    out = Path(args.out) if args.out else model.with_name(f"{model.stem}_results.json")
    try:
        text = _read_model_text(model)
    except (OSError, ValueError) as exc:
        return _fail(EXIT_INPUT, str(exc), args.json)
    started = time.perf_counter()
    try:
        fers_calculations.calculate_to_file(text, str(out), **_engine_kwargs(args))
    except Exception as exc:  # the wheel raises RuntimeError for every refusal
        return _fail(_classify_engine_error(exc), str(exc), args.json)
    seconds = time.perf_counter() - started
    try:
        summary = _summarise_results_file(out)
    except (OSError, ValueError) as exc:
        return _fail(EXIT_ENGINE, f"solved, but the results file could not be read back: {exc}", args.json)
    summary["seconds"] = round(seconds, 3)
    partial = bool(summary.get("solve_failures") or summary.get("load_case_failures"))
    summary["ok"] = not partial
    summary["exit_code"] = EXIT_PARTIAL if partial else EXIT_OK
    _emit(args.json, summary, _summary_line(summary, seconds))
    return summary["exit_code"]


def cmd_validate(args: argparse.Namespace) -> int:
    """Check a model file against the solver's input schema without solving.

    This is the SDK's schema validation (``FERS.validate_schema``): field names,
    enum values and nesting. References between objects are checked by the
    engine at solve time.
    """
    from fers_core import FERS

    path = Path(args.model)
    if not path.is_file():
        return _fail(EXIT_INPUT, f"no such file: {path}", args.json)
    try:
        model = FERS.from_json(str(path))
        model.validate_schema()
    except ValueError as exc:
        return _fail(EXIT_INPUT, str(exc), args.json)
    except Exception as exc:
        return _fail(EXIT_INPUT, f"could not read {path}: {exc}", args.json)
    counts = {
        "ok": True,
        "exit_code": EXIT_OK,
        "path": str(path),
        "nodes": model.number_of_nodes(),
        "members": len(model.get_all_members()),
        "plates": len(model.get_all_plates()),
        "load_cases": len(model.load_cases),
        "load_combinations": len(model.load_combinations),
    }
    _emit(
        args.json,
        counts,
        f"valid: {counts['nodes']} nodes, {counts['members']} members, {counts['plates']} plates, "
        f"{counts['load_cases']} load cases, {counts['load_combinations']} combinations",
    )
    return EXIT_OK


def _first_sentence(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]


def cmd_schema(args: argparse.Namespace) -> int:
    """Print the solver's input schema, one of its definitions, or the list of them.

    The schema is the SDK's generated pydantic model of the engine's OpenAPI
    contract, so it is exactly what ``fers validate`` checks against.
    """
    from fers_core.types.pydantic_models import FERS as InputSchema

    schema = InputSchema.model_json_schema()
    definitions = schema.get("$defs") or {}
    if args.list:
        rows = [("FERS", _first_sentence(schema.get("description")) or "the document root")]
        for name, definition in sorted(definitions.items()):
            rows.append((name, _first_sentence(definition.get("description"))))
        if args.json:
            print(json.dumps({"roots": [{"name": n, "description": d} for n, d in rows]}, indent=2))
        else:
            width = max(len(n) for n, _ in rows)
            for name, description in rows:
                print(f"{name:<{width}}  {description}")
        return EXIT_OK
    if args.root and args.root != "FERS":
        if args.root not in definitions:
            message = f"unknown schema root {args.root!r}; see `fers schema --list`"
            return _fail(EXIT_INPUT, message, args.json)
        payload: Any = definitions[args.root]
    else:
        payload = schema
    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({_fmt_bytes(len(text.encode('utf-8')))})")
    else:
        print(text)
    return EXIT_OK


def cmd_sections(args: argparse.Namespace) -> int:
    """List the section catalogues, or print one section's properties in SI units."""
    from fers_core import MaterialLibrary, list_sections, resolve_section
    from fers_core.sections.steel_sections_en import section_catalogue

    if args.sections_command == "list":
        try:
            names = list_sections(args.series)
        except (KeyError, ValueError) as exc:
            return _fail(EXIT_INPUT, str(exc), args.json)
        if args.contains:
            needle = args.contains.lower()
            names = [n for n in names if needle in n.lower()]
        if args.json:
            print(json.dumps({"count": len(names), "sections": names}, indent=2))
        else:
            print("\n".join(names))
        return EXIT_OK
    try:
        material = MaterialLibrary.get(args.material)
        section = resolve_section(args.name, material)
    except (KeyError, ValueError) as exc:
        return _fail(EXIT_INPUT, str(exc), args.json)
    properties = section.to_dict()
    for key in ("id", "material", "shape_path"):
        properties.pop(key, None)
    properties["catalogue"] = section_catalogue(args.name)
    properties["units"] = "m, m2, m4, m6"
    if args.json:
        print(json.dumps(properties, indent=2))
    else:
        for key, value in properties.items():
            print(f"{key:<13} {value}")
    return EXIT_OK


def cmd_materials(args: argparse.Namespace) -> int:
    """List the material presets, or print one in SI units."""
    from fers_core import MaterialLibrary

    if args.materials_command == "list":
        names = MaterialLibrary.list_available()
        if args.json:
            print(json.dumps({"count": len(names), "materials": names}, indent=2))
        else:
            print("\n".join(names))
        return EXIT_OK
    try:
        material = MaterialLibrary.get(args.name)
    except (KeyError, ValueError) as exc:
        return _fail(EXIT_INPUT, str(exc), args.json)
    properties = material.to_dict()
    properties.pop("id", None)
    properties["units"] = "Pa, kg/m3"
    if args.json:
        print(json.dumps(properties, indent=2))
    else:
        for key, value in properties.items():
            print(f"{key:<13} {value}")
    return EXIT_OK


def cmd_examples(args: argparse.Namespace) -> int:
    """List, print or run the numbered examples shipped with the package.

    Each example builds a model with the SDK, solves it and checks the result
    against a closed-form answer, which makes them the quickest reference for
    the object API. ``run`` executes one in a scratch directory (or ``--dir``)
    because the examples write their model JSON next to where they run.
    """
    if args.examples_command == "list":
        files = _list_examples(args.all)
        if args.json:
            listing = {"directory": str(_examples_dir()), "examples": [p.name for p in files]}
            print(json.dumps(listing, indent=2))
        else:
            print("\n".join(p.name for p in files))
        return EXIT_OK
    try:
        example = _find_example(args.example)
    except (FileNotFoundError, ValueError) as exc:
        return _fail(EXIT_INPUT, str(exc), args.json)
    if args.examples_command == "show":
        print(example.read_text(encoding="utf-8"))
        return EXIT_OK
    workdir = Path(args.dir) if args.dir else Path(tempfile.mkdtemp(prefix="fers-example-"))
    workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    completed = subprocess.run([sys.executable, str(example)], cwd=str(workdir), env=env)
    return EXIT_OK if completed.returncode == 0 else EXIT_ENGINE


def _unity_row(result: Any) -> dict[str, Any]:
    governing = _field(result, "governing") or {}
    entity = _field(governing, "entity")
    if isinstance(entity, dict):
        entity = entity.get("id") or entity.get("member_id") or entity
    elif entity is not None and not isinstance(entity, (str, int)):
        entity = _field(entity, "id") or _field(entity, "member_id") or str(entity)
    status = _field(result, "status")
    return {
        "check": _field(result, "check_id") or _field(result, "name"),
        "name": _field(result, "name"),
        "status": str(_field(status, "value") or status or ""),
        "utilization": _field(result, "max_utilization"),
        "governing_entity": entity,
        "governing_combination": _field(governing, "governing_combination_id"),
        "unsolved_combinations": len(_field(result, "unsolved_combination_ids") or []),
    }


def cmd_check(args: argparse.Namespace) -> int:
    """Solve a model file and print its unity-check results.

    The model must carry unity-check definitions (``fers schema UnityCheckDefinition``
    or ``check_beam`` in the SDK). The solve runs in-process through the SDK, so
    this is for models whose results fit in memory; ``fers solve`` streams.
    """
    from fers_core import FERS

    path = Path(args.model)
    if not path.is_file():
        return _fail(EXIT_INPUT, f"no such file: {path}", args.json)
    try:
        model = FERS.from_json(str(path))
    except Exception as exc:
        return _fail(EXIT_INPUT, f"could not read {path}: {exc}", args.json)
    try:
        # run_analysis prints a progress line; stdout here is the command's output.
        with contextlib.redirect_stdout(io.StringIO()):
            model.run_analysis(**_engine_kwargs(args))
    except ValueError as exc:
        return _fail(EXIT_INPUT, str(exc), args.json)
    except Exception as exc:
        return _fail(_classify_engine_error(exc), str(exc), args.json)
    results = model.unity_check_results()
    rows = [_unity_row(r) for r in results]
    if args.out:
        model.save_to_json(args.out)
    if args.json:
        payload = {"ok": True, "exit_code": EXIT_OK, "checks": rows, "output": args.out}
        print(json.dumps(payload, indent=2, default=str))
        return EXIT_OK
    if not rows:
        print("no unity checks in this model")
        return EXIT_OK
    for row in rows:
        utilization = row["utilization"]
        value = f"{utilization:.3f}" if isinstance(utilization, (int, float)) else "-"
        line = f"{row['check']}: {row['status']}, utilization {value}"
        if row["governing_entity"] is not None:
            line += f", governing {row['governing_entity']} in combination {row['governing_combination']}"
        if row["unsolved_combinations"]:
            line += f", {row['unsolved_combinations']} combinations unsolved"
        print(line)
    if args.out:
        print(f"-> {args.out}")
    return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    """Render the unity-check HTML report of an already-solved document.

    No re-solve: the engine fills each check's report template from the results
    in the file and writes the consolidated ``report_html`` to ``--out``.
    """
    path = Path(args.solved)
    try:
        text = _read_model_text(path)
    except (OSError, ValueError) as exc:
        return _fail(EXIT_INPUT, str(exc), args.json)
    try:
        rendered = fers_calculations.render_reports_from_json(text)
    except Exception as exc:
        return _fail(_classify_engine_error(exc), str(exc), args.json)
    document = json.loads(rendered) if isinstance(rendered, str) else rendered
    html = (document.get("results") or {}).get("report_html") if isinstance(document, dict) else None
    if not html:
        return _fail(
            EXIT_INPUT,
            "the document has no report: it needs unity checks and solved results",
            args.json,
        )
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    _emit(
        args.json,
        {"ok": True, "exit_code": EXIT_OK, "path": str(out), "bytes": out.stat().st_size},
        f"wrote {out} ({_fmt_bytes(out.stat().st_size)})",
    )
    return EXIT_OK


def _licence_status(key: str, timeout: float) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    base = os.environ.get("FERS_CLOUD_URL", "https://ferscloud.com").rstrip("/")
    request = urllib.request.Request(f"{base}/api/sdk/me", headers={"X-API-Key": key})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"reachable": True, "accepted": False, "status": exc.code, "server": base}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"reachable": False, "accepted": False, "server": base, "error": str(exc)}
    return {
        "reachable": True,
        "accepted": True,
        "server": base,
        "premium": bool(body.get("is_premium")),
    }


def _skill_path() -> Path:
    import fers_core

    return Path(fers_core.__file__).parent / "skills" / "fers" / "SKILL.md"


def cmd_skill(args: argparse.Namespace) -> int:
    """Print the skill file for coding agents, or install it into a project.

    The skill is one page in the format coding agents read before a task: the
    install step, the author-validate-solve-read loop, how to read results, and
    when the hosted MCP server fits better. ``--install DIR`` writes it to
    ``DIR/.claude/skills/fers/SKILL.md``, which is where Claude Code looks;
    other agents can be pointed at ``--path``.
    """
    source = _skill_path()
    if args.path:
        print(source)
        return EXIT_OK
    if args.install:
        target = Path(args.install) / ".claude" / "skills" / "fers" / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        _emit(args.json, {"ok": True, "exit_code": EXIT_OK, "path": str(target)}, f"wrote {target}")
        return EXIT_OK
    print(source.read_text(encoding="utf-8"), end="")
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    """Report the installed versions and, with a key, whether the licence server accepts it."""
    report: dict[str, Any] = {
        "python": sys.version.split()[0],
        "sdk": _sdk_version(),
        "engine": fers_calculations.__version__,
        "examples": str(_examples_dir()),
    }
    key = _api_key(args)
    report["api_key"] = "set" if key else "not set (free tier, no network call)"
    code = EXIT_OK
    if key and not args.offline:
        status = _licence_status(key, args.license_timeout or 10.0)
        report["licence"] = status
        if not status["accepted"]:
            code = EXIT_LICENCE
    if args.json:
        report["ok"] = code == EXIT_OK
        report["exit_code"] = code
        print(json.dumps(report, indent=2))
        return code
    for name, value in report.items():
        if name == "licence":
            if value["accepted"]:
                tier = "premium" if value["premium"] else "free"
                print(f"licence      accepted by {value['server']} ({tier})")
            elif value["reachable"]:
                print(f"licence      rejected by {value['server']} (HTTP {value['status']})")
            else:
                print(f"licence      {value['server']} not reachable: {value['error']}")
        else:
            print(f"{name:<12} {value}")
    return code


def cmd_version(args: argparse.Namespace) -> int:
    """Print the SDK and engine versions."""
    payload = {"sdk": _sdk_version(), "engine": fers_calculations.__version__}
    _emit(args.json, payload, f"FERS {payload['sdk']} / fers_calculations {payload['engine']}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="print a JSON object instead of a line")


def _add_licence(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api-key", help="API key for Premium limits; default $FERS_API_KEY; omit for the free tier"
    )
    parser.add_argument(
        "--license-timeout",
        type=float,
        metavar="SECONDS",
        help="bound on the licence handshake, not on the solve (engine default 30, or $FERS_LICENSE_TIMEOUT)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fers",
        description="FERS from the command line: solve, validate and inspect structural models.",
        epilog="Exit codes: 0 done, 1 engine error, 2 bad input, 3 licence, 4 solved with recorded failures.",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.required = True

    solve = commands.add_parser("solve", help="solve a model file; results stream to a file")
    solve.add_argument("model", help="model JSON file")
    solve.add_argument("--out", help="results file (default: <model>_results.json beside the model)")
    _add_licence(solve)
    _add_json(solve)
    solve.set_defaults(func=cmd_solve)

    validate = commands.add_parser("validate", help="check a model file against the input schema")
    validate.add_argument("model", help="model JSON file")
    _add_json(validate)
    validate.set_defaults(func=cmd_validate)

    schema = commands.add_parser("schema", help="print the input schema, one definition, or list them")
    schema.add_argument(
        "root", nargs="?", help="a definition name, e.g. Analysis or Member (default: everything)"
    )
    schema.add_argument("--list", action="store_true", help="list the definitions with one line each")
    schema.add_argument("--out", help="write the schema to a file instead of stdout")
    _add_json(schema)
    schema.set_defaults(func=cmd_schema)

    sections = commands.add_parser("sections", help="section catalogues (EN, British Steel, AISC)")
    sections_commands = sections.add_subparsers(dest="sections_command", metavar="SUBCOMMAND")
    sections_commands.required = True
    sections_list = sections_commands.add_parser("list", help="list section names")
    sections_list.add_argument(
        "--series", help="IPE, HEA, HEB, HEM, UPE, CHS, RHS, SHS, L, UB, UC, PFC, W, HP, HSS, HSSR, PIPE"
    )
    sections_list.add_argument("--contains", help="keep names containing this text")
    _add_json(sections_list)
    sections_get = sections_commands.add_parser("get", help="one section's properties in SI units")
    sections_get.add_argument(
        "name", help='designation, e.g. IPE200, "RHS 200x100x8", "UB 457x191x67", W10X22'
    )
    sections_get.add_argument(
        "--material", default="S235", help="material preset for the section (default S235)"
    )
    _add_json(sections_get)
    sections.set_defaults(func=cmd_sections)

    materials = commands.add_parser("materials", help="material presets")
    materials_commands = materials.add_subparsers(dest="materials_command", metavar="SUBCOMMAND")
    materials_commands.required = True
    materials_list = materials_commands.add_parser("list", help="list preset names")
    _add_json(materials_list)
    materials_get = materials_commands.add_parser("get", help="one preset's properties in SI units")
    materials_get.add_argument("name", help="preset name, e.g. S235")
    _add_json(materials_get)
    materials.set_defaults(func=cmd_materials)

    examples = commands.add_parser("examples", help="the numbered examples shipped with the package")
    examples_commands = examples.add_subparsers(dest="examples_command", metavar="SUBCOMMAND")
    examples_commands.required = True
    examples_list = examples_commands.add_parser("list", help="list the examples")
    examples_list.add_argument(
        "--all", action="store_true", help="include the 1xx visual and 9xx experimental ones"
    )
    _add_json(examples_list)
    examples_show = examples_commands.add_parser("show", help="print an example's source")
    examples_show.add_argument("example", help="number or file name prefix, e.g. 001")
    examples_run = examples_commands.add_parser("run", help="run an example")
    examples_run.add_argument("example", help="number or file name prefix, e.g. 001")
    examples_run.add_argument(
        "--dir", help="working directory for the example's files (default: a scratch directory)"
    )
    examples.set_defaults(func=cmd_examples)

    check = commands.add_parser("check", help="solve a model file and print its unity-check results")
    check.add_argument("model", help="model JSON file carrying unity-check definitions")
    check.add_argument("--out", help="also write the solved document here")
    _add_licence(check)
    _add_json(check)
    check.set_defaults(func=cmd_check)

    report = commands.add_parser("report", help="render the unity-check HTML report of a solved document")
    report.add_argument("solved", help="solved model JSON file")
    report.add_argument("--out", required=True, help="HTML file to write")
    _add_json(report)
    report.set_defaults(func=cmd_report)

    skill = commands.add_parser("skill", help="the skill file for coding agents: print it or install it")
    skill.add_argument("--install", metavar="DIR", help="write it to DIR/.claude/skills/fers/SKILL.md")
    skill.add_argument("--path", action="store_true", help="print the file's path instead of its text")
    _add_json(skill)
    skill.set_defaults(func=cmd_skill)

    doctor = commands.add_parser(
        "doctor", help="versions, and whether a key is accepted by the licence server"
    )
    doctor.add_argument("--offline", action="store_true", help="do not contact the licence server")
    _add_licence(doctor)
    _add_json(doctor)
    doctor.set_defaults(func=cmd_doctor)

    version = commands.add_parser("version", help="print the SDK and engine versions")
    _add_json(version)
    version.set_defaults(func=cmd_version)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "json"):
        args.json = False
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
