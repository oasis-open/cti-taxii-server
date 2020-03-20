from flask import Blueprint, Response, current_app, json

from . import MEDIA_TYPE_TAXII_V20
from .. import auth
from ..exceptions import ProcessingError

discovery_bp = Blueprint("discovery", __name__)




@discovery_bp.route("/taxii/", methods=["GET"])
@auth.login_required
def get_server_discovery():
    """
    Defines TAXII API - Server Information:
    `Server Discovery Section (4.1) <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542727>`__

    Returns:
        discovery: A Discovery Resource upon successful requests. Additional information `here <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542728>`__.

    """
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


@discovery_bp.route("/<string:api_root>/", methods=["GET"])
@auth.login_required
def get_api_root_information(api_root):
    """
    Defines TAXII API - Server Information:
    `Get API Root Information Section (4.2) <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542729>`__

    Args:
        api_root (str): the base URL of the API Root

    Returns:
        api-root: An API Root Resource upon successful requests. Additional information `here <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542730>`__.

    """
    # TODO: Check if user has access to objects in collection.
    root_info = current_app.medallion_backend.get_api_root_information(api_root)

    if root_info:
        return Response(
            response=json.dumps(root_info),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("API root '{}' information not found".format(api_root), 404)


@discovery_bp.route("/<string:api_root>/status/<string:status_id>/", methods=["GET"])
@auth.login_required
def get_status(api_root, collection_id):
    # TODO: Check if user has access to the Status resource.
    status = current_app.medallion_backend.get_status(api_root, collection_id)

    if status:
        return Response(
            response=json.dumps(status),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("Status '{}' not found".format(collection_id), 404)
