"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the csv_ekg package. Other packages import it
             as soup_pkg_csv_ekg.api, and only if they list "csv_ekg" in
             their `requires`: the CSV reader, the multiplicities between
             entity columns and the contributions.
Project : soup-packages/csv_ekg
------------------------------------------------------------------------
"""

from .contributions import CsvEkgImporter, TableToEkg, mapping_fields, parse_options
from .multiplicity import multiplicity, multiplicity_block
from .reader import FORMAT_ID, read_csv

__all__ = [
    "FORMAT_ID",
    "CsvEkgImporter",
    "TableToEkg",
    "mapping_fields",
    "multiplicity",
    "multiplicity_block",
    "parse_options",
    "read_csv",
]
