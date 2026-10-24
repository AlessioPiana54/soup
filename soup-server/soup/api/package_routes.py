"""
------------------------------------------------------------------------
File : package_routes.py
Description: /api/v3/packages - the package manager over HTTP:
             - GET    /api/v3/packages                 list with status
             - POST   /api/v3/packages                 install a zip
                      (multipart field `file`; `allow_override=true` to
                      replace a bundled package with a higher version)
             - POST   /api/v3/packages/<name>/enable
             - POST   /api/v3/packages/<name>/disable  (`cascade=true`
                      also disables the packages depending on it)
             - DELETE /api/v3/packages/<name>          uninstall
             Install and uninstall answer 403 unless
             SOUP_ALLOW_PACKAGE_INSTALL=true: a package runs code with
             the privileges of the server and of the browser. Domain
             errors propagate to the handler in flask_app.py.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from soup.core.contracts import ValidationError
from soup.core.engine import Engine
from soup.core.results import Result

PACKAGE_ROUTES_BLUEPRINT_NAME = "package_routes_bp"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _flag(name: str) -> bool:
    value = request.values.get(name, "")
    return value.strip().lower() in _TRUE_VALUES


def _ok(message: str, data, status: int = 200):
    return jsonify(Result(status, message, data).to_dict()), status


def build_package_blueprint(engine: Engine) -> Blueprint:
    blueprint = Blueprint(PACKAGE_ROUTES_BLUEPRINT_NAME, __name__)
    packages = engine.package_manager

    @blueprint.route("/api/v3/packages", methods=["GET"])
    def list_packages():
        return _ok("Packages", [info.to_dict() for info in packages.list()])

    @blueprint.route("/api/v3/packages", methods=["POST"])
    def install_package():
        file = request.files.get("file")
        if file is None or not file.filename:
            raise ValidationError("Missing package archive (multipart field 'file')")
        info = packages.install(file.stream, allow_override=_flag("allow_override"))
        return _ok(f"Package '{info.name}' installed", info.to_dict(), 201)

    @blueprint.route("/api/v3/packages/<name>/enable", methods=["POST"])
    def enable_package(name: str):
        info = packages.enable(name)
        return _ok(f"Package '{name}' enabled", info.to_dict())

    @blueprint.route("/api/v3/packages/<name>/disable", methods=["POST"])
    def disable_package(name: str):
        disabled = packages.disable(name, cascade=_flag("cascade"))
        return _ok(f"Package '{name}' disabled", {"disabled": disabled})

    @blueprint.route("/api/v3/packages/<name>", methods=["DELETE"])
    def uninstall_package(name: str):
        packages.uninstall(name)
        return _ok(f"Package '{name}' uninstalled", {"name": name})

    return blueprint
