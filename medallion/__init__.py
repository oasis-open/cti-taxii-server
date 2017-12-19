import importlib
import logging
from functools import wraps

_CONFIG = None


# This is a dummy implementation of Flask Auth that always returns false
class DummyAuth:

    def login_required(self, f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function

    def get_password():
        return None


# Set the default implementation to the dummy auth
auth = DummyAuth()


def get_config():
    return _CONFIG


def init(config):
    logging.basicConfig(level=10)

    logging.debug("Initializing configuration using {0}".format(config))

    if "backend" not in config:
        raise ValueError("No backend was specified in the confinguration")

    if "type" not in config['backend']:
        raise ValueError("No backend type for the TAXII server was provided")

    global _CONFIG
    _CONFIG = config

    # If auth is not present, or it is set to true, then require it (default is required)
    global auth
    if "auth" not in config or config["auth"]:
        from flask_httpauth import HTTPBasicAuth
        auth = HTTPBasicAuth()

        if "users" in config:
            @auth.get_password
            def get_pwd(username):
                users = config["users"]
                if username in users:
                    return users.get(username)
                return None
        else:
            raise ValueError("No \"users\" entry found in configuration file")

    global _BACKEND

    backend_config = config["backend"]
    if "type" not in backend_config:
        raise ValueError("No backend type for the TAXII server was provided")

    if backend_config["type"] == "memory":
        from medallion.backends.memory_backend import MemoryBackend
        _BACKEND = MemoryBackend()
        _BACKEND.load_data_from_file(backend_config["data_file"])
    elif backend_config["type"] == "mongodb":
        try:
            from medallion.backends.mongodb_backend import MongoBackend
        except ImportError:
            raise ImportError("The pymongo package is not available")
        _BACKEND = MongoBackend(backend_config["url"])
    elif backend_config["type"] == "module":
        if "module" not in backend_config:
            raise ValueError("No module parameter found in backend_config")

        if "module_class" not in backend_config:
            raise ValueError("No module_class parameter found in backend_config")

        mod = importlib.import_module(backend_config["module"])
        class_ = getattr(mod, backend_config["module_class"])
        _BACKEND = class_(backend_config)

    else:
        raise ValueError("Unknown backend {0} for TAXII server ".format(backend_config["type"]))


_BACKEND = None


def get_backend():
    return _BACKEND


def register_blueprints(application_instance):
    logging.debug("Registering blueprints")

    from medallion.views import collections
    from medallion.views import discovery
    from medallion.views import manifest
    from medallion.views import objects

    application_instance.register_blueprint(collections.mod)
    application_instance.register_blueprint(discovery.mod)
    application_instance.register_blueprint(manifest.mod)
    application_instance.register_blueprint(objects.mod)
