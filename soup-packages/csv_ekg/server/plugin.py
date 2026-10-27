"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the "CSV come event log" importer and the
             "Converti in EKG" operation (table -> ekg). Name, version and
             dependencies come from soup-package.json.
Project : soup-packages/csv_ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin

from .contributions import CsvEkgImporter, TableToEkg


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_importer(CsvEkgImporter())
        ctx.add_operation(TableToEkg())
