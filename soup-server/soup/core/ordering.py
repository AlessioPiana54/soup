"""
------------------------------------------------------------------------
File : ordering.py
Description: topological_order - Kahn's algorithm, stable on the given
             order, shared by the PluginManager (plugins ordered on
             `requires` and on the providers of the tools they require)
             and the PackageManager (packages ordered on `requires`).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def topological_order(
    names: list[str], requires: Mapping[str, Iterable[str]]
) -> tuple[list[str], list[str]]:
    """
    Kahn's algorithm on `requires`, stable on the order of `names`.
    Requirements outside `names` are ignored. Returns the ordered names
    and the names left out: those in a cycle and those depending on one.
    """

    indegree = {name: 0 for name in names}
    dependents: dict[str, list[str]] = {name: [] for name in names}
    for name in names:
        for dep in dict.fromkeys(requires.get(name, ())):
            if dep in indegree:
                dependents[dep].append(name)
                indegree[name] += 1

    position = {name: index for index, name in enumerate(names)}
    queue = [name for name, degree in indegree.items() if degree == 0]
    ordered: list[str] = []
    while queue:
        queue.sort(key=position.__getitem__)
        name = queue.pop(0)
        ordered.append(name)
        for dependent in dependents[name]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    done = set(ordered)
    return ordered, [name for name in names if name not in done]
