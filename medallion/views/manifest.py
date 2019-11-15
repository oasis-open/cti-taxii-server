from flask import Blueprint, Response, current_app, json, request

from . import MEDIA_TYPE_TAXII_V21
from .. import auth
from ..exceptions import ProcessingError
from .objects import (collection_exists, permission_to_read,
                      validate_limit_parameter)

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:collection_id>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, collection_id):
    """
    Defines TAXII API - Collections:
    Get Object Manifests section (5.3) <link here>`__

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested

    Returns:
        manifest: A Manifest Resource upon successful requests. Additional information here <link here>`__.

    """
    if collection_exists(api_root, collection_id) and permission_to_read(api_root, collection_id):
        limit = validate_limit_parameter()
        manifests, headers = current_app.medallion_backend.get_object_manifest(
            api_root, collection_id, request.args, ("id", "type", "version", "spec_version"), limit
        )
        if manifests:
            return Response(
                response=json.dumps(manifests),
                status=200,
                headers=headers,
                mimetype=MEDIA_TYPE_TAXII_V21,
            )
        raise ProcessingError("Collection '{}' has no manifests available".format(collection_id), 404)
