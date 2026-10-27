"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - opens the "ekg.build_steps" and
             "ekg.state_providers" extension points, activates the
             EkgRuntime used by api.py, registers the "load" operation and
             adds the datasets already on the volume to the catalog
             (adoption.py). A failed adoption (e.g. storage unreachable)
             is logged and does not stop the package. Name, version and
             dependencies come from soup-package.json.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from typing import Optional

from soup.core.contracts import PluginContext, SoupPlugin

from .adoption import adopt_legacy_datasets
from .operations import LoadEkg
from .runtime import BUILD_STEPS_POINT, STATE_PROVIDERS_POINT, EkgRuntime, activate, deactivate

_LOGGER = logging.getLogger("soup.ekg")


class Plugin(SoupPlugin):
    runtime: Optional[EkgRuntime] = None

    def register(self, ctx: PluginContext) -> None:
        ctx.add_extension_point(BUILD_STEPS_POINT)
        ctx.add_extension_point(STATE_PROVIDERS_POINT)
        ctx.add_operation(LoadEkg())
        self.runtime = EkgRuntime(ctx)
        activate(self.runtime)
        try:
            adopted = adopt_legacy_datasets(self.runtime.tools)
        except Exception as exc:  # noqa: BLE001 - the package works without the old datasets
            _LOGGER.warning("The datasets already on the volume were not added to the catalog: %s", exc)
        else:
            if adopted:
                _LOGGER.info("Added %d dataset(s) already on the volume to the catalog", len(adopted))

    def on_shutdown(self, ctx: PluginContext) -> None:
        if self.runtime is not None:
            deactivate(self.runtime)
            self.runtime = None
