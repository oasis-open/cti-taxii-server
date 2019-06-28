import importlib
import logging

from flask import Flask, Response, current_app, json
from flask_httpauth import HTTPBasicAuth

from medallion.exceptions import BackendError, ProcessingError
from medallion.version import __version__  # noqa
from medallion.views import MEDIA_TYPE_TAXII_V20

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

    set_config(application_instance, "users", configuration)
    set_config(application_instance, "taxii", configuration)
    set_config(application_instance, "backend", configuration)
    register_blueprints(application_instance)

    return application_instance


def set_config(flask_application_instance, prop_name, config):
    with flask_application_instance.app_context():
        log.debug("Registering medallion {} configuration into {}".format(prop_name, current_app))
        if prop_name == "taxii":
            flask_application_instance.taxii_config = config[prop_name]
        elif prop_name == "users":
            flask_application_instance.users_backend = config[prop_name]
        elif prop_name == "backend":
            flask_application_instance.medallion_backend = connect_to_backend(config[prop_name])


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


@auth.get_password
def get_pwd(username):
    if username in current_app.users_backend:
        return current_app.users_backend.get(username)
    return None


@application_instance.errorhandler(500)
def handle_error(error):
    e = {
        "title": "InternalError",
        "http_status": "500",
        "description": str(error.args[0])
    }
    return Response(
        response=json.dumps(e),
        status=500,
        mimetype=MEDIA_TYPE_TAXII_V20
    )


@application_instance.errorhandler(ProcessingError)
def handle_processing_error(error):
    e = {
        "title": str(error.__class__.__name__),
        "http_status": str(error.status),
        "description": str(error)
    }
    return Response(
        response=json.dumps(e),
        status=error.status,
        headers=getattr(error, "headers", None),
        mimetype=MEDIA_TYPE_TAXII_V20
    )


@application_instance.errorhandler(BackendError)
def handle_backend_error(error):
    e = {
        "title": str(error.__class__.__name__),
        "http_status": str(error.status),
        "description": str(error)
    }
    return Response(
        response=json.dumps(e),
        status=error.status,
        mimetype=MEDIA_TYPE_TAXII_V20
    )
