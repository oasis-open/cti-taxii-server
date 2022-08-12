from functools import wraps
import logging
import os

import flask
from werkzeug.security import check_password_hash

import medallion
from medallion import connect_to_backend, register_blueprints, set_config
from medallion.common import (
    APPLICATION_INSTANCE, get_application_instance_config_values
)
import medallion.config
from medallion.scripts.cert_auth_gunicorn import ClientAuthApplication

log = logging.getLogger("medallion")


class CertAuth(object):

    def login_required(self, f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            username = flask.request.headers.get('X-USER')
            stored_password = medallion.get_pwd(username)
            client_password = flask.request.headers.get('X-PASS')
            if not check_password_hash(stored_password, client_password):
                raise medallion.exceptions.BackendError("Unauthorized", 401)

            return f(*args, **kwargs)
        return decorated_function


medallion.auth = CertAuth()


def getApp():
    # Gunicorn messes up argparse, so only use env vars
    # use one or the other, not both
    configuration = medallion.config.load_config(
        os.environ.get(
            "MEDALLION_CONFFILE", medallion.config.DEFAULT_CONFFILE
        ),
        os.environ.get(
            "MEDALLION_CONFDIR", medallion.config.DEFAULT_CONFDIR
        ),
    )

    ca_path = configuration.get('ca_path')
    cert_path = configuration.get('cert_path')
    key_path = configuration.get('key_path')
    host = configuration.get('host')
    port = configuration.get('port')

    set_config(APPLICATION_INSTANCE, "users", configuration)
    set_config(APPLICATION_INSTANCE, "taxii", configuration)
    set_config(APPLICATION_INSTANCE, "backend", configuration)

    APPLICATION_INSTANCE.medallion_backend = connect_to_backend(get_application_instance_config_values(APPLICATION_INSTANCE, "backend"))
    if (not APPLICATION_INSTANCE.blueprints):
        register_blueprints(APPLICATION_INSTANCE)

    app = ClientAuthApplication(
        APPLICATION_INSTANCE,
        ca_path,
        cert_path,
        key_path,
        host,
        port,
    )
    return app.application


if __name__ == "__main__":
    getApp().run()
