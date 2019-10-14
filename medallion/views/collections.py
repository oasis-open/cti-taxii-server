from flask import Blueprint, Response, current_app, json

from . import MEDIA_TYPE_TAXII_V21
from .. import auth
from ..exceptions import ProcessingError

mod = Blueprint("collections", __name__)


@mod.route("/<string:api_root>/collections/", methods=["GET"])
@auth.login_required
def get_collections(api_root):
    # TODO: Check if user has access to the each collection's metadata - unrelated to can_read, can_write attributes
    collections = current_app.medallion_backend.get_collections(api_root)
    if collections:
        return Response(
            response=json.dumps(collections),
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V21,
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
            mimetype=MEDIA_TYPE_TAXII_V21,
        )
    raise ProcessingError("Collection '{}' not found".format(collection_id), 404)
