from flask import Blueprint, Response, current_app, json

from . import MEDIA_TYPE_TAXII_V20
from .. import auth
from ..exceptions import ProcessingError
from .objects import (get_range_request_from_headers,
                      get_response_status_and_headers)

mod = Blueprint("collections", __name__)


@mod.route("/<string:api_root>/collections/", methods=["GET"])
@auth.login_required
def get_collections(api_root):
    # TODO: Check if user has access to the each collection's metadata - unrelated to can_read, can_write attributes
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


@mod.route("/<string:api_root>/collections/<string:collection_id>/", methods=["GET"])
@auth.login_required
def get_collection(api_root, collection_id):
    # TODO: Check if user has access to the collection's metadata - unrelated to can_read, can_write attributes
    collection = current_app.medallion_backend.get_collection(api_root, collection_id)
    if collection:
        return Response(
            response=json.dumps(collection),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V20,
        )
    raise ProcessingError("Collection '{}' not found".format(collection_id), 404)
