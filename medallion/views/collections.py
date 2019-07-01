import flask
from flask import Blueprint, Response, abort, current_app, request

from medallion import auth
from medallion.views import MEDIA_TYPE_TAXII_V20
from medallion.views.objects import (get_range_request_from_headers,
                                     get_response_status_and_headers)

mod = Blueprint('collections', __name__)


@mod.route("/<string:api_root>/collections/", methods=["GET"])
@auth.login_required
def get_collections(api_root):
    # TODO: Check if user has access to the each collection's metadata - unrelated to can_read, can_write attributes
    start_index, end_index = get_range_request_from_headers(request)
    total_count, result = current_app.medallion_backend.get_collections(api_root, start_index, end_index)
    if result:
        status, headers = get_response_status_and_headers(start_index, total_count, result)
        return Response(response=flask.json.dumps({"collections": result}),
                        status=status,
                        mimetype=MEDIA_TYPE_TAXII_V20,
                        headers=headers)
    abort(404)


@mod.route("/<string:api_root>/collections/<string:id_>/", methods=["GET"])
@auth.login_required
def get_collection(api_root, id_):
    # TODO: Check if user has access to the collection's metadata - unrelated to can_read, can_write attributes
    collection = current_app.medallion_backend.get_collection(api_root, id_)
    if collection:
        return Response(response=flask.json.dumps(collection), status=200, mimetype=MEDIA_TYPE_TAXII_V20)
    abort(404)
