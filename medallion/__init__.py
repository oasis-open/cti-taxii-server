import logging

from flask import Flask
from flask_httpauth import HTTPBasicAuth

from medallion.version import __version__  # noqa

# Console Handler for medallion messages
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("[%(name)s] [%(levelname)-8s] [%(asctime)s] %(message)s"))

# Module-level logger
log = logging.getLogger(__name__)
log.addHandler(ch)

application_instance = Flask(__name__)
auth = HTTPBasicAuth()

_CONFIG = None


def set_config(config):
    global _CONFIG
    _CONFIG = config


def get_config():
    return _CONFIG


def connect_to_backend(config_info):
    log.debug("Initializing backend configuration using: {}".format(config_info))

    if "type" not in config_info:
        raise ValueError("No backend for the TAXII server was provided")
    if config_info["type"] == "memory":
        log.debug("Initializing medallion with MemoryBackend")
        from medallion.backends.memory_backend import MemoryBackend
        return MemoryBackend(config_info["data_file"])
    elif config_info["type"] == "mongodb":
        log.debug("Initializing medallion with MongoBackend")
        try:
            from medallion.backends.mongodb_backend import MongoBackend
        except ImportError:
            raise ImportError("The pymongo package is not available")
        return MongoBackend(config_info["url"])
    else:
        raise ValueError("Unknown backend %s for TAXII server ".format(config_info["backend"]))


_BACKEND = None


def init_backend(config_info):
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = connect_to_backend(config_info)


def get_backend():
    return _BACKEND


@auth.get_password
def get_pwd(username):
    users = get_config()["users"]
    if username in users:
        return users.get(username)
    return None


def register_blueprints(flask_application_instance):
    log.debug("Registering medallion blueprints")
    from medallion.views import collections
    from medallion.views import discovery
    from medallion.views import manifest
    from medallion.views import objects

    flask_application_instance.register_blueprint(collections.mod)
    flask_application_instance.register_blueprint(discovery.mod)
    flask_application_instance.register_blueprint(manifest.mod)
    flask_application_instance.register_blueprint(objects.mod)
