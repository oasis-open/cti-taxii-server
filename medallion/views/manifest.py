import flask
from flask import Blueprint, Response, abort, current_app, request

from medallion import auth
from medallion.views import MEDIA_TYPE_TAXII_V20, FILTERS

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:id_>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, id_):
    # TODO: Check if user has access to objects in collection.
    manifest = current_app.medallion_backend.get_object_manifest(api_root, id_, request.args, FILTERS)

    if manifest:
        return Response(response=flask.json.dumps({"objects": manifest}),
                        status=200,
                        mimetype=MEDIA_TYPE_TAXII_V20)
    abort(404)
