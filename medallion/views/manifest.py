import flask
from flask import Blueprint, Response, abort, request

from medallion import auth, get_backend
from medallion.views import MEDIA_TYPE_TAXII_V20

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:id_>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, id_):
    # TODO: Check if user has access to objects in collection.

    manifest = get_backend().get_object_manifest(api_root, id_, request.args, ("id", "type", "version"))
    if manifest:
        return Response(response=flask.json.dumps({"objects": manifest}),
                        status=200,
                        mimetype=MEDIA_TYPE_TAXII_V20)
    abort(404)
