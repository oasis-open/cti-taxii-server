import flask
from flask import Blueprint, Response, abort, current_app, request

from medallion import auth
from medallion.exceptions import ProcessingError
from medallion.utils import common
from medallion.views import MEDIA_TYPE_STIX_V20, MEDIA_TYPE_TAXII_V20

mod = Blueprint("objects", __name__)


def permission_to_read(api_root, collection_id):
    collection_info = current_app.medallion_backend.get_collection(api_root, collection_id)
    return collection_info["can_read"]


def permission_to_write(api_root, collection_id):
    collection_info = current_app.medallion_backend.get_collection(api_root, collection_id)
    return collection_info["can_write"]


def collection_exists(api_root, collection_id):
    if current_app.medallion_backend.get_collection(api_root, collection_id):
        return True
    return False


@mod.route("/<string:api_root>/collections/<string:id_>/objects/", methods=["GET", "POST"])
@auth.login_required
def get_or_add_objects(api_root, id_):
    # TODO: Check if user has access to read or write objects in collection - right now just check for permissions on the collection.

    if not collection_exists(api_root, id_):
        abort(404)

    if request.method == "GET":
        if permission_to_read(api_root, id_):
            objects = current_app.medallion_backend.get_objects(api_root, id_, request.args, ("id", "type", "version"))
            if objects:
                return Response(response=flask.json.dumps(objects),
                                status=200,
                                mimetype=MEDIA_TYPE_STIX_V20)
            else:
                abort(404)
        else:
            abort(403)
    elif request.method == "POST":
        if permission_to_write(api_root, id_):
            # Can't I get this from the request itself?
            request_time = common.format_datetime(common.get_timestamp())
            try:
                status = current_app.medallion_backend.add_objects(api_root, id_, request.get_json(force=True), request_time)
            except ProcessingError as e:
                abort(422)

            return Response(response=flask.json.dumps(status),
                            status=202,
                            mimetype=MEDIA_TYPE_TAXII_V20)
        else:
            abort(403)


@mod.route("/<string:api_root>/collections/<string:id_>/objects/<string:object_id>/", methods=["GET"])
@auth.login_required
def get_object(api_root, id_, object_id):
    # TODO: Check if user has access to objects in collection - right now just check for permissions on the collection

    if not collection_exists(api_root, id_):
        abort(404)

    if permission_to_read(api_root, id_):
        objects = current_app.medallion_backend.get_object(api_root, id_, object_id, request.args, ("version",))
        if objects:
            return Response(response=flask.json.dumps(objects),
                            status=200,
                            mimetype=MEDIA_TYPE_STIX_V20)
        abort(404)
    else:

        abort(403)
