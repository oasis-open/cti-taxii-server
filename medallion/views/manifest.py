from flask import Blueprint, Response, current_app, json, request

from medallion import auth
from medallion.exceptions import ProcessingError
from medallion.views import MEDIA_TYPE_TAXII_V20
from medallion.views.objects import (collection_exists,
                                     get_range_request_from_headers,
                                     get_response_status_and_headers,
                                     permission_to_read)

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:id_>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, id_):

    if collection_exists(api_root, id_) and permission_to_read(api_root, id_):
        start_index, end_index = get_range_request_from_headers()
        total_count, manifest = current_app.medallion_backend.get_object_manifest(
            api_root, id_, request.args, ("id", "type", "version"), start_index, end_index
        )
        status, headers = get_response_status_and_headers(start_index, total_count, manifest)
        if manifest:
            return Response(
                response=json.dumps({"objects": manifest}),
                status=status,
                headers=headers,
                mimetype=MEDIA_TYPE_TAXII_V20,
            )
        raise ProcessingError("Collection '{}' has no manifests available".format(id_), 404)
