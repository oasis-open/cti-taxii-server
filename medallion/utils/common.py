import datetime as dt
import uuid

import pytz
from six import iteritems


def create_resource(resource_name, o, more=False):
    """Generates a Resource Object given a resource name."""
    return {resource_name: o, "more": more}


def determine_version(new_obj, request_time):
    """Grab the modified time if present, if not grab created time,
    if not grab request time provided by server."""
    return new_obj.get("modified", new_obj.get("created", format_datetime_micro(request_time)))


def determine_spec_version(obj):
    """Given a STIX 2.x object, determine its spec version."""
    missing = ("created", "modified")
    if all(x not in obj for x in missing):
        # Special case: only SCOs are 2.1 objects and they don't have a spec_version
        # For now the only way to identify one is checking the created and modified
        # are both missing.
        return "2.1"
    return obj.get("spec_version", "2.0")


def get(data, key):
    """Given a dict, loop recursively over the object. Returns the value based on the key match"""
    for ancestors, item in iterpath(data):
        if key in ancestors:
            return item


def iterpath(obj, path=None):
    """
    Generator which walks the input ``obj`` model. Each iteration yields a
    tuple containing a list of ancestors and the property value.

    Args:
        obj: A SDO or SRO object.
        path: None, used recursively to store ancestors.

    Example:
        >>> for item in iterpath(obj):
        >>>     print(item)
        (['type'], 'campaign')
        ...
        (['cybox', 'objects', '[0]', 'hashes', 'sha1'], 'cac35ec206d868b7d7cb0b55f31d9425b075082b')

    Returns:
        tuple: Containing two items: a list of ancestors and the property value.

    """
    if path is None:
        path = []

    for varname, varobj in iter(sorted(iteritems(obj))):
        path.append(varname)
        yield (path, varobj)

        if isinstance(varobj, dict):

            for item in iterpath(varobj, path):
                yield item

        elif isinstance(varobj, list):

            for item in varobj:
                index = "[{0}]".format(varobj.index(item))
                path.append(index)

                yield (path, item)

                if isinstance(item, dict):
                    for descendant in iterpath(item, path):
                        yield descendant

                path.pop()

        path.pop()


def get_timestamp():
    """Get current time with UTC offset"""
    return dt.datetime.now(tz=pytz.UTC)


def format_datetime(dttm):
    """Given a datetime instance, produce the string representation"""
    # 1. Convert to timezone-aware
    # 2. Convert to UTC
    # 3. Format in ISO format
    # 4. Add subsecond value if non-zero
    # 5. Add "Z"

    if dttm.tzinfo is None or dttm.tzinfo.utcoffset(dttm) is None:
        # dttm is timezone-naive; assume UTC
        zoned = pytz.UTC.localize(dttm)
    else:
        zoned = dttm.astimezone(pytz.UTC)
    ts = zoned.strftime("%Y-%m-%dT%H:%M:%S")
    if zoned.microsecond > 0:
        ms = zoned.strftime("%f")
        ts = ts + "." + ms.rstrip("0")
    return ts + "Z"


def format_datetime_micro(dttm):
    """Given a datetime instance, produce the string representation
    with microsecond precision"""
    # 1. Convert to timezone-aware
    # 2. Convert to UTC
    # 3. Format in ISO format with microsecond precision

    if dttm.tzinfo is None or dttm.tzinfo.utcoffset(dttm) is None:
        # dttm is timezone-naive; assume UTC
        zoned = pytz.UTC.localize(dttm)
    else:
        zoned = dttm.astimezone(pytz.UTC)
    ts = zoned.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return ts


def convert_to_stix_datetime(timestamp_string):
    """Convert string timestamp to datetime instance."""
    try:
        return dt.datetime.strptime(timestamp_string, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return dt.datetime.strptime(timestamp_string, "%Y-%m-%dT%H:%M:%SZ")


def generate_status(
    request_time, status, succeeded, failed, pending,
    successes=None, failures=None, pendings=None,
):
    """Generate Status Resource as defined in TAXII 2.1 section (4.3.1) <link here>`__."""
    status = {
        "id": str(uuid.uuid4()),
        "status": status,
        "request_timestamp": request_time,
        "total_count": succeeded + failed + pending,
        "success_count": succeeded,
        "failure_count": failed,
        "pending_count": pending,
    }

    if successes:
        status["successes"] = successes
    if failures:
        status["failures"] = failures
    if pendings:
        status["pendings"] = pendings

    return status


def generate_status_details(id, version, message=None):
    """Generate Status Details as defined in TAXII 2.1 section (4.3.1) <link here>`__."""
    status_details = {
        "id": id,
        "version": version
    }

    if message:
        status_details["message"] = message

    return status_details
