"""Renderer and runtime implementations for :mod:`badge_sdk` applications.

Application authors should import from ``badge_sdk``.  This package is the
launcher-owned implementation layer and may evolve without changing the public
app contract.
"""

from .application_runtime import ApplicationRuntime
from .renderer import Renderer

__all__ = ["ApplicationRuntime", "Renderer"]
