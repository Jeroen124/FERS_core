"""Optional dependencies: plotting, section design and DXF import.

The solver needs only numpy, pydantic, ujson and the engine. Everything else is an
extra, so an agent's sandbox installs FERS in ~30 MB instead of ~257 MB (VTK alone
is 140 MB). These helpers import an extra where it is used and, when it is
missing, name the extra that provides it.
"""

import importlib
from types import ModuleType
from typing import Any


def require(module: str, extra: str) -> ModuleType:
    """Import an optional dependency, or explain which extra installs it."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ImportError(
            f"{module.split('.')[0]} is needed for this and is not installed. "
            f'Install it with: pip install "FERS[{extra}]" (or "FERS[all]" for every extra).'
        ) from exc


class _LazyModule:
    """Stands in for a module until an attribute is first used."""

    def __init__(self, module: str, extra: str):
        self._lazy_name = module
        self._lazy_extra = extra
        self._lazy_module: ModuleType | None = None

    def __getattr__(self, attr: str) -> Any:
        if self._lazy_module is None:
            self._lazy_module = require(self._lazy_name, self._lazy_extra)
        return getattr(self._lazy_module, attr)


def lazy(module: str, extra: str) -> Any:
    """A module-level name that imports `module` on first use: `plt = lazy("matplotlib.pyplot", "plot")`."""
    return _LazyModule(module, extra)
