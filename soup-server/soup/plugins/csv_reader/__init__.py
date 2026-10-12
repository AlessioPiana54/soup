"""
csv_reader - built-in plugin reading flat CSV event logs. `PLUGIN` is the
instance PluginManager resolves when "csv_reader" is listed in
SOUP_PLUGINS/Settings.plugins.
"""

from soup.plugins.csv_reader.plugin import CsvReaderPlugin
from soup.plugins.csv_reader.reader import CsvEventLogReader

PLUGIN = CsvReaderPlugin()

__all__ = ["CsvReaderPlugin", "CsvEventLogReader", "PLUGIN"]
