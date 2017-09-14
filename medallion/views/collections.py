import flask
from flask import Blueprint, Response, abort

from medallion import auth, get_backend
from medallion.views import MEDIA_TYPE_TAXII_V20

mod = Blueprint('collections', __name__)


@mod.route("/<string:api_root>/collections/", methods=["GET"])
@auth.login_required
def get_collections(api_root):
    # TODO: Check if user has access to the each collection's metadata - unrelated to can_read, can_write attributes
    result = get_backend().get_collections(api_root)

    if result:
        return Response(response=flask.json.dumps(result), status=200, mimetype=MEDIA_TYPE_TAXII_V20)
    abort(404)


@mod.route("/<string:api_root>/collections/<string:id_>/", methods=["GET"])
@auth.login_required
def get_collection(api_root, id_):
    # TODO: Check if user has access to the collection's metadata - unrelated to can_read, can_write attributes

    collection = get_backend().get_collection(api_root, id_)
    if collection:
        return Response(response=flask.json.dumps(collection), status=200, mimetype=MEDIA_TYPE_TAXII_V20)
    abort(404)
