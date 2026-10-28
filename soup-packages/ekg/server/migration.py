"""
------------------------------------------------------------------------
File : migration.py
Description: The migration of the volumes of the old interface, in one
             module: run_migration() is all the Plugin calls at startup.
             It is idempotent and runs at every start (a dataset folder
             copied onto the volume later is adopted too).
             adopt_legacy_datasets - the datasets already on the volume
             (/soup/<name>/ with a <name>_config.json, built by the old
             pages or by /api/v2/graph before commit 8) become "ekg"
             objects of the catalog, created_by the csv_ekg importer (the
             one that disposes of them), with the meta read from the
             config and a new graph key (meta.graph_key). A folder that
             already has an "ekg" object (same meta.dataset) is skipped,
             so running it again adds nothing;
             a folder whose config cannot be read is logged and skipped.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from soup.core.contracts import CREATED_BY_IMPORTER, Catalog, CreatedBy, ObjectRef, validate_name

from .builder import EKG_KIND, STORAGE, meta_from_config
from .dataset_repository import DatasetRepository
from .process_timer import DATE_FORMAT
from .state import CATALOG, is_derived

_LOGGER = logging.getLogger("soup.ekg")

# The importer that creates "ekg" objects from CSV files (csv_ekg, which
# requires this package: a key, not an import).
LEGACY_PACKAGE = "csv_ekg"
LEGACY_IMPORTER = f"{LEGACY_PACKAGE}.csv"


def adopt_legacy_datasets(tools: Any, clock: Callable[[], datetime] = datetime.now) -> list[ObjectRef]:
    """Register the datasets not yet in the catalog; return the objects added."""

    catalog = tools.typed(CATALOG, Catalog)
    repository = DatasetRepository(tools.get(STORAGE))
    known = {obj.meta.get("dataset") for obj in catalog.list() if obj.kind == EKG_KIND and not is_derived(obj)}

    adopted = []
    for name in repository.datasets():
        if name in known:
            continue
        try:
            config = repository.load_config(name)
            description = config.get("dataset_description") or ""
            obj = ObjectRef(
                id=str(uuid.uuid4()),
                name=validate_name(name),
                kind=EKG_KIND,
                created_by=CreatedBy(CREATED_BY_IMPORTER, LEGACY_IMPORTER, LEGACY_PACKAGE),
                created_at=str(config.get("date_created") or clock().strftime(DATE_FORMAT)[:-3]),
                description=description if isinstance(description, str) else "",
                meta=meta_from_config(name, config),
            )
            catalog.add(obj)
        except Exception:  # noqa: BLE001 - one broken folder must not stop the others
            _LOGGER.exception("Dataset '%s' could not be added to the catalog", name)
            continue
        adopted.append(obj)
    return adopted


def run_migration(tools: Any) -> list[ObjectRef]:
    """
    Adopt the datasets already on the volume; a failure (e.g. storage
    unreachable) is logged and does not stop the package.
    """

    try:
        adopted = adopt_legacy_datasets(tools)
    except Exception as exc:  # noqa: BLE001 - the package works without the old datasets
        _LOGGER.warning("The datasets already on the volume were not added to the catalog: %s", exc)
        return []
    if adopted:
        _LOGGER.info("Added %d dataset(s) already on the volume to the catalog", len(adopted))
    return adopted
