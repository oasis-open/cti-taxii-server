import importlib
import logging
import warnings

from flask import Flask, Response, current_app, json
from flask_httpauth import HTTPBasicAuth

from .backends import base as mbe_base
from .exceptions import BackendError, ProcessingError
from .version import __version__  # noqa
from .views import MEDIA_TYPE_TAXII_V21

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
            try:
                flask_application_instance.taxii_config = config[prop_name]
            except KeyError:
                flask_application_instance.taxii_config = {'max_page_size': 100}
        elif prop_name == "users":
            try:
                flask_application_instance.users_backend = config[prop_name]
            except KeyError:
                log.warning("You did not give user information in your config.")
                log.warning("We are giving you the default user information of:")
                log.warning("User = user")
                log.warning("Pass = pass")
                flask_application_instance.users_backend = {"user": "pass"}
        elif prop_name == "backend":
            try:
                flask_application_instance.medallion_backend = connect_to_backend(config[prop_name])
            except KeyError:
                log.warning("You did not give backend information in your config.")
                log.warning("We are giving medallion the default settings,")
                log.warning("which includes a data file of 'default_data.json'.")
                log.warning("Please ensure this file is in your CWD.")
                back = {'module': 'medallion.backends.memory_backend', 'module_class': 'MemoryBackend', 'filename': None}
                flask_application_instance.medallion_backend = connect_to_backend(back)


def connect_to_backend(config_info):
    log.debug("Initializing backend configuration using: {}".format(config_info))

    try:
        backend_cls_name = config_info["module_class"]
    except KeyError:
        raise ValueError("No module_class parameter provided for the TAXII server.")

    try:
        backend_mod_name = config_info["module"]
    except KeyError:
        # Handle configurations which only specify a backend class name
        try:
            backend_cls = mbe_base.BackendRegistry.get(backend_cls_name)
        except KeyError as exc:
            msg = "Unknown backend {!r}".format(backend_cls_name)
            log.error(msg)
            raise ValueError(msg) from exc
    else:
        # Handle configurations which specify a module to load
        warnings.warn(
            "Backend module paths in configuration will be removed in future. "
            "Simply use the backend class name in 'module_class' for builtin "
            "backend implementations.",
            DeprecationWarning
        )
        try:
            backend_mod = importlib.import_module(backend_mod_name)
            backend_cls = getattr(backend_mod, backend_cls_name)
        except (ImportError, AttributeError) as exc:
            log.error(
                "Failed to load backend %r from %r",
                backend_cls_name, backend_mod_name,
            )
            raise exc
        else:
            log.debug(
                "Instantiating medallion backend with %r from %r",
                backend_cls_name, backend_mod_name,
            )

    # Finally, instantiate the backend class with the configuration passed in
    try:
        return backend_cls(**config_info)
    except BaseException as exc:
        log.error("Failed to instantiate %r: %s", backend_cls_name, exc)
        raise exc


def register_blueprints(flask_application_instance):
    from medallion.views import collections, discovery, manifest, objects

    with flask_application_instance.app_context():
        log.debug("Registering medallion blueprints into {}".format(current_app))
        current_app.register_blueprint(collections.collections_bp)
        current_app.register_blueprint(discovery.discovery_bp)
        current_app.register_blueprint(manifest.manifest_bp)
        current_app.register_blueprint(objects.objects_bp)


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
        "description": str(error.args[0]),
    }
    return Response(
        response=json.dumps(e),
        status=500,
        mimetype=MEDIA_TYPE_TAXII_V21,
    )


@application_instance.errorhandler(ProcessingError)
def handle_processing_error(error):
    e = {
        "title": str(error.__class__.__name__),
        "http_status": str(error.status),
        "description": str(error),
    }
    return Response(
        response=json.dumps(e),
        status=error.status,
        headers=getattr(error, "headers", None),
        mimetype=MEDIA_TYPE_TAXII_V21,
    )


@application_instance.errorhandler(BackendError)
def handle_backend_error(error):
    e = {
        "title": str(error.__class__.__name__),
        "http_status": str(error.status),
        "description": str(error),
    }
    return Response(
        response=json.dumps(e),
        status=error.status,
        mimetype=MEDIA_TYPE_TAXII_V21,
    )
