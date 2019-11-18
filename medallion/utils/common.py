import datetime as dt
import time
import uuid

import pytz
from six import iteritems, text_type


def generate_stix20_id(sdo_type):
    return "{sdo_type}--{uuid}".format(
        sdo_type=sdo_type,
        uuid=text_type(uuid.uuid4()),
    )


def create_bundle(o):
    return {
        "id": generate_stix20_id("bundle"),
        "objects": o,
        "spec_version": "2.0",
        "type": "bundle",
    }


def determine_version(new_obj, request_time):
    """Grab the modified time if present, if not grab created time,
    if not grab request time provided by server."""
    return new_obj.get("modified", new_obj.get("created", datetime_to_string(request_time)))


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


def datetime_to_string(dttm):
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


def datetime_to_string_stix(dttm):
    """Given a datetime instance, produce the string representation
    with millisecond precision"""
    # 1. Convert to timezone-aware
    # 2. Convert to UTC
    # 3. Format in ISO format with millisecond precision,
    #       except for objects defined with higher precision
    # 4. Add "Z"

    if dttm.tzinfo is None or dttm.tzinfo.utcoffset(dttm) is None:
        # dttm is timezone-naive; assume UTC
        zoned = pytz.UTC.localize(dttm)
    else:
        zoned = dttm.astimezone(pytz.UTC)
    ts = zoned.strftime("%Y-%m-%dT%H:%M:%S")
    ms = zoned.strftime("%f")
    if len(ms.rstrip("0")) > 3:
        return ts + "." + ms + "Z"
    return ts + "." + ms[:3] + "Z"


def datetime_to_float(dttm):
    """Given a datetime instance, return its representation as a float"""
    # Based on this solution: https://stackoverflow.com/questions/30020988/python3-datetime-timestamp-in-python2
    if dttm.tzinfo is None:
        return time.mktime((dttm.timetuple())) + dttm.microsecond / 1e6
    else:
        return (dttm - dt.datetime(1970, 1, 1, tzinfo=pytz.UTC)).total_seconds()


def float_to_datetime(timestamp_float):
    """Given a floating-point number, produce a datetime instance"""
    return dt.datetime.fromtimestamp(timestamp_float)


def string_to_datetime(timestamp_string):
    """Convert string timestamp to datetime instance."""
    try:
        return dt.datetime.strptime(timestamp_string, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return dt.datetime.strptime(timestamp_string, "%Y-%m-%dT%H:%M:%SZ")


def generate_status(
    request_time, status, succeeded, failed, pending,
    successes_ids=None, failures=None, pendings=None,
):
    """
    Generate Status Resource as defined in
    `TAXII 2.0 section (4.3.1) <https://docs.google.com/document/d/1Jv9ICjUNZrOnwUXtenB1QcnBLO35RnjQcJLsa1mGSkI/pub#h.21tzry6u9dbz>`__.
    """
    status = {
        "id": str(uuid.uuid4()),
        "status": status,
        "request_timestamp": request_time,
        "total_count": succeeded + failed + pending,
        "success_count": succeeded,
        "failure_count": failed,
        "pending_count": pending,
    }

    if successes_ids:
        status["successes"] = successes_ids
    if failures:
        status["failures"] = failures
    if pendings:
        status["pendings"] = pendings

    return status
