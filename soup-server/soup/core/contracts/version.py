"""
------------------------------------------------------------------------
File : version.py
Description: Version of the stable contracts exposed by the host to
             plugins. Plugins declare the contracts version they were
             built against (SoupPlugin.api_version); the PluginManager
             refuses to load a plugin whose declared version does not
             match this one.
Project : soup-server
------------------------------------------------------------------------
"""

CONTRACTS_API_VERSION = "2.0"
