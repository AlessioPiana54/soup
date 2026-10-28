"""
------------------------------------------------------------------------
File : operations.py
Description: The operations of ekg_analysis on "ekg" objects:
             - NewAnalysis ("new", "Nuova analisi"; the sidebar of the
               filters and createAnalysis of details-dataset): the fields
               "name" and "filters", an "items" field with one variant per
               AnalysisFilter contributed by any package (its fields read
               from the graph of the object). It produces a derived "ekg"
               object: parents = the input, meta.state = {provider:
               "analysis", spec}, meta.graph_key (the analysis stays the
               loaded graph), meta.analysis = {dataset, name, based_on?}
               (the file in <dataset>/Analyses/; based_on is the name of
               the input when it is an analysis too), meta.counts {before, after} and
               meta.result "changed" or "unchanged" (with meta.notice,
               shown by the visualizers);
             - ImportAnalysis ("import", "Importa configurazione di
               analisi"; uploadJson + parseAndValidateJson): a JSON file in
               the legacy format, validated filter by filter, then as
               NewAnalysis;
             - ExampleConfiguration ("example", "Esempio di
               configurazione"; getExampleJSON and
               help/file_configuration_example.json): a "report" with a
               markdown block that explains every key and a "file" block
               with an example built on the entity types, the activities
               and the time range of the object.
             Deleting an analysis object (dispose) removes its graph if it
             is active and its file - otherwise the file would come back
             as an object at the next start (migration.py).
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import soup_pkg_ekg.api as ekg

from soup.core.contracts import (
    REPORT,
    Field,
    ObjectDraft,
    ObjectRef,
    Operation,
    OperationInput,
    ToolAccess,
    ValidationError,
    Variant,
    report,
)

from .analysis import ANALYSIS_PROVIDER, Analysis, analysis_file
from .filters import MEMGRAPH, AnalysisFilter, activities, entity_types, time_range
from .service import STORAGE, AnalysisRuntime, AnalysisService, remove_file

GROUP = "Analisi"
UNCHANGED = "unchanged"
CHANGED = "changed"
UNCHANGED_NOTICE = "L'analisi non ha modificato il grafo: è uguale a quello di partenza."


# The values of a field listed in the example configuration.
SHOWN_VALUES = 8


def name_field() -> Field:
    return Field("name", "Nome dell'analisi", required=True,
                 help="Diventa anche il nome del file in Analyses/ del dataset: deve essere unico.")


class _AnalysisOperation(Operation):
    group = GROUP
    inputs = (OperationInput("ekg", (ekg.EKG_KIND,)),)
    produces = (ekg.EKG_KIND,)
    requires_tools = (MEMGRAPH, STORAGE)

    def __init__(self, runtime: AnalysisRuntime, service: AnalysisService):
        self._runtime = runtime
        self._service = service

    def _create(self, parent: ObjectRef, analysis: Analysis, tools: ToolAccess) -> list[ObjectDraft]:
        applied = self._service.apply(parent, analysis, tools)
        meta: dict[str, Any] = {
            "state": {"provider": ANALYSIS_PROVIDER, "spec": analysis.to_spec()},
            "graph_key": applied.graph_key,
            "analysis": {"dataset": applied.dataset, "name": analysis.name,
                         **({"based_on": applied.based_on} if applied.based_on else {})},
            "counts": {"before": applied.before, "after": applied.after},
            "result": CHANGED if applied.changed else UNCHANGED,
        }
        if not applied.changed:
            meta["notice"] = UNCHANGED_NOTICE
        return [ObjectDraft(analysis.name, ekg.EKG_KIND, meta, description=analysis.description)]

    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        ekg.dispose(obj, tools)
        found = analysis_file(obj)
        if found is None:
            return
        repository = ekg.DatasetRepository(tools.get(STORAGE))
        dataset, name = found
        if name in repository.analyses(dataset):
            remove_file(repository, dataset, name)


class NewAnalysis(_AnalysisOperation):
    id = "new"
    label = "Nuova analisi"
    description = "Filtra l'EKG con una lista di condizioni e ne fa un nuovo oggetto."

    def fields(self, inputs: Mapping[str, ObjectRef], tools: ToolAccess) -> list[Field]:
        obj = inputs["ekg"]
        variants = tuple(
            Variant(item.key, item.label or item.key, item.description, tuple(item.fields(obj, tools)))
            for item in self._runtime.filters()
        )
        return [
            name_field(),
            Field("description", "Descrizione", type="textarea"),
            Field("filters", "Filtri", type="items", required=True, variants=variants,
                  help="Si applicano nell'ordine dei filtri, non in quello della lista."),
        ]

    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools: ToolAccess) -> list[ObjectDraft]:
        analysis = Analysis.from_items(params["name"], params.get("filters") or [], self._runtime.filters(),
                                       params.get("description") or "")
        return self._create(inputs["ekg"], analysis, tools)


class ImportAnalysis(_AnalysisOperation):
    id = "import"
    label = "Importa configurazione di analisi"
    description = (
        "Crea un'analisi da un file JSON nel formato delle analisi salvate "
        "(vedi \"Esempio di configurazione\")."
    )

    def fields(self, inputs: Mapping[str, ObjectRef], tools: ToolAccess) -> list[Field]:
        return [name_field(), Field("file", "File di configurazione (.json)", type="file", required=True)]

    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools: ToolAccess) -> list[ObjectDraft]:
        upload = params["file"]
        try:
            content = json.loads(upload.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"The file '{upload.filename}' is not valid JSON: {exc}") from None
        analysis = Analysis.from_legacy(params["name"], content, self._runtime.filters())
        return self._create(inputs["ekg"], analysis, tools)


# The values of the old help/file_configuration_example.json, used when the
# graph has no entity, activity or timestamp to show.
LEGACY_EXAMPLE = {
    "timestamp": [{"startDate": "2021-05-01T22:00:00.000Z", "endDate": "2021-05-09T21:00:00.000Z"}],
    "performance": [{"entity": "Actor", "operator": ">=", "seconds": 100}],
    "includeActivities": [{"activities": ["Create_Order", "Receive_SO", "Update_Invoice"]}],
    "excludeActivities": [{"activities": ["Create_Invoice", "Unpack", "Ship"]}],
    "frequence": [{"entity": "Actor", "operator": ">=", "frequency": 3}],
    "variant": [{"entity": "Order", "operator": "=", "variant": 1}],
}


def example_configuration(types: list[str], names: list[str], first: str | None, last: str | None) -> dict[str, Any]:
    example = json.loads(json.dumps(LEGACY_EXAMPLE))
    if first and last:
        example["timestamp"] = [{"startDate": first, "endDate": last}]
    if types:
        example["performance"][0]["entity"] = types[0]
        example["frequence"][0]["entity"] = types[-1]
        example["variant"][0]["entity"] = types[0]
    if names:
        include = names[:min(3, max(1, len(names) // 2))]
        exclude = names[len(include):len(include) + 3] or include[-1:]
        example["includeActivities"] = [{"activities": include}]
        example["excludeActivities"] = [{"activities": exclude}]
    return example


def _field_text(spec: Field) -> str:
    values = spec.choice_values()
    shown = ", ".join(f"`{value}`" for value in values[:SHOWN_VALUES]) + (", …" if len(values) > SHOWN_VALUES else "")
    return f"| `{spec.name}` | {spec.label} | {spec.type} | {shown} |"


def explanation(filters: list[AnalysisFilter], obj: ObjectRef, tools: ToolAccess) -> str:
    lines = [
        "Una configurazione è un file JSON con una chiave per filtro; ogni chiave ha una lista di condizioni.",
        "I filtri si applicano in quest'ordine, qualunque sia l'ordine delle chiavi nel file: "
        + ", ".join(f"`{item.key}`" for item in filters) + ".",
        "Le chiavi `dataset_name`, `analysis_name` e `analysis_description` sono facoltative e vengono ignorate "
        "all'import (il nome lo scegli nell'operazione).",
        "",
    ]
    for item in filters:
        lines += [f"### `{item.key}`: {item.label or item.key}", "", item.description, "",
                  "| campo | significato | tipo | valori |", "|---|---|---|---|"]
        lines += [_field_text(spec) for spec in item.fields(obj, tools)]
        lines.append("")
    lines.append("Operatori: `<`, `<=`, `=`, `!=`, `>`, `>=`. Le date sono ISO-8601; il fuso orario viene ignorato.")
    return "\n".join(lines)


class ExampleConfiguration(Operation):
    id = "example"
    label = "Esempio di configurazione"
    description = (
        "Un report con un file di configurazione di esempio, costruito su questo EKG, "
        "e la spiegazione delle chiavi."
    )
    group = GROUP
    inputs = (OperationInput("ekg", (ekg.EKG_KIND,)),)
    produces = (REPORT,)
    requires_tools = (MEMGRAPH,)

    def __init__(self, runtime: AnalysisRuntime):
        self._runtime = runtime

    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools: ToolAccess) -> list[ObjectDraft]:
        obj = inputs["ekg"]
        filters = self._runtime.filters()
        first, last = time_range(obj, tools)
        example = example_configuration(entity_types(obj, tools), activities(obj, tools), first, last)
        for item in filters:
            example.setdefault(item.key, [])
        content = json.dumps(example, ensure_ascii=False, indent=2).encode("utf-8")
        blocks = [
            report.markdown(explanation(filters, obj, tools), title="Come è fatta una configurazione"),
            report.file("analysis_example.json", content, "application/json", title="Esempio"),
        ]
        return [report.report(f"Esempio di configurazione di {obj.name}", blocks,
                              description="Da usare con \"Importa configurazione di analisi\".")]
