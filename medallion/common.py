import datetime as dt
import threading
import uuid

import pytz


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
        obj_version = timestamp_to_datetime(obj_version)
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
    return dttm.timestamp()


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


def timestamp_to_epoch_seconds(timestamp):
    """
    Convert a timestamp to epoch seconds.  This is a more general purpose
    conversion function supporting a few different input types: strings,
    numbers (i.e. value is already in epoch seconds), and datetime objects.

    :param timestamp: A timestamp as a string, number, or datetime object
    :return: Number of epoch seconds (can be a float with fractional seconds)
    """
    if isinstance(timestamp, (int, float)):
        result = timestamp
    elif isinstance(timestamp, str):
        result = datetime_to_float(string_to_datetime(timestamp))
    elif isinstance(timestamp, dt.datetime):
        result = timestamp.timestamp()
    else:
        raise TypeError(
            "Can't convert {} to an epoch seconds timestamp".format(
                type(timestamp)
            )
        )

    return result


def timestamp_to_stix_json(timestamp):
    """
    Convert a timestamp to STIX JSON.  This is a more general purpose
    conversion function supporting a few different input types: strings
    (i.e. value is already a STIX JSON timestamp), numbers (epoch seconds), and
    datetime objects.

    :param timestamp: A timestamp as a string, number, or datetime object
    :return: A STIX JSON timestamp string
    """
    if isinstance(timestamp, (int, float)):
        result = datetime_to_string_stix(float_to_datetime(timestamp))
    elif isinstance(timestamp, str):
        result = timestamp  # any format verification?
    elif isinstance(timestamp, dt.datetime):
        result = datetime_to_string_stix(timestamp)
    else:
        raise TypeError(
            "Can't convert {} to a STIX JSON timestamp string".format(
                type(timestamp)
            )
        )

    return result


def timestamp_to_taxii_json(timestamp):
    """
    Convert a timestamp to TAXII JSON.  This is a more general purpose
    conversion function supporting a few different input types: strings
    (i.e. value is already a TAXII JSON timestamp), numbers (epoch seconds),
    and datetime objects.  From the TAXII spec: "Unlike the STIX timestamp
    type, the TAXII timestamp MUST have microsecond precision."

    :param timestamp: A timestamp as a string, number, or datetime object
    :return: A TAXII JSON timestamp string
    """
    if isinstance(timestamp, (int, float)):
        result = datetime_to_string(float_to_datetime(timestamp))
    elif isinstance(timestamp, str):
        result = timestamp  # any format verification?
    elif isinstance(timestamp, dt.datetime):
        result = datetime_to_string(timestamp)
    else:
        raise TypeError(
            "Can't convert {} to a TAXII JSON timestamp string".format(
                type(timestamp)
            )
        )

    return result


def timestamp_to_datetime(timestamp):
    """
    Convert a timestamp to a datetime object.  This is a more general purpose
    conversion function supporting a few different input types: strings,
    numbers (epoch seconds), and datetime objects.

    :param timestamp: A timestamp as a string, number, or datetime object
    :return: A timezone-aware datetime object in the UTC timezone
    """
    if isinstance(timestamp, (int, float)):
        result = float_to_datetime(timestamp)
    elif isinstance(timestamp, str):
        result = string_to_datetime(timestamp)
    elif isinstance(timestamp, dt.datetime):

        # If no timezone, treat as UTC directly
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.timezone.utc)

        # If timezone is not equivalent to UTC, convert to UTC (try to write
        # this in a way which is agnostic to the actual tzinfo implementation).
        elif timestamp.utcoffset() != dt.timezone.utc.utcoffset(None):
            timestamp = timestamp.astimezone(dt.timezone.utc)

        result = timestamp

    else:
        raise TypeError(
            "Can't convert {} to a datetime instance".format(
                type(timestamp)
            )
        )

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
        self.lock = threading.Lock()
        # One can "cancel" a timer, but that does nothing if the time has
        # already expired.  In that case, we need this flag to tell it to not
        # schedule a new timer.
        self.stop_flag = False

        # Create a task checker in an un-started state.
        self.__reset_timer(start=False)

    def handle_function(self):
        self.target_function()
        self.__reset_timer()

    def __reset_timer(self, start=True):
        with self.lock:
            if not self.stop_flag:
                self.thread = threading.Timer(
                    interval=self.interval, function=self.handle_function
                )
                self.thread.daemon = True
                if start:
                    self.start()

    def start(self):
        self.thread.start()

    def stop(self, timeout=None):
        with self.lock:
            self.thread.cancel()
            self.stop_flag = True
        # Implies a timer thread must not call this method!
        # It can be important to wait for thread termination: a backend has to
        # be careful not to release resources a task checker thread might use,
        # before the thread has terminated.
        self.thread.join(timeout)
