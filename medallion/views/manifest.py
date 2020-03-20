from flask import Blueprint, Response, current_app, json, request

from . import MEDIA_TYPE_TAXII_V20
from .. import auth
from ..exceptions import ProcessingError
from .objects import (collection_exists, get_custom_headers,
                      get_range_request_from_headers,
                      get_response_status_and_headers, permission_to_read)

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:collection_id>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, collection_id):
    """
    Defines TAXII API - Collections:
    `Get Object Manifests Section (5.6) <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542741>`__

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested

    Returns:
        manifest: A Manifest Resource upon successful requests. Additional information `here <http://docs.oasis-open.org/cti/taxii/v2.0/cs01/taxii-v2.0-cs01.html#_Toc496542742>`__.

    """
    validate_taxii_version_parameter_in_accept_header()

    if collection_exists(api_root, collection_id) and permission_to_read(api_root, collection_id):
        start_index, end_index = get_range_request_from_headers()
        total_count, manifest = current_app.medallion_backend.get_object_manifest(
            api_root, collection_id, request.args, ("id", "type", "version"), start_index, end_index,
        )
        if manifest:
            status, headers = get_response_status_and_headers(start_index, total_count, manifest)
            headers = get_custom_headers(headers, api_root, collection_id, start_index, end_index)
            return Response(
                response=json.dumps({"objects": manifest}),
                status=status,
                headers=headers,
                mimetype=MEDIA_TYPE_TAXII_V20,
            )
        raise ProcessingError("Collection '{}' has no manifests available".format(collection_id), 404)
