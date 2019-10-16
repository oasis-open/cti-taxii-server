import logging

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from ..exceptions import MongoBackendError, ProcessingError
from ..filters.mongodb_filter import MongoDBFilter
from ..utils.common import create_resource, determine_version, format_datetime, generate_status, generate_status_details
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

    def __init__(self, uri=None, **kwargs):
        try:
            self.client = MongoClient(uri)
        except ConnectionFailure:
            log.error("Unable to establish a connection to MongoDB server {}".format(uri))

    @catch_mongodb_error
    def _update_manifest(self, new_obj, api_root, collection_id, request_time):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        media_type_fmt = "application/taxii+json;version={}"

        version = determine_version(new_obj, request_time)
        media_type = media_type_fmt.format(new_obj.get("spec_version", "2.1"))

        # version is a single value now, therefore a new manifest is created always
        manifest_info.insert_one(
            {
                "id": new_obj["id"],
                "date_added": request_time,
                "version": version,
                "media_type": media_type,
                "_collection_id": collection_id,
                "_type": new_obj["type"],
            },
        )

    @catch_mongodb_error
    def server_discovery(self):
        discovery_db = self.client["discovery_database"]
        collection = discovery_db["discovery_information"]
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
        ]
        info = list(collection.aggregate(pipeline))[0]
        info.pop("_roots", None)
        info.pop("_id", None)
        return info

    @catch_mongodb_error
    def get_collections(self, api_root):
        if api_root not in self.client.list_database_names():
            return None  # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        collections = list(collection_info.find({}))

        for c in collections:
            if c:
                c.pop("_id", None)
        return create_resource("collections", collections)

    @catch_mongodb_error
    def get_collection(self, api_root, collection_id):
        if api_root not in self.client.list_database_names():
            return None  # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        info = collection_info.find_one({"id": collection_id})
        if info:
            info.pop("_id", None)
        return info

    @catch_mongodb_error
    def get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        full_filter = MongoDBFilter(
            filter_args,
            {"$_collection_id": collection_id},
            allowed_filters,
        )
        objects_found = full_filter.process_filter(
            manifest_info,
            allowed_filters,
            None,
        )
        if objects_found:
            for obj in objects_found:
                if obj:
                    obj.pop("_id", None)
                    obj.pop("_collection_id", None)
                    obj.pop("_type", None)
                    # format date_added which is an ISODate object
                    obj["date_added"] = format_datetime(obj["date_added"])
        return create_resource("objects", objects_found)

    @catch_mongodb_error
    def get_api_root_information(self, api_root_name):
        db = self.client["discovery_database"]
        api_root_info = db["api_root_info"]
        info = api_root_info.find_one({"_name": api_root_name})
        if info:
            info.pop("_id", None)
            info.pop("_url", None)
            info.pop("_name", None)
        return info

    @catch_mongodb_error
    def get_status(self, api_root, status_id):
        api_root_db = self.client[api_root]
        status_info = api_root_db["status"]
        result = status_info.find_one({"id": status_id})
        if result:
            result.pop("_id", None)
        return result

    @catch_mongodb_error
    def get_objects(self, api_root, collection_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        full_filter = MongoDBFilter(
            filter_args,
            {"$_collection_id": collection_id},
            allowed_filters,
        )
        # Note: error handling was not added to following call as mongo will
        # handle (user supplied) filters gracefully if they don't exist
        objects_found = full_filter.process_filter(
            objects,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": collection_id},
        )
        for obj in objects_found:
            if obj:
                obj.pop("_id", None)
                obj.pop("_collection_id", None)
        return create_resource("objects", objects_found)

    @catch_mongodb_error
    def add_objects(self, api_root, collection_id, objs, request_time):
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        failed = 0
        succeeded = 0
        pending = 0
        successes = []
        failures = []

        try:
            for new_obj in objs["objects"]:
                mongo_query = {"_collection_id": collection_id, "id": new_obj["id"]}
                if "modified" in new_obj:
                    mongo_query["modified"] = new_obj["modified"]
                existing_entry = objects.find_one(mongo_query)
                if existing_entry:
                    status_detail = generate_status_details(
                        new_obj["id"], determine_version(new_obj, request_time),
                        message="Unable to process object",
                    )
                    failures.append(status_detail)
                    failed += 1
                else:
                    new_obj.update({"_collection_id": collection_id})
                    objects.insert_one(new_obj)
                    self._update_manifest(new_obj, api_root, collection_id, request_time)
                    status_detail = generate_status_details(new_obj["id"], determine_version(new_obj, request_time))
                    successes.append(status_detail)
                    succeeded += 1
        except Exception as e:
            raise ProcessingError("While processing supplied content, an error occurred", 422, e)

        status = generate_status(
            request_time, "complete", succeeded, failed,
            pending, successes=successes, failures=failures,
        )
        api_root_db["status"].insert_one(status)
        status.pop("_id", None)
        return status

    @catch_mongodb_error
    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        full_filter = MongoDBFilter(
            filter_args,
            {"$_collection_id": collection_id, "$id": object_id},
            allowed_filters,
        )
        objects_found = full_filter.process_filter(
            objects,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": collection_id},
        )
        if objects_found:
            for obj in objects_found:
                if obj:
                    obj.pop("_id", None)
                    obj.pop("_collection_id", None)
        return create_resource("objects", objects_found)

    @catch_mongodb_error
    def delete_object(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]

        full_filter = MongoDBFilter(
            filter_args,
            {"$_collection_id": collection_id, "$id": object_id},
            allowed_filters,
        )
        objects_found = full_filter.process_filter(
            objects,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": collection_id},
        )
        if objects_found:
            for obj in objects_found:
                if obj:
                    objects.delete_one({"_id": obj.pop("_id", None)})
        else:
            raise ProcessingError("Object '{}' not found".format(object_id), 404)

    @catch_mongodb_error
    def get_object_versions(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]

        full_filter = MongoDBFilter(
            filter_args,
            {"$_collection_id": collection_id, "$id": object_id},
            allowed_filters,
        )
        objects_found = full_filter.process_filter(
            manifest_info,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": collection_id},
        )
        objects_found = sorted(map(lambda x: x["version"], objects_found), reverse=True)
        return create_resource("versions", objects_found)
