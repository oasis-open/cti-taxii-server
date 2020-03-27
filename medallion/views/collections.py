from flask import Blueprint, Response, current_app, json

from . import MEDIA_TYPE_TAXII_V21, validate_version_parameter_in_accept_header
from .. import auth
from .discovery import api_root_exists
from .objects import collection_exists

collections_bp = Blueprint("collections", __name__)


@collections_bp.route("/<string:api_root>/collections/", methods=["GET"])
@auth.login_required
def get_collections(api_root):
    """
    Defines TAXII API - Collections:
    Get Collection section (5.1) `here <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107533>`__

    Args:
        api_root (str): the base URL of the API Root

    Returns:
        collections: A Collections Resource upon successful requests. Additional information
        `here <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107534>`__.

    """
    # TODO: Check if user has access to the each collection's metadata - unrelated to can_read, can_write attributes

    validate_version_parameter_in_accept_header()
    api_root_exists(api_root)
    collections = current_app.medallion_backend.get_collections(api_root)
    return Response(
        response=json.dumps(collections),
        status=200,
        mimetype=MEDIA_TYPE_TAXII_V21,
    )


@collections_bp.route("/<string:api_root>/collections/<string:collection_id>/", methods=["GET"])
@auth.login_required
def get_collection(api_root, collection_id):
    """
    Defines TAXII API - Collections:
    Get Collection section (5.2) `here <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107535>`__

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested

    Returns:
        collection: A Collection Resource upon successful requests. Additional information
        `here <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107536>`__.

    """
    # TODO: Check if user has access to the collection's metadata - unrelated to can_read, can_write attributes

    validate_version_parameter_in_accept_header()
    api_root_exists(api_root)
    collection_exists(api_root, collection_id)
    collection = current_app.medallion_backend.get_collection(api_root, collection_id)

    return Response(
        response=json.dumps(collection),
        status=200,
        mimetype=MEDIA_TYPE_TAXII_V21,
    )
