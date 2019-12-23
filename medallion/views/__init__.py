import re

from flask import request

from ..exceptions import ProcessingError

MEDIA_TYPE_TAXII_ANY = "application/taxii+json"
MEDIA_TYPE_TAXII_V21 = "{media};version=2.1".format(media=MEDIA_TYPE_TAXII_ANY)


def validate_version_parameter_in_accept_header():
    """All endpoints need to check the Accept Header for the correct Media Type"""
    accept_header = request.headers.get("accept", "").replace(" ", "").split(",")
    found = False

    for item in accept_header:
        result = re.match(r"^application\/taxii\+json(;version=(\d\.\d))?$", item)
        if result:
            if len(result.groups()) >= 1:
                version_str = result.group(2)
                if version_str != "2.1":  # The server only supports 2.1
                    raise ProcessingError("The server does not support version {}".format(version_str), 406)
            found = True
            break

    if found is False:
        raise ProcessingError("Media type in the Accept header is invalid or not found", 406)
