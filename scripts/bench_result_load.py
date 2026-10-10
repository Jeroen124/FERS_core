"""Measure the memory and time it takes to load a result file.

Each run is a fresh interpreter, so the peak belongs to that load alone. The
figure reported is the one an integrator's report used: peak working set
(Windows) or max RSS (Linux), minus the resident size just before the load,
divided by the file size. Run it with the interpreter whose ``fers_core`` you
want to measure::

    python scripts/bench_result_load.py result.json --runs 3
    python scripts/bench_result_load.py result.json --mode string --touch
    path/to/other/venv/python scripts/bench_result_load.py result.json

``--mode string`` measures the path ``run_analysis`` takes: the engine hands back
the whole result as one string, which is read first and not counted. ``--touch``
also times one read of every member's and node's results after the load.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_PROBE = r"""
import gc, json, sys, time
import psutil

path, mode, touch = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
proc = psutil.Process()


def peak():
    info = proc.memory_info()
    if hasattr(info, "peak_wset"):
        return info.peak_wset
    import resource
    scale = 1 if sys.platform == "darwin" else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale


from fers_core import FERS

text = None
if mode == "string":
    with open(path, encoding="utf-8") as f:
        text = f.read()


def load_string(text):
    try:
        from fers_core.results._loader import results_from_engine_output
    except ImportError:
        # Before the streaming loader: what run_analysis did with the string.
        import ujson
        from fers_core.results.resultsbundle import ResultsBundle
        from fers_core.types.pydantic_models import ResultsBundle as Schema

        return ResultsBundle.from_pydantic(Schema(**ujson.loads(text)["results"]))
    return results_from_engine_output(text)


gc.collect()
rss0, peak0 = proc.memory_info().rss, peak()
t0 = time.perf_counter()
bundle = FERS.from_json(path).resultsbundle if mode == "file" else load_string(text)
load_s = time.perf_counter() - t0
peak1, rss1 = peak(), proc.memory_info().rss

touch_s = None
if touch:
    t1 = time.perf_counter()
    total = 0.0
    for group in (bundle.loadcases, bundle.loadcombinations):
        for single in group.values():
            for result in single.member_results.values():
                total += result.local_maximums.my + result.local_start_forces.fx
                total += result.local_displacement_end_node.dz
            for disp in single.displacement_nodes.values():
                total += disp.dy
    touch_s = time.perf_counter() - t1

print(json.dumps({"rss0": rss0, "peak0": peak0, "peak1": peak1, "rss1": rss1,
                  "load_s": load_s, "touch_s": touch_s}))
"""


def run_once(python: str, path: str, mode: str, touch: bool) -> dict:
    # Run outside the repo: a FERS.egg-info there makes importlib.metadata report a
    # version that is not installed.
    out = subprocess.run(
        [python, "-c", _PROBE, os.path.abspath(path), mode, "1" if touch else "0"],
        capture_output=True,
        text=True,
        cwd=os.path.expanduser("~"),
    )
    if out.returncode:
        raise SystemExit(f"load of {path} failed:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--mode", choices=("file", "string"), default="file")
    parser.add_argument("--touch", action="store_true")
    args = parser.parse_args()

    mb = 1e6
    for path in args.paths:
        size = os.path.getsize(path)
        runs = [run_once(args.python, path, args.mode, args.touch) for _ in range(args.runs)]
        peak = max(r["peak1"] - r["rss0"] for r in runs)
        resident = max(r["rss1"] - r["rss0"] for r in runs)
        import_peak_hid_it = any(r["peak1"] == r["peak0"] for r in runs)
        line = (
            f"{os.path.basename(path)}  {size / mb:.1f} MB  mode={args.mode}  "
            f"baseline {runs[0]['rss0'] / mb:.0f} MB  "
            f"peak +{peak / mb:.0f} MB = {peak / size:.2f}x  "
            f"resident +{resident / mb:.0f} MB = {resident / size:.2f}x  "
            f"load {max(r['load_s'] for r in runs):.2f} s"
        )
        if args.touch:
            line += f"  read-all {max(r['touch_s'] for r in runs):.2f} s"
        if import_peak_hid_it:
            line += "  (load never exceeded the import peak: peak figure is an upper bound)"
        print(line, flush=True)


if __name__ == "__main__":
    main()
