"""
------------------------------------------------------------------------
File : package_routes.py
Description: /api/v3/packages - the package manager over HTTP:
             - GET    /api/v3/packages                 list with status,
                      version, contributions and errors
             - POST   /api/v3/packages                 install a zip
                      (multipart field `file`; `allow_override=true` to
                      replace a bundled package with a higher version)
             - POST   /api/v3/packages/<name>/enable
             - POST   /api/v3/packages/<name>/disable  (`cascade=true`
                      also disables the packages depending on it)
             - DELETE /api/v3/packages/<name>          uninstall
             - GET    /api/v3/packages/<name>/app/<path>  static files of
                      the package's app/dist (PackageFrontend validates
                      the path), with an ETag based on the version
             - GET    /api/v3/frontend/manifest        the active packages
                      with an app part, dependencies first
             Install and uninstall answer 403 unless
             SOUP_ALLOW_PACKAGE_INSTALL=true: a package runs code with
             the privileges of the server and of the browser. Domain
             errors propagate to the handler in flask_app.py.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from flask import Blueprint, send_file

from soup.api import request_args, serializers
from soup.core.engine import Engine

PACKAGE_ROUTES_BLUEPRINT_NAME = "package_routes_bp"


def build_package_blueprint(engine: Engine) -> Blueprint:
    blueprint = Blueprint(PACKAGE_ROUTES_BLUEPRINT_NAME, __name__)
    packages = engine.package_manager
    frontend = engine.frontend

    @blueprint.route("/api/v3/packages", methods=["GET"])
    def list_packages():
        return serializers.ok("Packages", [serializers.package(info) for info in packages.list()])

    @blueprint.route("/api/v3/packages", methods=["POST"])
    def install_package():
        archive = request_args.uploaded_file()
        info = packages.install(archive.stream, allow_override=request_args.flag("allow_override"))
        return serializers.ok(f"Package '{info.name}' installed", serializers.package(info), 201)

    @blueprint.route("/api/v3/packages/<name>/enable", methods=["POST"])
    def enable_package(name: str):
        info = packages.enable(name)
        return serializers.ok(f"Package '{name}' enabled", serializers.package(info))

    @blueprint.route("/api/v3/packages/<name>/disable", methods=["POST"])
    def disable_package(name: str):
        disabled = packages.disable(name, cascade=request_args.flag("cascade"))
        return serializers.ok(f"Package '{name}' disabled", {"disabled": disabled})

    @blueprint.route("/api/v3/packages/<name>", methods=["DELETE"])
    def uninstall_package(name: str):
        packages.uninstall(name)
        return serializers.ok(f"Package '{name}' uninstalled", {"name": name})

    @blueprint.route("/api/v3/packages/<name>/app/<path:path>", methods=["GET"])
    def package_app_file(name: str, path: str):
        static = frontend.app_file(name, path)
        return send_file(static.path, mimetype=static.mime, etag=static.etag, conditional=True, max_age=0)

    @blueprint.route("/api/v3/frontend/manifest", methods=["GET"])
    def frontend_manifest():
        return serializers.ok("Frontend manifest", [serializers.frontend_module(m) for m in frontend.manifest()])

    return blueprint
