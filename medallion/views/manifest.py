import flask
from flask import Blueprint, Response, abort, current_app, request

from medallion import auth
from medallion.views import MEDIA_TYPE_TAXII_V20
from medallion.views.objects import (collection_exists,
                                     get_range_request_from_headers,
                                     get_response_status_and_headers,
                                     permission_to_read)

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:id_>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, id_):

    if not collection_exists(api_root, id_):
        abort(404)

    if not permission_to_read(api_root, id_):
        abort(403)

    start_index, end_index = get_range_request_from_headers(request)
    total_count, manifest = current_app.medallion_backend.get_object_manifest(api_root, id_, request.args, ("id", "type", "version"),
                                                                              start_index, end_index)

    status, headers = get_response_status_and_headers(start_index, total_count, manifest)
    if manifest:
        return Response(response=flask.json.dumps({"objects": manifest}),
                        status=status,
                        mimetype=MEDIA_TYPE_TAXII_V20,
                        headers=headers)
    abort(404)
