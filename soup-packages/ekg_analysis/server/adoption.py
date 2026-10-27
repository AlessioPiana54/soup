"""
------------------------------------------------------------------------
File : adoption.py
Description: adopt_legacy_analyses - the analyses already on the volume
             (<dataset>/Analyses/<name>.json, saved by the old pages, by
             /api/v2/analyses/new or by "Nuova analisi") become "ekg"
             objects derived from their parent (the ekg package adds the
             datasets to the catalog first: ekg_analysis requires it).
             The parent is the root "ekg" object of the dataset, or, for a
             file with "based_on" (a nested analysis), the analysis of
             that name: the files are adopted in topological order, the
             ones without based_on first, then their children. A based_on
             that names no analysis of the dataset, or a cycle, adopts the
             analysis under the root with meta.warning (and meta.notice,
             shown by the visualizers) and a warning in the log - never
             silently on the wrong parent.
             created_by is the operation "ekg_analysis.new" (the one that
             disposes of them), meta.state the analysis read from the file
             (strict=False: a filter of another package, not contributed
             yet at startup, is kept as it is), meta.analysis the file,
             no graph key (the first opening rebuilds and applies the
             chain). A file that already has an object (same
             meta.analysis) is skipped but is still a parent for the
             others, so running it again adds nothing; a file that cannot
             be read, or whose name is not a valid object name, is logged
             and skipped. The Plugin runs it at startup.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence

from soup.core.contracts import CREATED_BY_OPERATION, Catalog, CreatedBy, ObjectRef, contribution_key
import soup_pkg_ekg.api as ekg

from .analysis import ANALYSIS_PROVIDER, Analysis, analysis_file
from .filters import AnalysisFilter
from .service import STORAGE

_LOGGER = logging.getLogger("soup.ekg_analysis")

PACKAGE = "ekg_analysis"
CATALOG = "catalog"
CREATOR = contribution_key(PACKAGE, "new")
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


def _based_on(content: Mapping[str, Any]) -> Optional[str]:
    value = content.get("based_on")
    return value if isinstance(value, str) and value else None


def adopt_legacy_analyses(tools: Any, filters: Sequence[AnalysisFilter],
                          clock: Callable[[], datetime] = datetime.now) -> list[ObjectRef]:
    """Register the analyses on the volume not yet in the catalog; return the objects added."""

    catalog = tools.typed(CATALOG, Catalog)
    repository = ekg.DatasetRepository(tools.get(STORAGE))
    objects = catalog.list()
    roots = {obj.meta["dataset"]: obj for obj in objects
             if obj.kind == ekg.EKG_KIND and not ekg.is_derived(obj) and obj.meta.get("dataset")}
    known: dict[tuple[str, str], ObjectRef] = {}
    for obj in objects:
        found = analysis_file(obj)
        if found is not None:
            known.setdefault(found, obj)

    adopted: list[ObjectRef] = []
    for dataset, root in sorted(roots.items()):
        try:
            names = repository.analyses(dataset)
        except Exception:  # noqa: BLE001 - one unreadable dataset must not stop the others
            _LOGGER.exception("The analyses of the dataset '%s' could not be listed", dataset)
            continue
        objects_by_name = {name: obj for (folder, name), obj in known.items() if folder == dataset}
        pending: dict[str, Mapping[str, Any]] = {}
        for name in names:
            if name in objects_by_name:
                continue
            try:
                content = repository.load_analysis(dataset, name)
            except Exception:  # noqa: BLE001 - one broken file must not stop the others
                _LOGGER.exception("Analysis '%s' of the dataset '%s' could not be read", name, dataset)
                continue
            pending[name] = content if isinstance(content, Mapping) else {}

        def adopt(name: str, parent: ObjectRef, based_on: Optional[str], warning: Optional[str]) -> None:
            obj = _adopt(catalog, dataset, name, pending.pop(name), parent, based_on, warning, filters, clock)
            if obj is not None:
                objects_by_name[name] = obj
                adopted.append(obj)

        # Topological order: an analysis waits for the one it is based on.
        progress = True
        while pending and progress:
            progress = False
            for name in sorted(pending):
                based_on = _based_on(pending[name])
                if based_on is None:
                    adopt(name, root, None, None)
                elif based_on in objects_by_name:
                    adopt(name, objects_by_name[based_on], based_on, None)
                elif based_on not in pending:
                    adopt(name, root, None, f"The analysis it is based on, '{based_on}', was not found: "
                                            "it was added under the dataset, without its filters.")
                else:
                    continue
                progress = True
        for name in sorted(pending):
            adopt(name, root, None, f"Its chain of 'based_on' is a cycle ('{_based_on(pending[name])}'): "
                                    "it was added under the dataset, without the filters of the chain.")
    return adopted


def _adopt(catalog: Catalog, dataset: str, name: str, content: Mapping[str, Any], parent: ObjectRef,
           based_on: Optional[str], warning: Optional[str], filters: Sequence[AnalysisFilter],
           clock: Callable[[], datetime]) -> Optional[ObjectRef]:
    try:
        analysis = Analysis.from_legacy(name, content, filters, strict=False)
        info: dict[str, Any] = {"dataset": dataset, "name": name}
        if based_on:
            info["based_on"] = based_on
        meta: dict[str, Any] = {"state": {"provider": ANALYSIS_PROVIDER, "spec": analysis.to_spec()}, "analysis": info}
        if warning:
            meta["warning"] = meta["notice"] = warning
        obj = ObjectRef(
            id=str(uuid.uuid4()),
            name=analysis.name,
            kind=ekg.EKG_KIND,
            created_by=CreatedBy(CREATED_BY_OPERATION, CREATOR, PACKAGE),
            parents=(parent.id,),
            created_at=clock().strftime(DATE_FORMAT)[:-3],
            description=analysis.description,
            meta=meta,
        )
        catalog.add(obj)
    except Exception:  # noqa: BLE001 - one broken file must not stop the others
        _LOGGER.exception("Analysis '%s' of the dataset '%s' could not be added to the catalog", name, dataset)
        return None
    if warning:
        _LOGGER.warning("Analysis '%s' of the dataset '%s': %s", name, dataset, warning)
    return obj
