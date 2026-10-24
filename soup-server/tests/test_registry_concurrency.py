"""
------------------------------------------------------------------------
File : test_registry_concurrency.py
Description: Packages are installed and uninstalled while requests read
             the registries: a thread installs and uninstalls a package
             in a loop while another lists the importers, reads an
             extension point and publishes events. With copy-on-write
             registries (Registry, ExtensionPoints, EventBus) no reader
             ever sees a structure being changed, so nothing raises.
             The package registers many importers and the interpreter
             switches threads very often, so that an in-place registry
             would be caught mid-iteration ("dictionary changed size").
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import sys
import threading

import pytest

from soup.core.contracts import ExtensionPointError
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import FakeDatabase, InMemoryFileStorage
from tests.package_builder import IMPORTER_PLUGIN, build_zip, write_package

ITERATIONS = 200
CONTRIBUTIONS = 40

# Opens an extension point, contributes to it, subscribes to an event
# and registers an importer: every structure the reader touches changes
# on each install and uninstall.
BUSY_PLUGIN = IMPORTER_PLUGIN.replace(
    "        ctx.add_importer(CsvImporter(self.name))",
    f"""        for index in range({CONTRIBUTIONS}):
            importer = CsvImporter(self.name)
            importer.id = f"csv{{index}}"
            ctx.add_importer(importer)
            ctx.subscribe("busy.event", lambda payload: None)
        ctx.add_extension_point("busy.point")
        for index in range({CONTRIBUTIONS}):
            ctx.contribute("busy.point", "item", key=f"k{{index}}")""",
)


@pytest.fixture(autouse=True)
def _switch_threads_often():
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(previous)


@pytest.fixture(autouse=True)
def _forget_test_modules():
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name.startswith("soup_pkg_"):
            del sys.modules[name]


def test_install_and_uninstall_while_reading_registries_and_publishing(tmp_path):
    bundled, installed = tmp_path / "bundled", tmp_path / "installed"
    write_package(bundled, "stable", plugin_source=IMPORTER_PLUGIN)
    settings = Settings(
        packages_path=(str(bundled), str(installed)), installed_packages_dir=str(installed), allow_package_install=True
    )
    engine = build_engine(settings, db=FakeDatabase(), storage=InMemoryFileStorage())
    archive = build_zip(tmp_path, "busy", plugin_source=BUSY_PLUGIN, extension_points=["busy.point"])
    errors: list[BaseException] = []
    done = threading.Event()
    reads = 0

    def churn() -> None:
        try:
            for _ in range(ITERATIONS):
                engine.package_manager.install(io.BytesIO(archive))
                engine.package_manager.uninstall("busy")
        except BaseException as exc:  # noqa: BLE001 - reported by the test
            errors.append(exc)
        finally:
            done.set()

    def read() -> None:
        nonlocal reads
        try:
            while not done.is_set():
                # Key, package and item come from one snapshot: always consistent.
                entries = engine.import_router.importers_for("x.csv")
                keys = [entry.key for entry in entries]
                assert all(entry.key == f"{entry.package}.{entry.item.id}" for entry in entries)
                assert "stable.csv" in keys
                assert all(key == "stable.csv" or key.startswith("busy.csv") for key in keys)
                list(engine.ctx.importers)
                engine.ctx.importers.keys()
                try:
                    engine.ctx.contributions("busy.point")
                except ExtensionPointError:
                    pass  # the package is uninstalled at this moment: a normal answer
                engine.event_bus.publish("busy.event", {"n": reads})
                engine.package_manager.package_status("busy")
                reads += 1
        except BaseException as exc:  # noqa: BLE001 - reported by the test
            errors.append(exc)

    writer = threading.Thread(target=churn)
    reader = threading.Thread(target=read)
    reader.start()
    writer.start()
    writer.join(timeout=300)
    reader.join(timeout=60)

    assert errors == []
    assert not writer.is_alive() and not reader.is_alive()
    assert reads > 0
    assert engine.ctx.importers.keys() == ["stable.csv"]
    assert engine.ctx.extension_points.points() == []
