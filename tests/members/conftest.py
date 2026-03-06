"""
conftest.py for tests/members/
================================
Stubs out optional heavy dependencies that are not installed in the
test environment (fers_calculations, ujson, pyvista) so that the
geometric / material unit tests can be collected and run without a
full solver installation.

This hook runs during pytest_configure, which is early enough that the
stubs are in sys.modules before any test module is imported.
"""

import sys
import types


def pytest_configure(config):
    _stub("fers_calculations")
    _stub("ujson")
    pv = _stub("pyvista")
    pv.PolyData = object  # prevent AttributeError in fers.py


def _stub(name: str) -> types.ModuleType:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
    return sys.modules[name]
