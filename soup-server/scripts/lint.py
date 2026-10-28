"""
------------------------------------------------------------------------
File : lint.py
Description: The static analysis of the backend, configured in
             pyproject.toml: ruff (E, F, W, I, B, UP, SIM, C90 with
             max-complexity 10, PL), vulture (min-confidence 80, with
             scripts/vulture_whitelist.py) and mypy --strict on soup/
             and on the server/ part of every package.
             The packages are imported at runtime as soup_pkg_<name>
             (soup/core/packages/loader.py), a name that exists on disk
             nowhere: mypy checks a temporary copy of each server/ folder
             under that name, so "from soup_pkg_ekg.api import ..." is
             resolved, and the paths of the messages are mapped back to
             soup-packages/<name>/server/.
             Run from soup-server/ with requirements-dev.txt installed:
             python scripts/lint.py [ruff|vulture|mypy ...] [--counts]
             Exit code 1 if a tool reports something.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
PACKAGES = SERVER.parent / "soup-packages"
# "<path>:<line>[:<column>]: <message>", the path possibly with a drive letter.
MESSAGE = re.compile(r"^(?P<path>(?:[A-Za-z]:)?[^:\n]+\.py):\d+(?::\d+)?:(?P<rest>.*)$", re.MULTILINE)


def _run(command: list[str], cwd: Path = SERVER, env_path: str = "") -> tuple[int, str]:
    env = {**os.environ, "MYPYPATH": env_path} if env_path else None
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=env, check=False)
    return result.returncode, result.stdout + result.stderr


def package_servers() -> dict[str, Path]:
    """Module name (soup_pkg_<manifest name>) -> server/ folder, _template included."""

    found = {}
    for server in sorted(path for path in PACKAGES.glob("*/server") if path.is_dir()):
        manifest = json.loads((server.parent / "soup-package.json").read_text(encoding="utf-8"))
        found[f"soup_pkg_{manifest['name']}"] = server
    return found


def ruff() -> tuple[int, str]:
    paths = ["soup", *(str(path) for path in package_servers().values())]
    return _run([sys.executable, "-m", "ruff", "check", "--output-format", "concise", *paths])


def vulture() -> tuple[int, str]:
    return _run([sys.executable, "-m", "vulture"])


def mypy() -> tuple[int, str]:
    config = str(SERVER / "pyproject.toml")
    code, output = _run([sys.executable, "-m", "mypy", "--config-file", config, "soup"])
    servers = package_servers()
    with tempfile.TemporaryDirectory(prefix="soup-mypy-") as temporary:
        root = Path(temporary)
        for name, server in servers.items():
            shutil.copytree(server, root / name, ignore=shutil.ignore_patterns("__pycache__"))
        package_code, package_output = _run(
            [sys.executable, "-m", "mypy", "--config-file", config, *(f"-p{name}" for name in servers)],
            cwd=root, env_path=str(SERVER),
        )
    for name, server in servers.items():
        real = server.relative_to(SERVER.parent).as_posix() + "/"
        for separator in (os.sep, "/"):
            package_output = package_output.replace(f"{name}{separator}", real)
    # The packages import soup/: its messages come twice, keep each once.
    lines = list(dict.fromkeys(line for line in (output + package_output).splitlines() if MESSAGE.match(line)))
    return max(code, package_code), "\n".join(lines)


def counts(tool: str, output: str) -> str:
    """One line per area with the number of messages, for the summary."""

    messages = [match for match in MESSAGE.finditer(output) if tool != "mypy" or " error:" in match.group("rest")]
    per_area = Counter(_area(match.group("path")) for match in messages)
    lines = [f"{tool}: {sum(per_area.values())}"]
    lines += [f"  {area}: {count}" for area, count in sorted(per_area.items())]
    return "\n".join(lines)


def _area(path: str) -> str:
    match = re.search(r"soup-packages/([^/]+)/", path.replace("\\", "/"))
    return f"package {match.group(1)}" if match else "soup (host)"


TOOLS: dict[str, Callable[[], tuple[int, str]]] = {"ruff": ruff, "vulture": vulture, "mypy": mypy}


def main(arguments: list[str]) -> int:
    only_counts = "--counts" in arguments
    selected = [name for name in arguments if name in TOOLS] or list(TOOLS)
    failed = False
    for name in selected:
        code, output = TOOLS[name]()
        failed = failed or code != 0
        print(counts(name, output) if only_counts else f"== {name}\n{output}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
