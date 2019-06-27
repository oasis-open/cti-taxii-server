import flask
from flask import Blueprint, Response, abort, current_app, request

from medallion import auth
from medallion.views import MEDIA_TYPE_TAXII_V20
from medallion.views.objects import collection_exists, permission_to_read

mod = Blueprint("manifest", __name__)


@mod.route("/<string:api_root>/collections/<string:id_>/manifest/", methods=["GET"])
@auth.login_required
def get_object_manifest(api_root, id_):

    if not collection_exists(api_root, id_):
        abort(404)

    if not permission_to_read(api_root, id_):
        abort(403)

    manifest = current_app.medallion_backend.get_object_manifest(api_root, id_, request.args, ("id", "type", "version"))

    if manifest:
        times = []
        for obj in manifest:
            times.append(str(obj['date_added']))
        times.sort()
        response = Response(response=flask.json.dumps({"objects": manifest}),
                            status=200,
                            mimetype=MEDIA_TYPE_TAXII_V20)
        if len(times) > 0:
            response.headers['X-TAXII-Date-Added-First'] = times[0]
            response.headers['X-TAXII-Date-Added-Last'] = times[-1]
        return response
    abort(404)
