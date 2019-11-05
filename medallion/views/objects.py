import logging

from flask import Blueprint, Response, current_app, json, request

from . import MEDIA_TYPE_TAXII_V21
from .. import auth
from ..exceptions import ProcessingError
from ..utils.common import format_datetime, get_timestamp

mod = Blueprint("objects", __name__)

# Module-level logger
log = logging.getLogger(__name__)


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


def get_custom_headers(api_root, id_):
    headers = {}
    try:
        manifest = current_app.medallion_backend.get_object_manifest(
            api_root, id_, request.args, ("id",),
        )
        if manifest:
            times = sorted(map(lambda x: x["date_added"], manifest["objects"]))
            if len(times) > 0:
                headers["X-TAXII-Date-Added-First"] = times[0]
                headers["X-TAXII-Date-Added-Last"] = times[-1]
    except Exception as e:
        log.exception(e)
    return headers


@mod.route("/<string:api_root>/collections/<string:collection_id>/objects/", methods=["GET", "POST"])
@auth.login_required
def get_or_add_objects(api_root, collection_id):
    """
    Defines TAXII API - Collections:
    Get Objects section (5.4 <link here>`__) and Add Objects section (5.5 <link here>`__)

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested

    Returns:
        resource:
            GET -> An Envelope Resource upon successful requests. Additional information here <link here>`__.
            POST -> An Status Resource upon successful requests. Additional information here <link here>`__.

    """
    # TODO: Check if user has access to read or write objects in collection - right now just check for permissions on the collection.
    request_time = format_datetime(get_timestamp())  # Can't I get this from the request itself?
    if collection_exists(api_root, collection_id):
        if request.method == "GET" and permission_to_read(api_root, collection_id):
            objects = current_app.medallion_backend.get_objects(
                api_root, collection_id, request.args, ("id", "type", "version", "spec_version"),
            )
            if objects:
                headers = get_custom_headers(api_root, collection_id)
                return Response(
                    response=json.dumps(objects),
                    status=200,
                    headers=headers,
                    mimetype=MEDIA_TYPE_TAXII_V21,
                )
            raise ProcessingError("Collection '{}' has no objects available".format(collection_id), 404)
        elif request.method == "POST" and permission_to_write(api_root, collection_id):
            status = current_app.medallion_backend.add_objects(
                api_root, collection_id, request.get_json(force=True), request_time
            )
            return Response(
                response=json.dumps(status),
                status=202,
                mimetype=MEDIA_TYPE_TAXII_V21,
            )


@mod.route("/<string:api_root>/collections/<string:collection_id>/objects/<string:object_id>/", methods=["GET", "DELETE"])
@auth.login_required
def get_or_delete_object(api_root, collection_id, object_id):
    """
    Defines TAXII API - Collections:
    Get Object section (5.6 <link here>`__) and Delete Object section (5.7 <link here>`__)

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested
        object_id (str): the `identifier` of the object being requested

    Returns:
        resource:
            GET -> An Envelope Resource upon successful requests. Additional information here <link here>`__.
            DELETE -> Upon successful request nothing (status code 200).

    """
    # TODO: Check if user has access to read or write objects in collection - right now just check for permissions on the collection.

    if collection_exists(api_root, collection_id):
        if request.method == "GET" and permission_to_read(api_root, collection_id):
            objects = current_app.medallion_backend.get_object(
                api_root, collection_id, object_id, request.args, ("version", "spec_version"),
            )
            if objects:
                headers = get_custom_headers(api_root, collection_id)
                return Response(
                    response=json.dumps(objects),
                    status=200,
                    headers=headers,
                    mimetype=MEDIA_TYPE_TAXII_V21,
                )
            raise ProcessingError("Object '{}' not found".format(object_id), 404)
        elif request.method == "DELETE" and permission_to_read(api_root, collection_id) and \
                permission_to_write(api_root, collection_id):
            current_app.medallion_backend.delete_object(
                api_root, collection_id, object_id, request.args, ("version", "spec_version"),
            )
            return Response(
                status=200,
                mimetype=MEDIA_TYPE_TAXII_V21,
            )


@mod.route("/<string:api_root>/collections/<string:collection_id>/objects/<string:object_id>/versions/", methods=["GET"])
@auth.login_required
def get_object_versions(api_root, collection_id, object_id):
    """
    Defines TAXII API - Collections: Get Object Versions section (5.8) <link here>`__.

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested
        object_id (str): the `identifier` of the object being requested

    Returns:
        versions: A Versions Resource upon successful requests. Additional information here <link here>`__.

    """
    # TODO: Check if user has access to read objects in collection - right now just check for permissions on the collection.

    if collection_exists(api_root, collection_id) and permission_to_read(api_root, collection_id):
        versions = current_app.medallion_backend.get_object_versions(
            api_root, collection_id, object_id, request.args, ("spec_version",),
        )
        headers = get_custom_headers(api_root, collection_id)
        return Response(
            response=json.dumps(versions),
            status=200,
            headers=headers,
            mimetype=MEDIA_TYPE_TAXII_V21,
        )
