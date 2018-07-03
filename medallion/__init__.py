import importlib
import json
import logging

import flask
from flask import Flask, Response, current_app
from flask_httpauth import HTTPBasicAuth

from medallion.version import __version__  # noqa
from medallion.views import MEDIA_TYPE_STIX_V20

# Console Handler for medallion messages
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("[%(name)s] [%(levelname)-8s] [%(asctime)s] %(message)s"))

# Module-level logger
log = logging.getLogger(__name__)
log.addHandler(ch)

application_instance = Flask(__name__)
auth = HTTPBasicAuth()


def load_app(config_file):
    with open(config_file, "r") as f:
        configuration = json.load(f)

    set_config(application_instance, configuration["users"])
    init_backend(application_instance, configuration["backend"])
    register_blueprints(application_instance)

    return application_instance


def set_config(flask_application_instance, config):
    with flask_application_instance.app_context():
        log.debug("Registering medallion users configuration into {}".format(current_app))
        flask_application_instance.users_backend = config


def connect_to_backend(config_info):
    log.debug("Initializing backend configuration using: {}".format(config_info))

    if "module" not in config_info:
        raise ValueError("No module parameter provided for the TAXII server.")
    if "module_class" not in config_info:
        raise ValueError("No module_class parameter provided for the TAXII server.")

    try:
        module = importlib.import_module(config_info["module"])
        module_class = getattr(module, config_info["module_class"])
        log.debug("Instantiating medallion backend with {}".format(module_class))
        return module_class(**config_info)
    except Exception as e:
        log.error("Unknown backend for TAXII server. {} ".format(str(e)))
        raise e


def init_backend(flask_application_instance, config_info):
    with flask_application_instance.app_context():
        log.debug("Registering medallion_backend into {}".format(current_app))
        current_app.medallion_backend = connect_to_backend(config_info)


@auth.get_password
def get_pwd(username):
    if username in current_app.users_backend:
        return current_app.users_backend.get(username)
    return None


def register_blueprints(flask_application_instance):
    from medallion.views import collections
    from medallion.views import discovery
    from medallion.views import manifest
    from medallion.views import objects

    with flask_application_instance.app_context():
        log.debug("Registering medallion blueprints into {}".format(current_app))
        current_app.register_blueprint(collections.mod)
        current_app.register_blueprint(discovery.mod)
        current_app.register_blueprint(manifest.mod)
        current_app.register_blueprint(objects.mod)


@application_instance.errorhandler(500)
def handle_error(error):
    error = {
        "title": error.args[0],
        "http_status": "500"
    }
    return Response(response=flask.json.dumps(error),
                    status=500,
                    mimetype=MEDIA_TYPE_STIX_V20)
