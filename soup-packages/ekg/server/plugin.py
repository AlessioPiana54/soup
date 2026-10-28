"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - opens the "ekg.build_steps" and
             "ekg.state_providers" extension points, activates the
             EkgRuntime used by api.py, registers the "load" operation and
             adds the datasets already on the volume to the catalog
             (migration.py). A failed adoption (e.g. storage unreachable)
             is logged and does not stop the package. Name, version and
             dependencies come from soup-package.json.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin

from .migration import run_migration
from .operations import LoadEkg
from .runtime import BUILD_STEPS_POINT, STATE_PROVIDERS_POINT, EkgRuntime, activate, deactivate


class Plugin(SoupPlugin):
    runtime: EkgRuntime | None = None

    def register(self, ctx: PluginContext) -> None:
        ctx.add_extension_point(BUILD_STEPS_POINT)
        ctx.add_extension_point(STATE_PROVIDERS_POINT)
        ctx.add_operation(LoadEkg())
        self.runtime = EkgRuntime(ctx)
        activate(self.runtime)
        run_migration(self.runtime.tools)

    def on_shutdown(self, ctx: PluginContext) -> None:
        if self.runtime is not None:
            deactivate(self.runtime)
            self.runtime = None
