"""
causal_df - built-in plugin adding the causal :DF build step (order 450).
Not active by default (unlike csv_reader): add "causal_df" to
Settings.plugins/SOUP_PLUGINS to enable it.
"""

from soup.plugins.causal_df.plugin import CausalDfPlugin
from soup.plugins.causal_df.step import CausalDirectlyFollowsStep

PLUGIN = CausalDfPlugin()

__all__ = ["CausalDfPlugin", "CausalDirectlyFollowsStep", "PLUGIN"]
