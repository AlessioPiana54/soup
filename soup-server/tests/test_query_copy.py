"""
------------------------------------------------------------------------
File : test_query_copy.py
Description: Query and ident() live in the tool_memgraph package; the
             core keeps a temporary copy (soup/core/contracts/query.py,
             TODO commit 11) for the legacy modules. The two must stay
             the same: same code below the module docstring, same
             behaviour, and the memgraph tool accepts either Query.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from soup.core.contracts import query as core_query
from tests.fakes import FakeDatabase, fake_memgraph_tool
from tests.packages import BUNDLED_PACKAGES_DIR, bundled_api

package_query = bundled_api("tool_memgraph")


def _code_without_docstring(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    body = tree.body[1:] if isinstance(tree.body[0], ast.Expr) else tree.body
    return "\n".join(ast.dump(node) for node in body)


def test_the_core_copy_has_the_same_code():
    core_file = Path(core_query.__file__)
    package_file = BUNDLED_PACKAGES_DIR / "tool_memgraph" / "server" / "query.py"

    assert _code_without_docstring(core_file) == _code_without_docstring(package_file)
    assert "TODO(commit 11)" in core_file.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["Event", "_x", "a1"])
def test_ident_accepts_the_same_names(name):
    assert core_query.ident(name) == package_query.ident(name)


@pytest.mark.parametrize("name", ["", "a b", "a`b", "1a", "a;b", "a.b", None])
def test_ident_refuses_the_same_names(name):
    with pytest.raises(ValueError):
        core_query.ident(name)
    with pytest.raises(ValueError):
        package_query.ident(name)


def test_the_tool_runs_either_query():
    db = FakeDatabase()
    tool = fake_memgraph_tool(db)

    tool.run(core_query.Query("RETURN $x", {"x": 1}))
    tool.run(package_query.Query("RETURN $x", {"x": 2}))

    assert [query.params for query in db.received_queries] == [{"x": 1}, {"x": 2}]
