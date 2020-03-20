import re

from flask import request

from ..exceptions import ProcessingError

MEDIA_TYPE_TAXII_ANY = "application/vnd.oasis.taxii+json"
MEDIA_TYPE_TAXII_V20 = "{media}; version=2.0".format(media=MEDIA_TYPE_TAXII_ANY)
MEDIA_TYPE_STIX_ANY = "application/vnd.oasis.stix+json"
MEDIA_TYPE_STIX_V20 = "{media}; version=2.0".format(media=MEDIA_TYPE_STIX_ANY)


def validate_taxii_version_parameter_in_accept_header():
    """Validate endpoint that need to check the Accept Header for the correct Media Type"""
    accept_header = request.headers.get("accept", "").replace(" ", "").split(",")
    found = False

    for item in accept_header:
        result = re.match(r"^application\/vnd\.oasis\.taxii\+json(; version=(\d\.\d))?$", item)
        if result:
            if len(result.groups()) >= 1:
                version_str = result.group(2)
                if version_str != "2.0":  # The server only supports 2.0
                    raise ProcessingError("The server does not support version {}".format(version_str), 406)
            found = True
            break

    if found is False:
        raise ProcessingError("Media type in the Accept header is invalid or not found", 406)


def validate_stix_version_parameter_in_accept_header():
    """Validate endpoint that need to check the Accept Header for the correct Media Type"""
    accept_header = request.headers.get("accept", "").replace(" ", "").split(",")
    found = False

    for item in accept_header:
        result = re.match(r"^application\/vnd\.oasis\.stix\+json(; version=(\d\.\d))?$", item)
        if result:
            if len(result.groups()) >= 1:
                version_str = result.group(2)
                if version_str != "2.0":  # The server only supports 2.0
                    raise ProcessingError("The server does not support version {}".format(version_str), 406)
            found = True
            break

    if found is False:
        raise ProcessingError("Media type in the Accept header is invalid or not found", 406)
