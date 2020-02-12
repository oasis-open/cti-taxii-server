import re

from flask import Blueprint, Response, current_app, json, request

from . import MEDIA_TYPE_STIX_V20, MEDIA_TYPE_TAXII_V20
from .. import auth
from ..exceptions import ProcessingError
from ..utils.common import get_timestamp

mod = Blueprint("objects", __name__)


def permission_to_read(api_root, collection_id):
    collection_info = current_app.medallion_backend.get_collection(api_root, collection_id)
    if collection_info["can_read"]:
        return True
    raise ProcessingError("Forbidden to read collection '{}'".format(collection_id), 403)


def permission_to_write(api_root, collection_id):
    collection_info = current_app.medallion_backend.get_collection(api_root, collection_id)
    if collection_info["can_write"]:
        return True
    raise ProcessingError("Forbidden to write collection '{}'".format(collection_id), 403)


def collection_exists(api_root, collection_id):
    if current_app.medallion_backend.get_collection(api_root, collection_id):
        return True
    raise ProcessingError("Collection '{}' not found".format(collection_id), 404)


def get_range_request_from_headers():
    if request.headers.get("Range") is not None:
        try:
            matches = re.match(r"^items (\d+)-(\d+)$", request.headers.get("Range"))
            start_index = int(matches.group(1))
            end_index = int(matches.group(2))
            # check that the requested number of items isn't larger than the maximum support server page size
            # the +1 and -1 below account for the fact that paging is zero index based.
            if (end_index - start_index) + 1 > current_app.taxii_config["max_page_size"]:
                end_index = start_index + (current_app.taxii_config["max_page_size"] - 1)
            return start_index, end_index
        except (AttributeError, ValueError) as e:
            raise ProcessingError("Bad Range header supplied", 400, e)
    else:
        return 0, current_app.taxii_config["max_page_size"] - 1


def get_custom_headers(headers, api_root, collection_id, start, end):
    try:
        manifest = current_app.medallion_backend.get_object_manifest(
            api_root, collection_id, request.args, ("id",),  start, end)[1]
        if manifest:
            times = sorted(map(lambda x: x["date_added"], manifest))

            if len(times) > 0:
                headers['X-TAXII-Date-Added-First'] = times[0]
                headers['X-TAXII-Date-Added-Last'] = times[-1]
    except Exception as e:
        print(e)
    return headers


def get_response_status_and_headers(start_index, total_count, objects):
    # If the requested range is outside the size of the result set, return a HTTP 416
    if start_index >= total_count > 0:
        error = ProcessingError("The requested range is outside the size of the result set", 416)
        error.headers = {
            "Accept-Ranges": "items",
            "Content-Range": "items */{}".format(total_count),
        }
        raise error

    # If no range request was supplied, and we can return the whole result set in one go, then do so.
    if request.headers.get("Range") is None and total_count < current_app.taxii_config["max_page_size"]:
        status = 200
        headers = {"Accept-Ranges": "items"}
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
            "Accept-Ranges": "items",
            "Content-Range": "items {}-{}/{}".format(start_index, end_index, total_count),
        }
    return status, headers


@mod.route("/<string:api_root>/collections/<string:collection_id>/objects/", methods=["GET", "POST"])
@auth.login_required
def get_or_add_objects(api_root, collection_id):
    # TODO: Check if user has access to read or write objects in collection - right now just check for permissions on the collection.
    request_time = get_timestamp()  # Can't I get this from the request itself?
    if collection_exists(api_root, collection_id):
        if request.method == "GET" and permission_to_read(api_root, collection_id):
            start_index, end_index = get_range_request_from_headers()
            total_count, objects = current_app.medallion_backend.get_objects(
                api_root, collection_id, request.args, ("id", "type", "version"), start_index, end_index,
            )
            if objects:
                status, headers = get_response_status_and_headers(start_index, total_count, objects["objects"])
                headers = get_custom_headers(headers, api_root, collection_id, start_index, end_index)
                return Response(
                    response=json.dumps(objects),
                    status=status,
                    headers=headers,
                    mimetype=MEDIA_TYPE_STIX_V20,
                )
            raise ProcessingError("Collection '{}' has no objects available".format(collection_id), 404)
        elif request.method == "POST" and permission_to_write(api_root, collection_id):
            status = current_app.medallion_backend.add_objects(api_root, collection_id, request.get_json(force=True), request_time)
            return Response(
                response=json.dumps(status),
                status=202,
                mimetype=MEDIA_TYPE_TAXII_V20,
            )


@mod.route("/<string:api_root>/collections/<string:collection_id>/objects/<string:object_id>/", methods=["GET"])
@auth.login_required
def get_object(api_root, collection_id, object_id):
    # TODO: Check if user has access to objects in collection - right now just check for permissions on the collection

    if collection_exists(api_root, collection_id) and permission_to_read(api_root, collection_id):
        objects = current_app.medallion_backend.get_object(api_root, collection_id, object_id, request.args, ("version",))
        if objects:
            return Response(
                response=json.dumps(objects),
                status=200,
                mimetype=MEDIA_TYPE_STIX_V20,
            )
        raise ProcessingError("Object '{}' not found".format(object_id), 404)
