"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the server part of soup_base. Other packages
             import it as soup_pkg_soup_base.api, and only if they list
             "soup_base" in their `requires`: ParsedCache, the LRU cache
             of the parsed contents, and limits_from_env.
Project : soup-packages/soup_base
------------------------------------------------------------------------
"""

from .cache import DEFAULT_MAX_BYTES, DEFAULT_MAX_OBJECTS, ParsedCache, limits_from_env

__all__ = ["DEFAULT_MAX_BYTES", "DEFAULT_MAX_OBJECTS", "ParsedCache", "limits_from_env"]
