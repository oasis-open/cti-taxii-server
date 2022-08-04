import calendar
import datetime as dt
import threading
import uuid

from flask import Flask
import pytz

APPLICATION_INSTANCE = Flask("medallion")


def create_resource(resource_name, items, more=False, next_id=None):
    """Generates a Resource Object given a resource name."""
    resource = {}
    if items:
        resource[resource_name] = items
    if resource_name == "objects" or resource_name == "versions":
        if more and next_id and resource:
            resource["next"] = next_id
        if resource:
            resource["more"] = more
    return resource


def determine_version(new_obj, request_time):
    """Grab the modified time if present, if not grab created time,
    if not grab request time provided by server."""
    obj_version = new_obj.get("modified") or new_obj.get("created")
    if obj_version:
        obj_version = string_to_datetime(obj_version)
    else:
        obj_version = request_time

    return obj_version


def determine_spec_version(obj):
    """Given a STIX 2.x object, determine its spec version."""
    missing = ("created", "modified")
    if all(x not in obj for x in missing):
        # Special case: only SCOs are 2.1 objects and they don't have a spec_version
        # For now the only way to identify one is checking the created and modified
        # are both missing.
        return "2.1"
    return obj.get("spec_version", "2.0")


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
    return zoned.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


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
    if len(ms[3:].rstrip("0")) >= 1:
        ts = ts + "." + ms + "Z"
    else:
        ts = ts + "." + ms[:3] + "Z"
    return ts


def datetime_to_float(dttm):
    """Given a datetime instance, return its representation as a float"""
    # Based on this solution: https://stackoverflow.com/questions/30020988/python3-datetime-timestamp-in-python2
    if dttm.tzinfo is None:
        return calendar.timegm(dttm.utctimetuple()) + dttm.microsecond / 1e6
    else:
        return (dttm - dt.datetime(1970, 1, 1, tzinfo=pytz.UTC)).total_seconds()


def float_to_datetime(timestamp_float):
    """Given a floating-point number, produce a datetime instance"""
    result = dt.datetime.utcfromtimestamp(timestamp_float)
    result = result.replace(tzinfo=dt.timezone.utc)
    return result


def string_to_datetime(timestamp_string):
    """Convert string timestamp to datetime instance."""
    try:
        result = dt.datetime.strptime(timestamp_string, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        result = dt.datetime.strptime(timestamp_string, "%Y-%m-%dT%H:%M:%SZ")

    result = result.replace(tzinfo=dt.timezone.utc)

    return result


def generate_status(
    request_time, status, successes=(), failures=(), pendings=()
):
    """Generate Status Resource as defined in TAXII 2.1 section (4.3.1) <link here>`__."""
    succeeded = len(successes)
    failed = len(failures)
    pending = len(pendings)

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


def get_custom_headers(manifest_resource):
    """Generates the X-TAXII-Date-Added headers based on a manifest resource"""
    headers = {}

    times = sorted(map(lambda x: x["date_added"], manifest_resource.get("objects", [])))
    if len(times) > 0:
        headers["X-TAXII-Date-Added-First"] = times[0]
        headers["X-TAXII-Date-Added-Last"] = times[-1]

    return headers


def parse_request_parameters(filter_args):
    """Generates a dict with params received from client"""
    session_args = {}
    for key, value in filter_args.items():
        if key != "limit" and key != "next":
            session_args[key] = set(value.replace(" ", "").split(","))
    return session_args


class TaskChecker(object):
    """Calls a target method every X seconds to perform a task."""

    def __init__(self, interval, target_function):
        self.interval = interval
        self.target_function = target_function
        self.thread = threading.Timer(interval=self.interval, function=self.handle_function)
        self.thread.daemon = True

    def handle_function(self):
        self.target_function()
        self.thread = threading.Timer(interval=self.interval, function=self.handle_function)
        self.thread.daemon = True
        self.thread.start()

    def start(self):
        self.thread.start()


def get_application_instance_config_values(flask_application_instance, config_group, config_key=None):
    if config_group == "taxii" and hasattr(flask_application_instance, "taxii_config"):
        if flask_application_instance.taxii_config and config_key in flask_application_instance.taxii_config:
            return flask_application_instance.taxii_config[config_key]
        else:
            return flask_application_instance.taxii_config
    if config_group == "users" and hasattr(flask_application_instance, "users_config"):
        if flask_application_instance.users_config and config_key in flask_application_instance.users_config:
            return flask_application_instance.users_config[config_key]
        else:
            return flask_application_instance.users_config
    if config_group == "backend" and hasattr(flask_application_instance, "backend_config"):
        if flask_application_instance.backend_config and config_key in flask_application_instance.backend_config:
            return flask_application_instance.backend_config[config_key]
        else:
            return flask_application_instance.backend_config
    return None
