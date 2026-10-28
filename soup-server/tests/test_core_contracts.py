"""
------------------------------------------------------------------------
File : test_core_contracts.py
Description: Tests for the value objects of the core contracts (report
             blocks, Upload, ObjectRef/CreatedBy, Inspection,
             OperationInput, validate_name) and for the contracts version
             declared by the built-in plugins.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import base64
import io

import pytest

from soup.core.contracts import (
    CONTRACTS_API_VERSION,
    CreatedBy,
    Field,
    Inspection,
    ObjectRef,
    OperationInput,
    Upload,
    ValidationError,
    validate_name,
)
from soup.core.contracts import report
from tests.packages import bundled_plugin

CAUSAL_DF = bundled_plugin("causal_df")
CSV_EKG = bundled_plugin("csv_ekg")
EKG = bundled_plugin("ekg")


def test_contracts_version_is_3_1_and_built_in_plugins_declare_3_0():
    assert CONTRACTS_API_VERSION == "4.0"
    assert CSV_EKG.api_version == "4.0"
    assert EKG.api_version == "4.0"
    assert CAUSAL_DF.api_version == "4.0"


def test_block_factories_produce_the_documented_shapes():
    graph = report.graph(nodes=[{"id": 1}, {"id": 2, "label": "B"}], edges=[{"source": 1, "target": 2}])
    assert graph["data"] == {
        "nodes": [
            {"id": "1", "label": "1", "group": "", "props": {}},
            {"id": "2", "label": "B", "group": "", "props": {}},
        ],
        "edges": [{"id": "1->2#0", "source": "1", "target": "2", "label": "", "group": "", "props": {}}],
        "directed": True,
    }
    assert report.table(["a", "b"], [(1, 2)], total=10, title="Rows") == {
        "type": "table", "title": "Rows", "data": {"columns": ["a", "b"], "rows": [[1, 2]], "total": 10}
    }
    assert report.chart("bar", ["x"], [{"label": "n", "data": (1,)}])["data"]["datasets"] == [{"label": "n", "data": [1]}]
    assert report.keyvalue({"rows": 3})["data"] == {"items": [{"key": "rows", "value": 3}]}
    assert report.file("a.txt", b"hi", "text/plain")["data"]["base64"] == base64.b64encode(b"hi").decode()
    assert report.image(b"\x89PNG", "image/png")["data"]["mime"] == "image/png"
    assert report.svg("<svg/>")["data"] == {"svg": "<svg/>"}
    assert report.error("nope")["data"] == {"message": "nope"}
    assert report.markdown("# t")["data"] == {"markdown": "# t"}
    assert report.text("t")["type"] == "text"


@pytest.mark.parametrize(
    "block",
    [
        {"type": "html", "data": {"html": "<script>"}},
        {"type": "text", "data": {}},
        {"type": "image", "data": {"mime": "image/png"}},
        {"type": "chart", "data": {"chart": "radar", "labels": [], "datasets": []}},
        {"type": "table", "data": {"columns": []}},
        {"type": "text", "data": "plain"},
        "not a block",
    ],
)
def test_invalid_blocks_are_refused(block):
    with pytest.raises(ValueError):
        report.validate_block(block)


def test_report_draft_carries_validated_blocks():
    draft = report.report("stats", [report.text("hi")], "Summary")

    assert (draft.name, draft.kind, draft.description) == ("stats", "report", "Summary")
    assert draft.meta == {"blocks": [{"type": "text", "title": "", "data": {"text": "hi"}}]}


def test_upload_can_be_read_many_times():
    file = Upload("log.csv", io.BytesIO(b"a,b"), "text/csv")

    assert file.read() == b"a,b"
    assert file.stream.read() == b"a,b"
    assert file.stream.read() == b"a,b"


def test_object_ref_round_trips_and_is_frozen():
    obj = ObjectRef(
        id="44444444-4444-4444-8444-444444444444", name="orders", kind="event_log",
        created_by=CreatedBy("operation", "filter", "logs"), parents=["p1", "p2"],
        created_at="2025-01-01T00:00:00.000", description="d", meta={"events": 3},
    )

    assert obj.parents == ("p1", "p2")
    assert ObjectRef.from_dict(obj.to_dict()) == obj
    with pytest.raises(Exception):
        obj.kind = "table"  # type: ignore[misc]
    with pytest.raises(ValueError):
        CreatedBy("plugin", "x", "y")


def test_inspection_and_operation_input():
    inspection = Inspection(preview=[report.text("hi")], fields=[Field("sep")])

    assert inspection.to_dict()["preview"] == [{"type": "text", "title": "", "data": {"text": "hi"}}]
    assert inspection.to_dict()["fields"][0]["name"] == "sep"
    assert OperationInput("log", "event_log").kinds == ("event_log",)
    with pytest.raises(ValueError):
        OperationInput("log", ())


@pytest.mark.parametrize("name", ["orders", "Orders 2025", "a.b", "ordini-é", "x" * 128])
def test_validate_name_accepts_ordinary_names(name):
    assert validate_name(name) == name


def test_validate_name_names_the_resource():
    with pytest.raises(ValidationError, match="Package name"):
        validate_name("_x", label="Package")
