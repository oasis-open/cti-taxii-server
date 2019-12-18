import logging
import uuid

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from ..common import (SessionChecker, create_resource, datetime_to_float,
                      datetime_to_string, datetime_to_string_stix,
                      determine_spec_version, determine_version,
                      find_version_attribute, float_to_datetime,
                      generate_status, generate_status_details,
                      get_custom_headers, get_timestamp,
                      parse_request_parameters, string_to_datetime)
from ..exceptions import MongoBackendError, ProcessingError
from ..filters.mongodb_filter import MongoDBFilter
from .base import Backend

# Module-level logger
log = logging.getLogger(__name__)


def catch_mongodb_error(func):
    """Catch mongodb availability error"""

    def api_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            raise MongoBackendError("Unable to connect to MongoDB", 500, e)

    return api_wrapper


class MongoBackend(Backend):

    # access control is handled at the views level

    def __init__(self, **kwargs):
        try:
            self.client = MongoClient(kwargs.get("uri"))
            self.pages = {}
            self.timeout = kwargs.get("session_timeout", 30)
        except ConnectionFailure:
            log.error("Unable to establish a connection to MongoDB server {}".format(kwargs.get("uri")))

        checker = SessionChecker(kwargs.get("check_interval", 10), self._pop_expired_sessions)
        checker.start()

    def _process_params(self, filter_args, limit):
        next_id = filter_args.get("next")
        if limit and next_id is None:
            client_params = parse_request_parameters(filter_args)
            record = {"skip": 0, "limit": limit, "args": client_params, "request_time": datetime_to_float(get_timestamp())}
            next_id = str(uuid.uuid4())
            self.pages[next_id] = record
        elif limit and next_id:
            if next_id not in self.pages:
                raise ProcessingError("The server did not understand the request or filter parameters: 'next' not valid", 400)
            client_params = parse_request_parameters(filter_args)
            if self.pages[next_id]["args"] != client_params:
                raise ProcessingError("The server did not understand the request or filter parameters: params changed over subsequent transaction", 400)
            self.pages[next_id]["limit"] = limit
            self.pages[next_id]["request_time"] = datetime_to_float(get_timestamp())
            record = self.pages[next_id]
        else:
            record = {}
        return next_id, record

    def _update_record(self, next_id, count, internal=False):
        more = False
        if next_id:
            if internal is False:
                self.pages[next_id]["skip"] += self.pages[next_id]["limit"]
            if self.pages[next_id]["skip"] >= count:
                self.pages.pop(next_id, None)
                next_id = None
            else:
                more = True
        return next_id, more

    def _validate_object_id(self, manifest_info, collection_id, object_id):
        result = list(manifest_info.find({"_collection_id": collection_id, "id": object_id}).limit(1))
        if len(result) == 0:
            raise ProcessingError("Object '{}' not found".format(object_id), 404)

    def _pop_expired_sessions(self):
        expired_ids = []
        boundary = datetime_to_float(get_timestamp())
        for next_id, record in self.pages.items():
            if boundary - record["request_time"] > self.timeout:
                expired_ids.append(next_id)

        for item in expired_ids:
            self.pages.pop(item)

    def _get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters, limit, internal=False):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        next_id, record = self._process_params(filter_args, limit)

        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}},
            allowed_filters,
            record
        )
        count, objects_found = full_filter.process_filter(
            manifest_info,
            allowed_filters,
            None,
        )

        for obj in objects_found:
            obj["date_added"] = datetime_to_string(float_to_datetime(obj["date_added"]))
            obj["version"] = datetime_to_string_stix(float_to_datetime(obj["version"]))

        next_id, more = self._update_record(next_id, count, internal)
        manifest_resource = create_resource("objects", objects_found, more, next_id)
        if internal:
            return manifest_resource
        else:
            headers = get_custom_headers(manifest_resource)
            return manifest_resource, headers

    @catch_mongodb_error
    def _update_manifest(self, new_obj, api_root, collection_id, obj_version, request_time):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        collection_info = api_root_db["collections"]
        media_type_fmt = "application/stix+json;version={}"

        media_type = media_type_fmt.format(determine_spec_version(new_obj))

        # version is a single value now, therefore a new manifest is created always
        manifest_info.insert_one(
            {
                "id": new_obj["id"],
                "date_added": datetime_to_float(request_time),
                "version": datetime_to_float(string_to_datetime(obj_version)),
                "media_type": media_type,
                "_collection_id": collection_id,
                "_type": new_obj["type"],
            },
        )

        # update media_types in collection if a new one is present.
        info = collection_info.find_one({"id": collection_id})
        if media_type not in info["media_types"]:
            info["media_types"].append(media_type)
            collection_info.update_one(
                {"id": collection_id},
                {"$set": {"media_types": info["media_types"]}}
            )

    @catch_mongodb_error
    def server_discovery(self):
        discovery_db = self.client["discovery_database"]
        discovery_info = discovery_db["discovery_information"]
        pipeline = [
            {
                "$lookup": {
                    "from": "api_root_info",
                    "localField": "api_roots",
                    "foreignField": "_name",
                    "as": "_roots",
                },
            },
            {
                "$addFields": {
                    "api_roots": "$_roots._url",
                },
            },
            {
                "$project": {
                    "_roots": 0,
                    "_id": 0,
                }
            }
        ]
        info = discovery_info.aggregate(pipeline).next()
        return info

    @catch_mongodb_error
    def get_collections(self, api_root):
        if api_root not in self.client.list_database_names():
            return None  # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        collections = list(collection_info.find({}, {"_id": 0}))
        return create_resource("collections", collections)

    @catch_mongodb_error
    def get_collection(self, api_root, collection_id):
        if api_root not in self.client.list_database_names():
            return None  # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        info = collection_info.find_one({"id": collection_id}, {"_id": 0})
        return info

    @catch_mongodb_error
    def get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters, limit):
        return self._get_object_manifest(api_root, collection_id, filter_args, allowed_filters, limit, False)

    @catch_mongodb_error
    def get_api_root_information(self, api_root_name):
        db = self.client["discovery_database"]
        api_root_info = db["api_root_info"]
        info = api_root_info.find_one(
            {"_name": api_root_name},
            {"_id": 0, "_url": 0, "_name": 0}
        )
        return info

    @catch_mongodb_error
    def get_status(self, api_root, status_id):
        api_root_db = self.client[api_root]
        status_info = api_root_db["status"]
        result = status_info.find_one(
            {"id": status_id},
            {"_id": 0}
        )
        return result

    @catch_mongodb_error
    def get_objects(self, api_root, collection_id, filter_args, allowed_filters, limit):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        manifest_info = api_root_db["manifests"]
        next_id, record = self._process_params(filter_args, limit)

        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}},
            allowed_filters,
            record
        )
        # Note: error handling was not added to following call as mongo will
        # handle (user supplied) filters gracefully if they don't exist
        count, objects_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            manifest_info
        )

        for obj in objects_found:
            if "modified" in obj:
                obj["modified"] = datetime_to_string_stix(float_to_datetime(obj["modified"]))
            if "created" in obj:
                obj["created"] = datetime_to_string_stix(float_to_datetime(obj["created"]))

        manifest_resource = self._get_object_manifest(api_root, collection_id, filter_args, allowed_filters, limit, True)
        headers = get_custom_headers(manifest_resource)

        next_id, more = self._update_record(next_id, count)
        return create_resource("objects", objects_found, more, next_id), headers

    @catch_mongodb_error
    def add_objects(self, api_root, collection_id, objs, request_time):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        manifest_info = api_root_db["manifests"]
        failed = 0
        succeeded = 0
        pending = 0
        successes = []
        failures = []
        media_fmt = "application/stix+json;version={}"

        try:
            for new_obj in objs["objects"]:
                media_type = media_fmt.format(determine_spec_version(new_obj))
                mongo_query = {"_collection_id": collection_id, "id": new_obj["id"], "media_type": media_type}
                if "modified" in new_obj:
                    mongo_query["version"] = datetime_to_float(string_to_datetime(new_obj["modified"]))
                existing_entry = manifest_info.find_one(mongo_query)
                obj_version = determine_version(new_obj, request_time)
                if existing_entry:
                    status_detail = generate_status_details(
                        new_obj["id"], obj_version,
                        message="Unable to process object because an identical entry already exists in collection '{}'.".format(collection_id),
                    )
                    failures.append(status_detail)
                    failed += 1
                else:
                    new_obj.update({"_collection_id": collection_id})
                    if all(prop not in new_obj for prop in ("modified", "created")):
                        new_obj["_date_added"] = datetime_to_float(string_to_datetime(obj_version))  # Special case for un-versioned objects
                    if "modified" in new_obj:
                        new_obj["modified"] = datetime_to_float(string_to_datetime(new_obj["modified"]))
                    if "created" in new_obj:
                        new_obj["created"] = datetime_to_float(string_to_datetime(new_obj["created"]))
                    objects_info.insert_one(new_obj)
                    self._update_manifest(new_obj, api_root, collection_id, obj_version, request_time)
                    status_detail = generate_status_details(
                        new_obj["id"], obj_version,
                        message="Successfully added object to collection '{}'.".format(collection_id)
                    )
                    successes.append(status_detail)
                    succeeded += 1
        except Exception as e:
            log.exception(e)
            raise ProcessingError("While processing supplied content, an error occurred", 422, e)

        status = generate_status(
            datetime_to_string(request_time), "complete", succeeded, failed,
            pending, successes=successes, failures=failures,
        )
        api_root_db["status"].insert_one(status)
        status.pop("_id", None)
        return status

    @catch_mongodb_error
    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        manifest_info = api_root_db["manifests"]
        # set manually to properly retrieve manifests, and early to not break the pagination checks
        filter_args["match[id]"] = object_id
        next_id, record = self._process_params(filter_args, limit)

        self._validate_object_id(manifest_info, collection_id, object_id)

        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}, "id": {"$eq": object_id}},
            allowed_filters,
            record
        )
        count, objects_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            manifest_info
        )

        for obj in objects_found:
            if "modified" in obj:
                obj["modified"] = datetime_to_string_stix(float_to_datetime(obj["modified"]))
            if "created" in obj:
                obj["created"] = datetime_to_string_stix(float_to_datetime(obj["created"]))

        manifest_resource = self._get_object_manifest(api_root, collection_id, filter_args, ("id", "type", "version", "spec_version"), limit, True)
        headers = get_custom_headers(manifest_resource)

        next_id, more = self._update_record(next_id, count)
        return create_resource("objects", objects_found, more, next_id), headers

    @catch_mongodb_error
    def delete_object(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        manifest_info = api_root_db["manifests"]

        self._validate_object_id(manifest_info, collection_id, object_id)

        # Currently it will delete the object and the matching manifest from the backend
        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}, "id": {"$eq": object_id}},
            allowed_filters,
        )
        count, objects_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            manifest_info
        )
        if objects_found:
            for obj in objects_found:
                attr = find_version_attribute(obj)
                objects_info.delete_one(
                    {"_collection_id": collection_id, "id": object_id, attr: obj[attr]}
                )
                obj_version = obj.get("modified", obj.get("created", obj.get("_date_added")))
                manifest_info.delete_one(
                    {"_collection_id": collection_id, "id": object_id, "version": obj_version}
                )
        else:
            raise ProcessingError("Object '{}' not found".format(object_id), 404)

    @catch_mongodb_error
    def get_object_versions(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        # set manually to properly retrieve manifests, and early to not break the pagination checks
        filter_args["match[id]"] = object_id
        filter_args["match[version]"] = "all"
        next_id, record = self._process_params(filter_args, limit)

        self._validate_object_id(manifest_info, collection_id, object_id)

        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}, "id": {"$eq": object_id}},
            allowed_filters,
            record
        )
        count, manifests_found = full_filter.process_filter(
            manifest_info,
            allowed_filters,
            None,
        )

        manifest_resource = self._get_object_manifest(api_root, collection_id, filter_args, ("id", "type", "version", "spec_version"), limit, True)
        headers = get_custom_headers(manifest_resource)

        manifests_found = list(map(lambda x: datetime_to_string_stix(float_to_datetime(x["version"])), manifests_found))
        next_id, more = self._update_record(next_id, count)
        return create_resource("versions", manifests_found, more, next_id), headers
