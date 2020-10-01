import importlib
import inspect
import logging
import pkgutil
import sys

import environ
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


# Finally we define a top-level environ config class which includes and configs
# defined in the registered backends
@environ.config(prefix="BACKEND")
class BackendConfig(object):
    for name, clsobj in base.BackendRegistry.iter_():
        # We have to use a magic attribute name here since `config`s don't have
        # a specific mixin or type we can check for
        try:
            locals()[name] = environ.group(clsobj.Config, optional=True)
        except AttributeError:
            pass
    module_class = environ.var(None)
