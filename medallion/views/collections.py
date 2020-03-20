from flask import Blueprint, Response, current_app, json

from . import (
    MEDIA_TYPE_TAXII_V20, validate_taxii_version_parameter_in_accept_header
)
from .. import auth
from ..exceptions import ProcessingError
from .discovery import api_root_exists
from .objects import (
    collection_exists, get_range_request_from_headers,
    get_response_status_and_headers
)

collections_bp = Blueprint("collections", __name__)


@collections_bp.route("/<string:api_root>/collections/", methods=["GET"])
@auth.login_required
def get_collections(api_root):
    """
    Defines TAXII API - Collections:
    `Get Collections Section (5.1) <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542734>`__

    Args:
        api_root (str): the base URL of the API Root

    Returns:
        collections: A Collections Resource upon successful requests. Additional information `here <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542735>`__.

    """
    # TODO: Check if user has access to the each collection's metadata - unrelated to can_read, can_write attributes
    validate_taxii_version_parameter_in_accept_header()
    api_root_exists(api_root)

    start_index, end_index = get_range_request_from_headers()
    total_count, result = current_app.medallion_backend.get_collections(api_root, start_index, end_index)
    if result:
        status, headers = get_response_status_and_headers(start_index, total_count, result)
        return Response(
            response=json.dumps({"collections": result}),
            status=status,
            headers=headers,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("No collections found", 404)


@collections_bp.route("/<string:api_root>/collections/<string:collection_id>/", methods=["GET"])
@auth.login_required
def get_collection(api_root, collection_id):
    """
    Defines TAXII API - Collections:
    `Get Collection Section (5.2) <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542736>`__

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested

    Returns:
        collection: A Collection Resource upon successful requests. Additional information `here <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542737>`__.

    """
    # TODO: Check if user has access to the collection's metadata - unrelated to can_read, can_write attributes
    validate_taxii_version_parameter_in_accept_header()
    api_root_exists(api_root)
    collection_exists(api_root, collection_id)
    collection = current_app.medallion_backend.get_collection(api_root, collection_id)
    if collection:
        return Response(
            response=json.dumps(collection),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("Collection '{}' not found".format(collection_id), 404)
