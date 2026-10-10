"""Loading a result must cost a small multiple of the file's size, not many times it.

An integrator's nightly was killed for memory while loading an 81.5 MB result: the
loader peaked at about 14 times the file. Each case here loads a generated file of
that shape in a fresh process and holds the peak growth to under 3 times the file;
the streamed loader measures well under 1.
"""

import importlib.util
import json
import os
import subprocess
import sys

import pytest

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "make_synthetic_result.py")

_PROBE = r"""
import gc, json, sys

def resident_and_peak():
    if sys.platform.startswith("linux"):
        with open("/proc/self/status") as f:
            fields = dict(line.split(":", 1) for line in f if ":" in line)
        return int(fields["VmRSS"].split()[0]) * 1024, int(fields["VmHWM"].split()[0]) * 1024
    try:
        import psutil
    except ImportError:
        return None, None
    info = psutil.Process().memory_info()
    return info.rss, getattr(info, "peak_wset", None)

from fers_core import FERS

gc.collect()
if sys.platform.startswith("linux"):
    try:
        with open("/proc/self/clear_refs", "w") as f:
            f.write("5")  # resets the peak to the current resident size
    except OSError:
        pass
before, _ = resident_and_peak()
model = FERS.from_json(sys.argv[1])
_, peak = resident_and_peak()
print(json.dumps(None if before is None or peak is None else peak - before))
"""


def _generator():
    spec = importlib.util.spec_from_file_location("make_synthetic_result", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "shape",
    [
        {"nodes": 1000, "members": 1200, "combinations": 25},
        # One large combination: decoding a combination whole would fail here.
        {"nodes": 9000, "members": 9900, "combinations": 1},
    ],
    ids=["many_combinations", "one_combination"],
)
def test_loading_peaks_well_under_three_times_the_file(tmp_path, shape):
    path = tmp_path / "result.json"
    size = _generator().write_synthetic_result(str(path), **shape)
    out = subprocess.run(
        [sys.executable, "-c", _PROBE, str(path)], capture_output=True, text=True, cwd=str(tmp_path)
    )
    assert out.returncode == 0, out.stderr
    growth = json.loads(out.stdout.strip().splitlines()[-1])
    if growth is None:
        pytest.skip("no way to read the peak resident size on this platform (install psutil)")
    assert growth < 3 * size, f"load peaked at {growth / size:.2f}x the {size / 1e6:.1f} MB file"
