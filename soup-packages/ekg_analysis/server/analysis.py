"""
------------------------------------------------------------------------
File : analysis.py
Description: Analysis - the generic model of an analysis (scheda C29):
             {name, description, filters: {filter key: [condition, ...]}},
             whatever package contributed the filters. It comes from:
             - the "items" field of "Nuova analisi" (from_items: each
               element {variant: filter key, values}), and
             - a configuration file in the legacy format (from_legacy:
               one key per filter - timestamp, performance,
               includeActivities, excludeActivities, frequence, variant -
               plus dataset_name, analysis_name, analysis_description),
               validated filter by filter like the legacy
               parseAndValidateJson of details-dataset; every error names
               the filter and the position ("performance[0]: seconds ...").
             to_legacy() is the file saved in <dataset>/Analyses/<name>.json
             (the six legacy keys always present, so the /api/v2 pages
             still read it; "based_on", the name of the parent analysis
             of a nested one, is an extra key the legacy format ignores).
             is_analysis() and analysis_file() read the meta of the
             objects of an analysis. ordered() pairs every condition with its
             filter in the order of the filters (`order`, then the order
             of the contributions), not the order of the items: the order
             of the filters changes the result.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from soup.core.contracts import ObjectRef, ServiceUnavailableError, ValidationError, validate_name

from .filters import LEGACY_FILTER_KEYS, AnalysisFilter

# The keys of a configuration file that are not filters.
LEGACY_META_KEYS = ("dataset_name", "analysis_name", "analysis_description", "based_on")
ANALYSIS_PROVIDER = "analysis"


def is_analysis(obj: ObjectRef) -> bool:
    state = obj.meta.get("state")
    return isinstance(state, Mapping) and state.get("provider") == ANALYSIS_PROVIDER


def analysis_file(obj: ObjectRef) -> tuple[str, str] | None:
    """(dataset, name) of the file of an analysis object, if it has one."""

    info = obj.meta.get("analysis")
    if isinstance(info, Mapping) and info.get("dataset") and info.get("name"):
        return str(info["dataset"]), str(info["name"])
    return None


def _keyed(filters: Sequence[AnalysisFilter]) -> dict[str, AnalysisFilter]:
    found: dict[str, AnalysisFilter] = {}
    for item in filters:
        found.setdefault(item.key, item)
    return found


def _raise(errors: list[str]) -> None:
    if errors:
        raise ValidationError("Invalid analysis: " + "; ".join(errors))


@dataclass(frozen=True)
class Analysis:
    name: str
    filters: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        validate_name(self.name, label="Analysis")

    # ------------------------------------------------------------------ #
    @classmethod
    def from_items(cls, name: str, items: Sequence[Mapping[str, Any]], filters: Sequence[AnalysisFilter],
                   description: str = "") -> "Analysis":
        known = _keyed(filters)
        grouped: dict[str, list[dict[str, Any]]] = {}
        errors = []
        for index, item in enumerate(items or ()):
            key = item.get("variant") if isinstance(item, Mapping) else None
            if key not in known:
                errors.append(f"filters[{index}]: unknown filter {key!r}")
                continue
            try:
                grouped.setdefault(key, []).append(known[key].validate(item.get("values") or {}))
            except ValidationError as exc:
                errors.append(f"filters[{index}] ({key}): {exc}")
        _raise(errors)
        if not grouped:
            raise ValidationError("An analysis needs at least one filter")
        return cls(name, grouped, description)

    @classmethod
    def from_legacy(cls, name: str, content: Any, filters: Sequence[AnalysisFilter], strict: bool = True) -> "Analysis":
        """
        A configuration file in the legacy format. With strict=False (the
        files already on the volume, read at startup before other packages
        contribute their filters) a key no filter knows is kept as it is.
        """

        if not isinstance(content, Mapping):
            raise ValidationError("The configuration must be a JSON object with one key per filter")
        known = _keyed(filters)
        grouped: dict[str, list[dict[str, Any]]] = {}
        errors = []
        for key, conditions in content.items():
            if key in LEGACY_META_KEYS or conditions in (None, []):
                continue
            if not isinstance(conditions, list):
                errors.append(f"{key}: must be a list of conditions")
                continue
            if key not in known:
                if strict:
                    errors.append(f"{key}: unknown filter; expected one of {list(known)}")
                else:
                    grouped[key] = [dict(item) for item in conditions if isinstance(item, Mapping)]
                continue
            for index, condition in enumerate(conditions):
                try:
                    grouped.setdefault(key, []).append(known[key].validate(condition))
                except ValidationError as exc:
                    errors.append(f"{key}[{index}]: {exc}")
        _raise(errors)
        description = content.get("analysis_description")
        return cls(name, grouped, description if isinstance(description, str) else "")

    @classmethod
    def from_spec(cls, spec: Mapping[str, Any]) -> "Analysis":
        """meta.state.spec of a derived object (to_spec)."""

        filters = spec.get("filters") or {}
        if not isinstance(filters, Mapping):
            raise ValidationError("The analysis has no valid filters")
        return cls(str(spec.get("name") or ""), {str(key): [dict(item) for item in items] for key, items in filters.items()},
                   str(spec.get("description") or ""))

    # ------------------------------------------------------------------ #
    def to_spec(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "filters": {key: [dict(item) for item in items] for key, items in self.filters.items()}}

    def to_legacy(self, dataset: str, based_on: str | None = None) -> dict[str, Any]:
        content: dict[str, Any] = {key: [dict(item) for item in self.filters.get(key, [])] for key in LEGACY_FILTER_KEYS}
        for key, items in self.filters.items():
            if key not in content:
                content[key] = [dict(item) for item in items]
        content.update({"dataset_name": dataset, "analysis_name": self.name, "analysis_description": self.description})
        if based_on:
            content["based_on"] = based_on
        return content

    def ordered(self, filters: Sequence[AnalysisFilter]) -> list[tuple[AnalysisFilter, dict[str, Any]]]:
        """
        [(filter, condition)] in the order of the filters.
        :raises ServiceUnavailableError: a filter of the analysis is not contributed by any active package
        """

        known = _keyed(filters)
        missing = sorted(key for key in self.filters if key not in known)
        if missing:
            raise ServiceUnavailableError(f"No active package provides the analysis filters {missing}")
        position = {item.key: index for index, item in enumerate(known.values())}
        keys = sorted(self.filters, key=lambda key: (known[key].order, position[key]))
        return [(known[key], condition) for key in keys for condition in self.filters[key]]
