import flask
from flask import Blueprint, Response, abort

from medallion import auth, get_backend
from medallion.views import MEDIA_TYPE_TAXII_V20

mod = Blueprint('discovery', __name__)


@mod.route("/taxii/", methods=["GET"])
@auth.login_required
def server_discovery():
    # Having access to the discovery method is only related to having a credentials on the server
    # The metadata returned might be different depending upon the credentials

    return Response(response=flask.json.dumps(get_backend().server_discovery()), status=200, mimetype=MEDIA_TYPE_TAXII_V20)


@mod.route("/<string:api_root>/", methods=["GET"])
@auth.login_required
def get_api_root_information(api_root):
    # TODO: Check if user has access to objects in collection.

    root_info = get_backend().get_api_root_information(api_root)

    if root_info:
        return Response(response=flask.json.dumps(root_info), status=200, mimetype=MEDIA_TYPE_TAXII_V20)
    abort(404)


@mod.route("/<string:api_root>/status/<string:id_>/", methods=["GET"])
@auth.login_required
def get_status(api_root, id_):
    # TODO: Check if user has access to objects in collection.
    status = get_backend().get_status(api_root, id_)

    if status:
        return Response(response=flask.json.dumps(status), status=200, mimetype=MEDIA_TYPE_TAXII_V20)
    abort(404)
