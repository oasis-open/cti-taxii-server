from flask import Blueprint, Response, current_app, json

from . import MEDIA_TYPE_TAXII_V20
from .. import auth
from ..exceptions import ProcessingError

mod = Blueprint("discovery", __name__)


@mod.route("/taxii/", methods=["GET"])
@auth.login_required
def get_server_discovery():
    # Having access to the discovery method is only related to having
    # credentials on the server. The metadata returned might be different
    # depending upon the credentials.
    server_discovery = current_app.medallion_backend.server_discovery()

    if server_discovery:
        return Response(
            response=json.dumps(server_discovery),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("Server discovery information not available", 404)


@mod.route("/<string:api_root>/", methods=["GET"])
@auth.login_required
def get_api_root_information(api_root):
    # TODO: Check if user has access to objects in collection.
    root_info = current_app.medallion_backend.get_api_root_information(api_root)

    if root_info:
        return Response(
            response=json.dumps(root_info),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("API root '{}' information not found".format(api_root), 404)


@mod.route("/<string:api_root>/status/<string:id_>/", methods=["GET"])
@auth.login_required
def get_status(api_root, id_):
    # TODO: Check if user has access to the Status resource.
    status = current_app.medallion_backend.get_status(api_root, id_)

    if status:
        return Response(
            response=json.dumps(status),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("Status '{}' not found".format(id_), 404)
