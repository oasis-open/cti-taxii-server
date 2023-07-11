import logging
import re

from flask import Blueprint, Response, current_app, json, request

from . import MEDIA_TYPE_TAXII_V21, validate_version_parameter_in_accept_header
from .. import auth
from ..common import get_timestamp
from ..exceptions import ProcessingError
from .discovery import api_root_exists

objects_bp = Blueprint("objects", __name__)

# Module-level logger
log = logging.getLogger(__name__)


def permission_to_read(api_root, collection_id):
    collection_info = current_app.medallion_backend.get_collection(api_root, collection_id)
    if collection_info["can_read"] is False:
        raise ProcessingError("Forbidden to read collection '{}'".format(collection_id), 403)


def permission_to_write(api_root, collection_id):
    collection_info = current_app.medallion_backend.get_collection(api_root, collection_id)
    if collection_info["can_write"] is False:
        raise ProcessingError("Forbidden to write collection '{}'".format(collection_id), 403)


def permission_to_read_and_write(api_root, collection_id):
    collection_info = current_app.medallion_backend.get_collection(api_root, collection_id)
    if collection_info["can_read"] is False and collection_info["can_write"] is False:
        raise ProcessingError("Collection '{}' not found".format(collection_id), 404)
    if collection_info["can_write"] is False:
        raise ProcessingError("Forbidden to write collection '{}'".format(collection_id), 403)
    if collection_info["can_read"] is False:
        raise ProcessingError("Forbidden to read collection '{}'".format(collection_id), 403)


def collection_exists(api_root, collection_id):
    if not current_app.medallion_backend.get_collection(api_root, collection_id):
        raise ProcessingError("Collection '{}' not found".format(collection_id), 404)


def validate_size_in_request_body(api_root):
    api_root = current_app.medallion_backend.get_api_root_information(api_root)
    max_length = api_root["max_content_length"]
    try:
        content_length = int(request.headers.get("content_length", ""))
    except ValueError:
        raise ProcessingError("The server did not understand the request or headers", 400)
    if content_length > max_length or content_length <= 0:
        raise ProcessingError("Content-Length header not valid or exceeds maximum!", 413)


def validate_version_parameter_in_content_type_header():
    content_type = request.headers.get("content_type", "").replace(" ", "").split(",")
    found = False

    for item in content_type:
        result = re.match(r"^application/taxii\+json(;version=(\d\.\d))?$", item)
        if result:
            if len(result.groups()) >= 2:
                version_str = result.group(2)
                if version_str != "2.1":  # The server only supports 2.1
                    raise ProcessingError("The server does not support version {}".format(version_str), 415)
            found = True
            break

    if found is False:
        raise ProcessingError("Media type in the Content-Type header is invalid or not found", 415)


def validate_limit_parameter():
    max_page = current_app.taxii_config["max_page_size"]
    limit = request.args.get("limit", max_page)
    try:
        limit = int(limit)
    except ValueError:
        raise ProcessingError("The server did not understand the request or filter parameters", 400)
    if limit <= 0:
        raise ProcessingError("The limit parameter cannot be negative or zero", 400)
    if limit > max_page:
        limit = max_page
    return limit


@objects_bp.route("/<string:api_root>/collections/<string:collection_id>/objects/", methods=["GET", "POST"])
@auth.login_required
def get_or_add_objects(api_root, collection_id):
    """
    Defines TAXII API - Collections:
        Get Objects section (`5.4 <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107539>`__)
        and Add Objects section (`5.5 <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107540>`__)

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested

    Returns:
        resource:
            GET -> An Envelope Resource upon successful requests.
            POST -> An Status Resource upon successful requests.

    """
    # TODO: Check if user has access to read or write objects in collection - right now just check for permissions on the collection.
    request_time = get_timestamp()  # Can't I get this from the request itself?
    validate_version_parameter_in_accept_header()
    api_root_exists(api_root)
    collection_exists(api_root, collection_id)

    if request.method == "GET":
        permission_to_read(api_root, collection_id)
        limit = validate_limit_parameter()
        objects, headers = current_app.medallion_backend.get_objects(
            api_root, collection_id, request.args.to_dict(), ("id", "type", "version", "spec_version"), limit
        )

        return Response(
            response=json.dumps(objects),
            status=200,
            headers=headers,
            mimetype=MEDIA_TYPE_TAXII_V21,
        )

    elif request.method == "POST":
        validate_version_parameter_in_content_type_header()
        permission_to_write(api_root, collection_id)
        validate_size_in_request_body(api_root)
        status = current_app.medallion_backend.add_objects(
            api_root, collection_id, request.get_json(force=True), request_time
        )
        return Response(
            response=json.dumps(status),
            status=202,
            mimetype=MEDIA_TYPE_TAXII_V21,
        )


@objects_bp.route("/<string:api_root>/collections/<string:collection_id>/objects/<string:object_id>/", methods=["GET", "DELETE"])
@auth.login_required
def get_or_delete_object(api_root, collection_id, object_id):
    """
    Defines TAXII API - Collections:
        Get Object section (`5.6 <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107541>`__)
        and Delete Object section (`5.7 <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107542>`__)

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested
        object_id (str): the `identifier` of the object being requested

    Returns:
        resource:
            GET -> An Envelope Resource upon successful requests.
            DELETE -> Upon successful request nothing (status code 200).

    """
    # TODO: Check if user has access to read or write objects in collection - right now just check for permissions on the collection.
    validate_version_parameter_in_accept_header()
    api_root_exists(api_root)
    collection_exists(api_root, collection_id)

    if request.method == "GET":
        permission_to_read(api_root, collection_id)
        limit = validate_limit_parameter()
        objects, headers = current_app.medallion_backend.get_object(
            api_root, collection_id, object_id, request.args.to_dict(), ("version", "spec_version"), limit
        )
        if objects or request.args:
            return Response(
                response=json.dumps(objects),
                status=200,
                headers=headers,
                mimetype=MEDIA_TYPE_TAXII_V21,
            )
        raise ProcessingError("Object '{}' not found".format(object_id), 404)
    elif request.method == "DELETE":
        permission_to_read_and_write(api_root, collection_id)
        current_app.medallion_backend.delete_object(
            api_root, collection_id, object_id, request.args.to_dict(), ("version", "spec_version"),
        )
        return Response(
            status=200,
            mimetype=MEDIA_TYPE_TAXII_V21,
        )


@objects_bp.route("/<string:api_root>/collections/<string:collection_id>/objects/<string:object_id>/versions/", methods=["GET"])
@auth.login_required
def get_object_versions(api_root, collection_id, object_id):
    """
    Defines TAXII API - Collections: Get Object Versions section
    `(5.8) <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107543>`__.

    Args:
        api_root (str): the base URL of the API Root
        collection_id (str): the `identifier` of the Collection being requested
        object_id (str): the `identifier` of the object being requested

    Returns:
        versions: A Versions Resource upon successful requests. Additional information
            `here <https://docs.oasis-open.org/cti/taxii/v2.1/cs01/taxii-v2.1-cs01.html#_Toc31107544>`__.

    """
    # TODO: Check if user has access to read objects in collection - right now just check for permissions on the collection.

    validate_version_parameter_in_accept_header()
    api_root_exists(api_root)
    collection_exists(api_root, collection_id)
    permission_to_read(api_root, collection_id)

    limit = validate_limit_parameter()
    versions, headers = current_app.medallion_backend.get_object_versions(
        api_root, collection_id, object_id, request.args.to_dict(), ("spec_version",), limit
    )
    return Response(
        response=json.dumps(versions),
        status=200,
        headers=headers,
        mimetype=MEDIA_TYPE_TAXII_V21,
    )
