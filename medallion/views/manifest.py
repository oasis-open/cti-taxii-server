from flask import Blueprint, Response, current_app, json, request

from . import MEDIA_TYPE_TAXII_V21, validate_version_parameter_in_accept_header
from .. import auth
from .discovery import api_root_exists
from .objects import (collection_exists, permission_to_read,
                      validate_limit_parameter)

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:collection_id>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, collection_id):
    """
    Defines TAXII API - Collections:
    Get Object Manifests section (5.3) `here <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107537>`__

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested

    Returns:
        manifest: A Manifest Resource upon successful requests. Additional information
        `here <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107538>`__.

    """
    validate_version_parameter_in_accept_header()
    api_root_exists(api_root)
    collection_exists(api_root, collection_id)
    permission_to_read(api_root, collection_id)

    limit = validate_limit_parameter()
    manifests, headers = current_app.medallion_backend.get_object_manifest(
        api_root, collection_id, request.args.to_dict(), ("id", "type", "version", "spec_version"), limit
    )

    return Response(
        response=json.dumps(manifests),
        status=200,
        headers=headers,
        mimetype=MEDIA_TYPE_TAXII_V21,
    )
