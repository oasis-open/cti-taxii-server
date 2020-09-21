import importlib
import pkgutil
import sys

# Walk this package and import all sub-modules so the can instantiate backends
_paths = sys.modules[__name__].__path__
for _, subname, _ in pkgutil.walk_packages(_paths):
    mod_obj = importlib.import_module(__name__ + "." + subname)
    if "." not in subname:
        globals()[subname] = mod_obj
