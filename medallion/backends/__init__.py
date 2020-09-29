import importlib
import inspect
import pkgutil
import logging
import sys

import pkg_resources

from . import base

log = logging.getLogger(__name__)

# Walk this package and import all sub-modules so the can instantiate backends
_paths = sys.modules[__name__].__path__
for _, subname, _ in pkgutil.walk_packages(_paths):
    try:
        mod_obj = importlib.import_module(__name__ + "." + subname)
    except ImportError as exc:
        log.warn("Skipping import of %r backend: %s", subname, exc)
    else:
        if "." not in subname:
            globals()[subname] = mod_obj

# Load all defined backend entry points - we orphan them after loading rather
# than injecting them into this module, instead replying on `__init_subclass__`
for ep in pkg_resources.iter_entry_points("medallion.backends"):
    ep_obj = ep.load()
    if inspect.isclass(ep_obj):
        base.BackendRegistry.register(ep.name, ep_obj)
