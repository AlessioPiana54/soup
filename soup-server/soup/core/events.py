"""
------------------------------------------------------------------------
File : events.py
Description: The only events the core publishes on the EventBus: its own
             lifecycle events. Domain events (e.g. "an EKG was built") are
             declared as constants by the package that publishes them, in
             its api.py - never here.
Project : soup-server
------------------------------------------------------------------------
"""

# A new object was registered in the catalog (by an import or an
# operation). Payload: {"object": ObjectRef.to_dict()}.
OBJECT_CREATED = "object.created"

# An object is about to be disposed of and removed from the catalog.
# Payload: {"object": ObjectRef.to_dict()}. A critical subscriber can veto
# the deletion by raising.
OBJECT_BEFORE_DELETE = "object.before_delete"

# A package finished registering its contributions.
# Payload: {"package": name, "version": version}.
PACKAGE_LOADED = "package.loaded"

# A package's contributions were removed (shutdown, or deactivation at
# runtime). Payload: {"package": name, "version": version}.
PACKAGE_UNLOADED = "package.unloaded"

CORE_EVENTS = (OBJECT_CREATED, OBJECT_BEFORE_DELETE, PACKAGE_LOADED, PACKAGE_UNLOADED)
