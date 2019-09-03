from collections import OrderedDict
from datetime import datetime, timedelta
import importlib
import json
import logging
import random

from flask import Flask, Response, current_app, g
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth, MultiAuth
import jwt
from werkzeug.security import check_password_hash

from .exceptions import BackendError, ProcessingError
from .log import default_request_formatter
from .version import __version__  # noqa
from .views import MEDIA_TYPE_TAXII_V20

# Console Handler for medallion messages
ch = logging.StreamHandler()
ch.setFormatter(default_request_formatter())

# Module-level logger
log = logging.getLogger(__name__)
log.addHandler(ch)

jwt_auth = HTTPTokenAuth(scheme='JWT')
basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth(scheme='Token')
auth = MultiAuth(None)

DEFAULT_TAXII = {'max_page_size': 100}

DEFAULT_AUTH = {
    "module": "medallion.backends.auth_memory_backend",
    "module_class": "AuthMemoryBackend",
    "users": {
        "admin": "pbkdf2:sha256:150000$vhWiAWXq$a16882c2eaf4dbb5c55566c93ec256c189ebce855b0081f4903f09a23e8b2344"
    },
    "api_keys": {
        "123456": "admin",
    }
}

DEFAULT_BACKEND = {
    "module": "medallion.backends.memory_backend",
    "module_class": "MemoryBackend",
    "filename": "./medallion/test/data/memory_backend_no_data.json"
}


def set_multi_auth_config(main_auth, *additional_auth):
    type_to_app = {
        'jwt': jwt_auth,
        'api_key': token_auth,
        'basic': basic_auth
    }

    auth.main_auth = type_to_app[main_auth]
    additional_auth = [a for a in additional_auth if a != main_auth]
    auth.additional_auth = tuple(type_to_app[a] for a in tuple(OrderedDict.fromkeys(additional_auth)))


def set_auth_config(flask_application_instance, config_info):
    with flask_application_instance.app_context():
        log.debug("Registering medallion users configuration into {}".format(current_app))
        flask_application_instance.auth_backend = connect_to_backend(config_info)


def set_taxii_config(flask_application_instance, config_info):
    with flask_application_instance.app_context():
        log.debug("Registering medallion taxii configuration into {}".format(current_app))
        flask_application_instance.taxii_config = config_info


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


def set_backend_config(flask_application_instance, config_info):
    with flask_application_instance.app_context():
        log.debug("Registering medallion_backend into {}".format(current_app))
        current_app.medallion_backend = connect_to_backend(config_info)


def register_blueprints(app):
    from medallion.views import collections
    from medallion.views import discovery
    from medallion.views import manifest
    from medallion.views import objects
    from medallion.views.auth import auth_bp
    from medallion.views.healthcheck import healthecheck_bp

    log.debug("Registering medallion blueprints into {}".format(app))
    app.register_blueprint(collections.mod)
    app.register_blueprint(discovery.mod)
    app.register_blueprint(manifest.mod)
    app.register_blueprint(objects.mod)
    app.register_blueprint(auth_bp)
    app.register_blueprint(healthecheck_bp)


def handle_error(error):
    e = {
        "title": "InternalError",
        "http_status": "500",
        "description": str(error),
    }
    return Response(
        response=json.dumps(e),
        status=500,
        mimetype=MEDIA_TYPE_TAXII_V20,
    )


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
        mimetype=MEDIA_TYPE_TAXII_V20,
    )


def handle_backend_error(error):
    e = {
        "title": str(error.__class__.__name__),
        "http_status": str(error.status),
        "description": str(error),
    }
    return Response(
        response=json.dumps(e),
        status=error.status,
        mimetype=MEDIA_TYPE_TAXII_V20,
    )


def register_error_handlers(app):
    app.register_error_handler(500, handle_error)
    app.register_error_handler(ProcessingError, handle_processing_error)
    app.register_error_handler(BackendError, handle_backend_error)


def jwt_encode(username):
    exp = datetime.utcnow() + timedelta(minutes=int(current_app.config.get("JWT_EXP", 60)))
    payload = {
        'exp': exp,
        'user': username
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def jwt_decode(token):
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])


@jwt_auth.verify_token
def verify_token(token):
    current_dt = datetime.utcnow()
    try:
        decoded_token = jwt_decode(token)
        is_authorized = datetime.utcfromtimestamp(float(decoded_token['exp'])) > current_dt
        if is_authorized:
            g.user = decoded_token['user']
    except jwt.exceptions.InvalidTokenError:
        is_authorized = False

    return is_authorized


@basic_auth.verify_password
def verify_basic_auth(username, password):
    password_hash = current_app.auth_backend.get_password_hash(username)
    g.user = username
    return False if password_hash is None else check_password_hash(password_hash, password)


@token_auth.verify_token
def api_key_auth(api_key):
    user = current_app.auth_backend.get_username_for_api_key(api_key)
    if not user:
        return False
    g.user = user
    return True


def set_trace_id():
    g.trace_id = "{:08x}".format(random.randrange(0, 0x100000000))


def log_after_request(response):
    current_app.logger.info(response.status)
    return response


class TaxiiFlask(Flask):
    def __init__(self, *args, **kwargs):
        super(TaxiiFlask, self).__init__(*args, **kwargs)
        self.auth_backend = None
        self.taxii_config = None


def create_app(cfg):
    app = TaxiiFlask(__name__)

    if isinstance(cfg, dict):
        configuration = cfg
    else:
        with open(cfg, "r") as f:
            configuration = json.load(f)

    app.config.from_mapping(**configuration.get('flask', {}))

    app.logger = logging.getLogger('medallion-app')
    app.logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(default_request_formatter())
    app.logger.addHandler(handler)

    if not app.debug:
        # Shut up the werkzeug logger unless debugging.
        logging.getLogger('werkzeug').setLevel(logging.CRITICAL)

    _ = app.before_request(set_trace_id)
    _ = app.after_request(log_after_request)

    set_multi_auth_config(*configuration.get('multi-auth', ('basic',)))

    set_auth_config(app, configuration.get("auth", DEFAULT_AUTH))

    if "auth" not in configuration:
        log.warning("You did not give user information in your config.")
        log.warning("We are giving you the default user information of:")
        log.warning("  User = admin")
        log.warning("  Pass = Password0")

    set_taxii_config(app, configuration.get("taxii", DEFAULT_TAXII))

    set_backend_config(app, configuration.get("backend", DEFAULT_BACKEND))

    if "backend" not in configuration:
        log.warning("You did not give backend information in your config.")
        log.warning("We are giving medallion the default settings,")
        log.warning("which includes a data file of 'data_for_memory_config.json'.")
        log.warning("This file is included in the 'example_configs' directory.")

    register_blueprints(app)
    register_error_handlers(app)

    return app
