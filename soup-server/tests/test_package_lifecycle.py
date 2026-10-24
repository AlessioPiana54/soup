"""
------------------------------------------------------------------------
File : test_package_lifecycle.py
Description: Tests for the runtime package lifecycle on a whole engine
             (soup.core.packages.PackageManager): install from a zip
             (contributions available at once, hostile or invalid
             archives refused, name conflicts, upgrades, rollback),
             disable/enable, dependents (409), uninstall leaving the
             package's objects in the catalog as "missing", and the
             SOUP_ALLOW_PACKAGE_INSTALL switch.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import sys

import pytest

from soup.core.contracts import (
    CREATED_BY_IMPORTER,
    ConflictError,
    CreatedBy,
    ForbiddenError,
    ObjectRef,
    ValidationError,
)
from soup.core.engine import build_engine
from soup.core.events import PACKAGE_LOADED, PACKAGE_UNLOADED
from soup.core.packages import ArchiveLimits
from soup.core.settings import Settings
from tests.fakes import CoreToolsPackage, FakeDatabase, InMemoryFileStorage
from tests.package_builder import FAILING_PLUGIN, build_zip, write_package, zip_entries


@pytest.fixture(autouse=True)
def _forget_test_modules():
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name.startswith("soup_pkg_"):
            del sys.modules[name]


@pytest.fixture
def dirs(tmp_path):
    bundled, installed = tmp_path / "bundled", tmp_path / "installed"
    bundled.mkdir()
    return bundled, installed


def _engine(bundled, installed, allow_install=True, extra=()):
    settings = Settings(
        packages_path=(str(bundled), str(installed)),
        installed_packages_dir=str(installed),
        allow_package_install=allow_install,
    )
    return build_engine(settings, db=FakeDatabase(), storage=InMemoryFileStorage(), extra_plugins=extra)


def _events(engine, event):
    received = []
    engine.event_bus.subscribe(event, lambda payload: received.append(dict(payload)), owner="test")
    return received


# ---------------------------------------------------------------------- #
# install
# ---------------------------------------------------------------------- #
def test_install_from_zip_makes_contributions_available_at_once(tmp_path, dirs):
    engine = _engine(*dirs)
    loaded = _events(engine, PACKAGE_LOADED)

    info = engine.package_manager.install(io.BytesIO(build_zip(tmp_path, "alpha", provides_tools=["thing"])))

    assert (info.name, info.status, info.origin) == ("alpha", "active", "installed")
    assert "alpha" in engine.ctx.input_readers
    assert engine.ctx.tool_registry.owner_of("thing") == "alpha"
    assert loaded == [{"package": "alpha", "version": "1.0.0"}]
    assert (dirs[1] / "alpha" / "soup-package.json").is_file()
    assert not any((dirs[1] / "_staging").iterdir())


def test_install_accepts_a_zip_with_the_manifest_at_its_root(tmp_path, dirs):
    from tests.package_builder import zip_folder

    engine = _engine(*dirs)
    data = zip_folder(write_package(tmp_path / "src", "alpha"), top_folder=False)

    assert engine.package_manager.install(io.BytesIO(data)).status == "active"


def test_installed_package_is_found_again_at_the_next_start(tmp_path, dirs):
    _engine(*dirs).package_manager.install(io.BytesIO(build_zip(tmp_path, "alpha")))
    sys.modules.pop("soup_pkg_alpha", None)

    assert "alpha" in _engine(*dirs).report.loaded


@pytest.mark.parametrize(
    "archive",
    [
        zip_entries({"../evil.py": b"x", "soup-package.json": b"{}"}),
        zip_entries({"alpha/../../evil.py": b"x", "alpha/soup-package.json": b"{}"}),
        zip_entries({"/abs/evil.py": b"x", "soup-package.json": b"{}"}),
        zip_entries({"C:/evil.py": b"x", "soup-package.json": b"{}"}),
        zip_entries({"soup-package.json": b"{}"}, symlinks=["server"]),
    ],
    ids=["dotdot", "nested-dotdot", "absolute", "drive", "symlink"],
)
def test_hostile_zip_is_refused_and_nothing_is_written(tmp_path, dirs, archive):
    engine = _engine(*dirs)

    with pytest.raises(ValidationError):
        engine.package_manager.install(io.BytesIO(archive))

    assert not (tmp_path / "evil.py").exists()
    assert not (dirs[1] / "evil.py").exists()
    assert [path.name for path in dirs[1].glob("*") if not path.name.startswith("_")] == []


def test_not_a_zip_is_refused(dirs):
    with pytest.raises(ValidationError, match="not a valid zip"):
        _engine(*dirs).package_manager.install(io.BytesIO(b"plain text"))


def test_zip_without_manifest_is_refused(dirs):
    with pytest.raises(ValidationError, match="soup-package.json"):
        _engine(*dirs).package_manager.install(io.BytesIO(zip_entries({"a/x.txt": b"x", "b/y.txt": b"y"})))


def test_invalid_manifest_is_refused(tmp_path, dirs):
    engine = _engine(*dirs)
    archive = build_zip(tmp_path, "alpha", manifest={"name": "alpha", "version": "nope"})

    with pytest.raises(ValidationError) as error:
        engine.package_manager.install(io.BytesIO(archive))

    assert error.value.http_status_code == 400
    assert "version" in error.value.details["fields"]
    assert not (dirs[1] / "alpha").exists()


def test_too_large_archive_is_refused(tmp_path, dirs):
    engine = _engine(*dirs)
    engine.package_manager.config.limits = ArchiveLimits(max_archive_bytes=100)

    with pytest.raises(ValidationError, match="larger than"):
        engine.package_manager.install(io.BytesIO(build_zip(tmp_path, "alpha")))


def test_missing_python_dependency_is_refused_at_install(tmp_path, dirs):
    archive = build_zip(tmp_path, "alpha", python_dependencies=["surely-not-installed-lib"])

    with pytest.raises(ValidationError, match="not installed at runtime"):
        _engine(*dirs).package_manager.install(io.BytesIO(archive))
    assert not (dirs[1] / "alpha").exists()


def test_required_package_must_be_active(tmp_path, dirs):
    archive = build_zip(tmp_path, "alpha", requires=["beta"])

    with pytest.raises(ConflictError) as error:
        _engine(*dirs).package_manager.install(io.BytesIO(archive))
    assert error.value.details == {"missing": ["beta"]}


def test_bundled_name_needs_a_higher_version_and_explicit_override(tmp_path, dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", version="1.0.0", marker="bundled")
    engine = _engine(*dirs)
    packages = engine.package_manager

    with pytest.raises(ConflictError, match="ships with SOUP"):
        packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="1.0.0")), allow_override=True)
    with pytest.raises(ConflictError, match="allow_override"):
        packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="2.0.0")))

    info = packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="2.0.0", marker="v2")), allow_override=True)

    assert (info.version, info.origin) == ("2.0.0", "installed")
    assert "v2" in engine.ctx.input_readers and "bundled" not in engine.ctx.input_readers


def test_installed_package_is_upgraded_only_to_a_higher_version(tmp_path, dirs):
    engine = _engine(*dirs)
    packages = engine.package_manager
    packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="1.0.0", marker="v1")))

    with pytest.raises(ConflictError, match="already installed"):
        packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="1.0.0")))

    assert packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="1.1.0", marker="v11"))).version == "1.1.0"
    assert "v11" in engine.ctx.input_readers and "v1" not in engine.ctx.input_readers


def test_failing_upgrade_rolls_back_to_the_previous_version(tmp_path, dirs):
    engine = _engine(*dirs)
    packages = engine.package_manager
    packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="1.0.0", marker="v1")))

    with pytest.raises(ValidationError, match="register failed on purpose"):
        packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="2.0.0", plugin_source=FAILING_PLUGIN)))

    assert packages.info("alpha").version == "1.0.0"
    assert packages.info("alpha").status == "active"
    assert "v1" in engine.ctx.input_readers


def test_failing_new_package_leaves_nothing_behind(tmp_path, dirs):
    engine = _engine(*dirs)

    with pytest.raises(ValidationError, match="register failed on purpose"):
        engine.package_manager.install(io.BytesIO(build_zip(tmp_path, "alpha", plugin_source=FAILING_PLUGIN)))

    assert not (dirs[1] / "alpha").exists()
    assert [info.name for info in engine.package_manager.list()] == []


# ---------------------------------------------------------------------- #
# disable / enable
# ---------------------------------------------------------------------- #
def test_disable_removes_contributions_and_enable_restores_them(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", provides_tools=["thing"])
    engine = _engine(*dirs)
    unloaded = _events(engine, PACKAGE_UNLOADED)

    assert engine.package_manager.disable("alpha") == ["alpha"]

    assert "alpha" not in engine.ctx.input_readers
    assert "thing" not in engine.ctx.tool_registry
    assert unloaded == [{"package": "alpha", "version": "1.0.0"}]
    assert engine.package_manager.info("alpha").status == "disabled"

    assert engine.package_manager.enable("alpha").status == "active"
    assert "alpha" in engine.ctx.input_readers
    assert engine.ctx.tool_registry.owner_of("thing") == "alpha"


def test_disable_of_a_required_package_is_409_with_its_dependents(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha")
    write_package(bundled, "beta", requires=["alpha"])
    write_package(bundled, "gamma", requires=["beta"])
    write_package(bundled, "delta", provides_tools=["thing"])
    write_package(bundled, "epsilon", requires_tools=["thing"])
    engine = _engine(*dirs)
    packages = engine.package_manager

    with pytest.raises(ConflictError) as error:
        packages.disable("alpha")
    assert error.value.http_status_code == 409
    assert error.value.details == {"dependents": ["gamma", "beta"]}
    assert "alpha" in engine.ctx.input_readers

    with pytest.raises(ConflictError) as tool_error:
        packages.disable("delta")
    assert tool_error.value.details == {"dependents": ["epsilon"]}

    assert packages.disable("alpha", cascade=True) == ["gamma", "beta", "alpha"]
    assert {packages.info(name).status for name in ("alpha", "beta", "gamma")} == {"disabled"}


def test_enable_needs_the_required_packages_active(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha")
    write_package(bundled, "beta", requires=["alpha"])
    packages = _engine(*dirs).package_manager
    packages.disable("alpha", cascade=True)

    with pytest.raises(ConflictError) as error:
        packages.enable("beta")
    assert error.value.details == {"missing": ["alpha"]}

    packages.enable("alpha")
    assert packages.enable("beta").status == "active"


def test_unknown_package_is_404(dirs):
    packages = _engine(*dirs).package_manager
    with pytest.raises(Exception) as error:
        packages.disable("ghost")
    assert error.value.http_status_code == 404


# ---------------------------------------------------------------------- #
# uninstall
# ---------------------------------------------------------------------- #
def _object_of(package):
    return ObjectRef(
        id="7f7c1c39-5b8e-4f3e-9d6c-2d1a3b4c5d6e",
        name="table",
        kind="table",
        created_by=CreatedBy(CREATED_BY_IMPORTER, "alpha_importer", package),
    )


def test_uninstall_keeps_the_objects_and_marks_them_package_missing(tmp_path, dirs):
    tools = CoreToolsPackage()
    engine = _engine(*dirs, extra=[tools])
    packages = engine.package_manager
    packages.install(io.BytesIO(build_zip(tmp_path, "alpha")))
    tools.catalog.add(_object_of("alpha"))
    assert engine.workspace_service.list()[0].to_dict()["package_status"] == "active"

    packages.disable("alpha")
    assert engine.workspace_service.list()[0].package_status == "disabled"

    packages.uninstall("alpha")

    assert not (dirs[1] / "alpha").exists()
    assert "soup_pkg_alpha" not in sys.modules
    nodes = engine.workspace_service.list()
    assert [node.object.id for node in nodes] == [_object_of("alpha").id]
    assert nodes[0].package_status == "missing"
    with pytest.raises(Exception) as error:
        packages.info("alpha")
    assert error.value.http_status_code == 404


def test_uninstall_restores_the_bundled_package_of_the_same_name(tmp_path, dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", version="1.0.0", marker="bundled")
    engine = _engine(*dirs)
    packages = engine.package_manager
    packages.install(io.BytesIO(build_zip(tmp_path, "alpha", version="2.0.0", marker="v2")), allow_override=True)

    packages.uninstall("alpha")

    assert (packages.info("alpha").version, packages.info("alpha").origin) == ("1.0.0", "bundled")
    assert "bundled" in engine.ctx.input_readers


def test_bundled_packages_cannot_be_uninstalled(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha")

    with pytest.raises(ConflictError, match="can be disabled, not uninstalled"):
        _engine(*dirs).package_manager.uninstall("alpha")


def test_uninstall_of_a_required_package_is_409(tmp_path, dirs):
    packages = _engine(*dirs).package_manager
    packages.install(io.BytesIO(build_zip(tmp_path, "alpha")))
    packages.install(io.BytesIO(build_zip(tmp_path, "beta", requires=["alpha"])))

    with pytest.raises(ConflictError) as error:
        packages.uninstall("alpha")
    assert error.value.details == {"dependents": ["beta"]}


# ---------------------------------------------------------------------- #
# SOUP_ALLOW_PACKAGE_INSTALL
# ---------------------------------------------------------------------- #
def test_install_and_uninstall_are_forbidden_unless_allowed(tmp_path, dirs):
    write_package(dirs[1], "alpha")
    packages = _engine(*dirs, allow_install=False).package_manager

    with pytest.raises(ForbiddenError) as error:
        packages.install(io.BytesIO(build_zip(tmp_path, "beta")))
    assert error.value.http_status_code == 403
    with pytest.raises(ForbiddenError):
        packages.uninstall("alpha")

    assert not (dirs[1] / "beta").exists()
    assert (dirs[1] / "alpha").exists()
    # Enabling and disabling remain possible.
    assert packages.disable("alpha") == ["alpha"]
