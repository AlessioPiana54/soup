"""
------------------------------------------------------------------------
File : metrics.py
Description: The numbers of the code-quality summary, for the host
             (soup/) and the server/ part of the packages: lines and
             files of Python code, the warnings of ruff (pyproject.toml)
             and the cyclomatic complexity of every function (ruff C901
             with threshold 0): maximum, mean and the functions above 10.
             Run from soup-server/ with the dev requirements installed:
             python scripts/metrics.py [--json]
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SERVER = Path(__file__).resolve().parent.parent
PACKAGES = SERVER.parent / "soup-packages"
COMPLEXITY = re.compile(r"`(?P<name>[^`]+)` is too complex \((?P<value>\d+) > 0\)")
LIMIT = 10


def code_paths() -> list[Path]:
    return [SERVER / "soup", *sorted(path for path in PACKAGES.glob("*/server") if path.is_dir())]


def python_files() -> list[Path]:
    return sorted(path for root in code_paths() for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def ruff(*arguments: str) -> list[dict[str, Any]]:
    command = [sys.executable, "-m", "ruff", "check", *arguments, "--output-format", "json", "--exit-zero"]
    result = subprocess.run(command, cwd=SERVER, capture_output=True, text=True, check=True)
    found: list[dict[str, Any]] = json.loads(result.stdout or "[]")
    return found


def complexities() -> list[tuple[str, int]]:
    found = []
    paths = [str(path) for path in code_paths()]
    for item in ruff("--select", "C901", "--config", "lint.mccabe.max-complexity = 0", *paths):
        match = COMPLEXITY.search(item["message"])
        if match:
            label = Path(item["filename"]).resolve().relative_to(SERVER.parent).as_posix()
            found.append((f"{label}:{item['location']['row']} {match.group('name')}", int(match.group("value"))))
    return found


def report() -> dict[str, Any]:
    files = python_files()
    values = complexities()
    numbers = [value for _name, value in values]
    return {
        "python_files": len(files),
        "python_lines": sum(len(path.read_text(encoding="utf-8").splitlines()) for path in files),
        "ruff_warnings": len(ruff(*(str(path) for path in code_paths()))),
        "functions": len(values),
        "complexity_max": max(numbers, default=0),
        "complexity_mean": round(sum(numbers) / len(numbers), 2) if numbers else 0,
        "over_limit": sorted(([name, value] for name, value in values if value > LIMIT), key=lambda item: -item[1]),
    }


def main() -> int:
    data = report()
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2))
        return 0
    for key, value in data.items():
        if key != "over_limit":
            print(f"{key}: {value}")
    for name, value in data["over_limit"]:
        print(f"  {value:3d} {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
