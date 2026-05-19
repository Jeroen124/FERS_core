"""
Run all FERS examples and report pass/fail.

Usage:
    python run_examples.py              # run all examples (skips 1xx and 9xx)
    python run_examples.py --skip-visual  # skip 1xx visual and 9xx experimental examples (default)
    python run_examples.py --all          # include visual and experimental examples
"""

import argparse
import os
import re
import subprocess
import sys
import time

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "examples")

# Examples that open interactive windows or require external services / files
SKIP_ALWAYS = {
    "806_Cloud_Save_Load.py",
    "803_DXF_Cross_Section_Import.py",
}

VISUAL_PATTERN = re.compile(r"^[19]\d{2}_")  # 1xx and 9xx series


def collect_examples(include_visual: bool) -> list[str]:
    files = sorted(f for f in os.listdir(EXAMPLES_DIR) if f.endswith(".py") and re.match(r"^\d", f))
    result = []
    for f in files:
        if f in SKIP_ALWAYS:
            continue
        if not include_visual and VISUAL_PATTERN.match(f):
            continue
        result.append(f)
    return result


def run_example(filename: str) -> tuple[bool, float, str]:
    path = os.path.join(EXAMPLES_DIR, filename)
    start = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=os.path.join(EXAMPLES_DIR, "json_input_solver", ".."),  # examples dir
        env=env,
    )
    elapsed = time.perf_counter() - start
    ok = proc.returncode == 0
    output = proc.stderr.strip() if not ok else ""
    return ok, elapsed, output


def main():
    parser = argparse.ArgumentParser(description="Run FERS examples")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--skip-visual",
        action="store_true",
        default=True,
        help="Skip 1xx visual and 9xx experimental examples (default)",
    )
    group.add_argument(
        "--all", dest="include_visual", action="store_true", help="Include visual and experimental examples"
    )
    args = parser.parse_args()
    include_visual = args.include_visual

    examples = collect_examples(include_visual)
    total = len(examples)
    passed = 0
    failed = []

    print(f"Running {total} examples{'  (visual/experimental skipped)' if not include_visual else ''}...\n")
    print(f"{'Example':<55} {'Status':<8} {'Time':>6}")
    print("-" * 72)

    for filename in examples:
        ok, elapsed, err = run_example(filename)
        status = "PASS" if ok else "FAIL"
        print(f"{filename:<55} {status:<8} {elapsed:>5.1f}s")
        if ok:
            passed += 1
        else:
            failed.append((filename, err))

    print("-" * 72)
    print(f"\nResults: {passed}/{total} passed")

    if failed:
        print("\nFailed examples:")
        for fname, err in failed:
            print(f"\n  {fname}")
            if err:
                for line in err.splitlines()[-10:]:
                    print(f"    {line}")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
