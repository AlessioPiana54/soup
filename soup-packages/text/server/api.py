"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the text package. Other packages import it as
             soup_pkg_text.api, and only if they list "text" in their
             `requires`: the contributions (built on a ParsedCache of
             their own, or on the one given) and the cache of the decoded
             files.
Project : soup-packages/text
------------------------------------------------------------------------
"""

from .cache import DEFAULT_MAX_BYTES, DEFAULT_MAX_OBJECTS, ParsedCache, limits_from_env
from .text import OriginalFileExporter, TextFile, TextImporter, TextVisualizer, decode, extension_of, new_cache, stored_extension

__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_OBJECTS",
    "OriginalFileExporter",
    "ParsedCache",
    "TextFile",
    "TextImporter",
    "TextVisualizer",
    "decode",
    "extension_of",
    "limits_from_env",
    "new_cache",
    "stored_extension",
]
