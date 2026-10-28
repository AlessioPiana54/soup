"""
------------------------------------------------------------------------
File : vulture_whitelist.py
Description: Names vulture cannot see being used, because the framework
             calls them: the Flask view functions and error handlers
             (registered by their decorators), the SoupPlugin hooks and
             the Plugin classes (found by name through the manifest's
             server.plugin), the parameters of __exit__. Listed for
             vulture only: this module is never imported.
Project : soup-server
------------------------------------------------------------------------
"""

# ruff: noqa
Plugin  # soup-package.json "server": {"plugin": "plugin:Plugin"}
register  # SoupPlugin.register(ctx)
on_shutdown  # SoupPlugin.on_shutdown(ctx)
request_class  # Flask
exc_type, exc_value, tb  # __exit__
