"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - opens the "ekg.analysis_filters" extension point
             and contributes to it the six filters of filters.py (order
             100-600), contributes the "analysis" state provider to
             "ekg.state_providers", registers the operations "Nuova
             analisi", "Importa configurazione di analisi" and "Esempio di
             configurazione", the "Indicatori di processo" visualizer and
             the "Configurazione dell'analisi" exporter, then adds the
             analyses already on the volume to the catalog (adoption.py).
             A failed adoption (e.g. storage unreachable) is logged and
             does not stop the package. Name, version and dependencies
             come from soup-package.json.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging

from soup.core.contracts import PluginContext, SoupPlugin
import soup_pkg_ekg.api as ekg

from .adoption import adopt_legacy_analyses
from .exporter import AnalysisConfigExporter
from .filters import builtin_filters
from .insights import InsightsVisualizer
from .operations import ExampleConfiguration, ImportAnalysis, NewAnalysis
from .provider import AnalysisStateProvider
from .service import ANALYSIS_FILTERS_POINT, AnalysisRuntime, AnalysisService

_LOGGER = logging.getLogger("soup.ekg_analysis")


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_extension_point(ANALYSIS_FILTERS_POINT)
        for item in builtin_filters():
            ctx.contribute(ANALYSIS_FILTERS_POINT, item, key=item.key, order=item.order)

        runtime = AnalysisRuntime(ctx)
        provider = AnalysisStateProvider(runtime.filters)
        ctx.contribute(ekg.STATE_PROVIDERS_POINT, provider, key=provider.key)

        service = AnalysisService(runtime)
        ctx.add_operation(NewAnalysis(runtime, service))
        ctx.add_operation(ImportAnalysis(runtime, service))
        ctx.add_operation(ExampleConfiguration(runtime))
        ctx.add_visualizer(InsightsVisualizer())
        ctx.add_exporter(AnalysisConfigExporter())

        try:
            adopted = adopt_legacy_analyses(ctx.tools, runtime.filters())
        except Exception as exc:  # noqa: BLE001 - the package works without the old analyses
            _LOGGER.warning("The analyses already on the volume were not added to the catalog: %s", exc)
        else:
            if adopted:
                _LOGGER.info("Added %d analysis(es) already on the volume to the catalog", len(adopted))
