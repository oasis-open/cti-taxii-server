import re

import flask
from flask import Blueprint, Response, abort, current_app, request

from medallion import auth
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


def get_range_request_from_headers(request):
    if request.headers.get('Range') is not None:
        matches = re.match(r'items (\d+)-(\d+)$', request.headers.get('Range'))
        if matches is None:
            abort(Response('Bad Range header supplied', status=400))
        start_index = int(matches.group(1))
        end_index = int(matches.group(2))
        # check that the requested number of items isn't larger than the maximum support server page size
        # the +1 and -1 below account for the fact that paging is zero index based.
        if (end_index - start_index) + 1 > current_app.taxii_config['max_page_size']:
            end_index = start_index + (current_app.taxii_config['max_page_size'] - 1)
        return start_index, end_index
    else:
        return 0, current_app.taxii_config['max_page_size'] - 1


def get_custom_headers(headers, api_root, id_):
    try:
        manifest = current_app.medallion_backend.get_object_manifest(
            api_root, id_, request.args, ("id",),  0, -1)[1]
        times = []
    except Exception as e:
        print(e)
        manifest = None
    if manifest:
        for obj in manifest:
            if 'date_added' in obj:
                times.append(str(obj['date_added']))
        times.sort()

        if len(times) > 0:
            headers['X-TAXII-Date-Added-First'] = times[0]
            headers['X-TAXII-Date-Added-Last'] = times[-1]
    return headers


def get_response_status_and_headers(start_index, total_count, objects):
    # If the requested range is outside the size of the result set, return a HTTP 416
    if start_index >= total_count and total_count > 0:
        headers = {
            'Accept-Ranges': 'items',
            'Content-Range': 'items */{}'.format(total_count)
        }
        abort(Response(status=416, headers=headers))

    # If no range request was supplied, and we can return the whole result set in one go, then do so.
    if request.headers.get('Range') is None and total_count < current_app.taxii_config['max_page_size']:
        status = 200
        headers = {'Accept-Ranges': 'items'}
    else:
        # The minus one below is due to the fact that the range is zero based
        status = 206
        # This check is required as if the number of objects returned is zero, subtracting one would give us
        # an end index of -1
        if len(objects) == 0:
            end_index = start_index
        else:
            end_index = start_index + (len(objects) - 1)
        headers = {
            'Accept-Ranges': 'items',
            'Content-Range': 'items {}-{}/{}'.format(start_index, end_index, total_count)
        }
    return status, headers


@mod.route("/<string:api_root>/collections/<string:id_>/objects/", methods=["GET", "POST"])
@auth.login_required
def get_or_add_objects(api_root, id_):
    # TODO: Check if user has access to read or write objects in collection - right now just check for permissions on the collection.

    if not collection_exists(api_root, id_):
        abort(404)

    if request.method == "GET":
        if permission_to_read(api_root, id_):
            start_index, end_index = get_range_request_from_headers(request)
            total_count, objects = current_app.medallion_backend.get_objects(api_root, id_, request.args, ("id", "type", "version"),
                                                                             start_index, end_index)

            status, headers = get_response_status_and_headers(
                start_index, total_count, objects['objects'])
            if objects:
                headers = get_custom_headers(headers, api_root, id_)
                return Response(response=flask.json.dumps(objects),
                                status=status,
                                mimetype=MEDIA_TYPE_STIX_V20,
                                headers=headers)
            else:
                abort(404)
        else:
            abort(403)
    elif request.method == "POST":
        if permission_to_write(api_root, id_):
            # Can't I get this from the request itself?
            request_time = common.format_datetime(common.get_timestamp())
            status = current_app.medallion_backend.add_objects(api_root, id_, request.get_json(force=True), request_time)

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
