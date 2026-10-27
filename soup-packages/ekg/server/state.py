"""
------------------------------------------------------------------------
File : state.py
Description: The graph state of "ekg" objects. Memgraph holds one graph
             at a time; the memgraph tool's state key is the object's
             graph key (graph_key_of): meta.graph_key for a root object
             (set by build_ekg and by the adoption, kept by every
             rebuild), its id for a derived object or one without a key.
             A root "ekg" object (an import, a conversion)
             is a staged dataset (meta.dataset). A derived "ekg" object
             (e.g. an analysis) declares meta.state = {provider, spec}
             and lists its "ekg" parent among its parents: the provider,
             contributed to "ekg.state_providers" by some package, knows
             how to apply `spec` to the graph of the parent.
             - ensure_loaded(obj, tools, force=False): if obj is not the
               active state (or with force), publish "ekg.before_reset",
               then the loader rebuilds the root's dataset (build steps,
               counts and process times saved in its config like the
               legacy /complete-graph/build did) and applies, in order,
               the states of the derived objects from the root down to
               obj.
             - dispose(obj, tools): if obj is active, "ekg.before_reset"
               and the graph is emptied; a root's files are removed.
             `tools` are the caller's: it must declare "memgraph" and
             "storage". The parents are read from the catalog with this
             package's own tools.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from soup.core.contracts import Catalog, GraphDatabase, NotFoundError, ObjectRef, ValidationError

from .builder import (
    EKG_BEFORE_RESET,
    EKG_BUILT,
    EKG_KIND,
    MEMGRAPH,
    STORAGE,
    RunDatabase,
    build_context,
)
from .dataset_repository import DatasetRepository
from .ekg_service import EkgService
from .process_timer import ProcessTimer
from .runtime import current

CATALOG = "catalog"


class StateProvider(ABC):
    """
    Contributed to "ekg.state_providers" (contribution key = `key`). A
    derived "ekg" object with meta.state = {"provider": key, "spec": ...}
    is loaded by applying `spec` to the graph of its parent.
    """

    key: str = ""

    @abstractmethod
    def apply(self, spec: Mapping[str, Any], db: GraphDatabase) -> None:
        raise NotImplementedError


def is_derived(obj: ObjectRef) -> bool:
    return isinstance(obj.meta.get("state"), Mapping)


def graph_key_of(obj: ObjectRef) -> str:
    """The memgraph tool state of obj's graph: meta.graph_key, else (derived, or no key) its id."""

    key = obj.meta.get("graph_key")
    if is_derived(obj) or not isinstance(key, str) or not key:
        return obj.id
    return key


def chain_of(obj: ObjectRef, catalog: Catalog) -> list[ObjectRef]:
    """[root, ..., obj]: obj and its "ekg" ancestors up to the first one that is not derived."""

    if obj.kind != EKG_KIND:
        raise ValidationError(f"Object '{obj.name}' is a {obj.kind!r}, not an EKG")
    chain = [obj]
    while is_derived(chain[-1]):
        current_obj = chain[-1]
        parent = None
        for parent_id in current_obj.parents:
            candidate = catalog.get(parent_id)
            if candidate is not None and candidate.kind == EKG_KIND:
                parent = candidate
                break
        if parent is None:
            raise NotFoundError(f"EKG object '{current_obj.name}' has no EKG parent to apply its state to")
        if any(item.id == parent.id for item in chain):
            raise ValidationError(f"EKG object '{current_obj.name}' has a cycle in its parents")
        chain.append(parent)
    chain.reverse()
    if not chain[0].meta.get("dataset"):
        raise NotFoundError(f"EKG object '{chain[0].name}' has no dataset")
    return chain


def ensure_loaded(obj: ObjectRef, tools: Any, force: bool = False) -> bool:
    """
    Make `obj` the graph in Memgraph. Returns True if it was (re)built,
    False if it was already the active state.
    """

    runtime = current()
    memgraph = tools.get(MEMGRAPH)
    chain = chain_of(obj, runtime.tools.typed(CATALOG, Catalog))
    graph_key = graph_key_of(obj)
    if not force and memgraph.current_state() == graph_key:
        return False

    root = chain[0]
    dataset = root.meta["dataset"]
    repository = DatasetRepository(tools.get(STORAGE))
    providers = [(runtime.state_provider(item.meta["state"].get("provider", "")), item) for item in chain[1:]]
    config = repository.load_config(dataset)
    ctx = build_context(repository, dataset, config)
    counts: dict[str, int] = {}
    times: dict[str, str] = {}

    def loader(run) -> None:
        db = RunDatabase(run)
        service = EkgService(db, runtime.build_steps)
        service.build(ctx, times)
        counts.update(service.counts())
        for provider, item in providers:
            provider.apply(item.meta["state"].get("spec") or {}, db)

    runtime.publish(EKG_BEFORE_RESET, {"object": obj.id, "active": memgraph.current_state(), "reason": "load"})
    with ProcessTimer() as timer:
        loaded = memgraph.ensure_loaded(graph_key, loader, force=force)
    if not loaded:
        return False

    # Like the legacy /complete-graph/build: the counts and the times of
    # the last build of the dataset go back into its config.
    config.update(counts)
    process_info = dict(config.get("process_info") or {})
    process_info.update(times)
    process_info["init_time"] = timer.started_at
    process_info["finish_time"] = timer.finished_at
    config["process_info"] = process_info
    repository.save_config(dataset, config)

    runtime.publish(EKG_BUILT, {"object": obj.id, "graph_key": graph_key, "dataset": dataset, "counts": dict(counts)})
    return True


def dispose(obj: ObjectRef, tools: Any) -> None:
    """
    Remove what an "ekg" object holds: the graph if it is the active
    state, and the dataset files of a root. Tolerates partial state (a
    failed import has empty meta).
    """

    runtime = current()
    memgraph = tools.get(MEMGRAPH)
    graph_key = graph_key_of(obj)
    if memgraph.current_state() == graph_key:
        runtime.publish(EKG_BEFORE_RESET, {"object": None, "active": graph_key, "reason": "dispose"})
        memgraph.clear()
    dataset = obj.meta.get("dataset")
    if dataset and not is_derived(obj):
        DatasetRepository(tools.get(STORAGE)).delete(dataset)
