"""
------------------------------------------------------------------------
File : operations.py
Description: LoadEkg ("load") - "Carica in Memgraph": makes an "ekg"
             object the graph in Memgraph (ensure_loaded), rebuilding it
             only if another one is active, or always with "force". It
             produces no object. The /api/v2 route that rebuilt the graph
             of a dataset (/complete-graph/build) runs it with force.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Mapping

from soup.core.contracts import Field, ObjectDraft, ObjectRef, Operation, OperationInput

from .builder import EKG_KIND, MEMGRAPH, STORAGE
from .state import ensure_loaded


class LoadEkg(Operation):
    id = "load"
    label = "Carica in Memgraph"
    description = "Loads the EKG into Memgraph, rebuilding it from its dataset if another graph is loaded."
    group = "EKG"
    inputs = (OperationInput("ekg", (EKG_KIND,)),)
    produces = (EKG_KIND,)
    requires_tools = (MEMGRAPH, STORAGE)

    def fields(self, inputs: Mapping[str, ObjectRef], tools) -> list[Field]:
        return [Field("force", "Ricostruisci comunque", type="bool", default=False,
                      help="Ricostruisce il grafo anche se è già quello caricato.")]

    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools) -> list[ObjectDraft]:
        ensure_loaded(inputs["ekg"], tools, force=bool(params.get("force")))
        return []
