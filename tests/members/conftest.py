"""
conftest.py for tests/members/
================================
Stubs out optional heavy dependencies that are not installed in the
test environment (fers_calculations, ujson, pyvista) so that the
geometric / material unit tests can be collected and run without a
full solver installation.

This hook runs during pytest_configure, which is early enough that the
stubs are in sys.modules before any test module is imported.

A stub is installed only where the real package cannot be imported. The
`not in sys.modules` guard alone is not enough: at pytest_configure time
nothing has imported these yet, so an unconditional stub would win even on
a machine that has the real thing, and would then stay in sys.modules for
the rest of the session - poisoning every later test that does need to
solve. That is what made `pytest tests/members tests/functionality` fail
with `module 'ujson' has no attribute 'dumps'` while either directory
passed on its own.
"""

import importlib
import sys
import types


def pytest_configure(config):
    _stub("fers_calculations")
    _stub("ujson")
    pv = _stub("pyvista")
    if pv is not None:
        pv.PolyData = object  # prevent AttributeError in fers.py


def _stub(name: str) -> types.ModuleType | None:
    """Install an empty module under `name`, unless the real one is importable.

    Returns the stub, or None when the real package is present and was left
    alone.
    """
    if name in sys.modules:
        return None
    try:
        importlib.import_module(name)
    except ImportError:
        sys.modules[name] = types.ModuleType(name)
        return sys.modules[name]
    return None
