import logging

from ...exceptions import MongoBackendError, ProcessingError
from ...filters.mongodb_filter import MongoDBFilter
from ...utils.common import (create_bundle, determine_spec_version,
                             determine_version, format_datetime,
                             generate_status)
from .base import Backend

try:
    from pymongo import ASCENDING, MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
except ImportError:
    raise ImportError("'pymongo' package is required to use this module.")


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
        uri = kwargs.get("uri")
        try:
            self.client = MongoClient(uri)
        except ConnectionFailure:
            log.error("Unable to establish a connection to MongoDB server {}".format(uri))

    @catch_mongodb_error
    def _update_manifest(self, new_obj, api_root, collection_id, request_time):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        collection_info = api_root_db["collections"]
        entry = manifest_info.find_one(
            {"_collection_id": collection_id, "id": new_obj["id"]},
        )

        media_type_fmt = "application/vnd.oasis.stix+json; version={}"
        media_type = media_type_fmt.format(determine_spec_version(new_obj))
        version = determine_version(new_obj, request_time)

        if entry:
            if "modified" in new_obj:
                entry["versions"].append(new_obj["modified"])
                manifest_info.update_one(
                    {"_collection_id": collection_id, "id": new_obj["id"]},
                    {"$set": {"versions": sorted(entry["versions"], reverse=True)}},
                )
            # If the new_obj is there, and it has no modified property,
            # then it is immutable, and there is nothing to do.
        else:
            manifest_info.insert_one(
                {
                    "id": new_obj["id"],
                    "date_added": request_time,
                    "versions": [version],
                    "media_types": [media_type],
                    "_collection_id": collection_id,
                    "_type": new_obj["type"],
                },
            )

        # update media_types in collection if a new one is present.
        info = collection_info.find_one({"id": collection_id})
        if media_type not in info["media_types"]:
            collection_info.update_one(
                {"id": collection_id},
                {"$set": {"media_types": info["media_types"] + [media_type]}}
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
    def get_collections(self, api_root, start_index, end_index):
        if api_root not in self.client.list_database_names():
            return None, None   # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        count = collection_info.count()

        pipeline = [
            {"$match": {}},
            {"$sort": {"_id": ASCENDING}},
            {"$skip": start_index},
            {"$limit": (end_index - start_index) + 1},
        ]
        collections = list(collection_info.aggregate(pipeline))
        for c in collections:
            if c:
                c.pop("_id", None)
        return count, collections

    @catch_mongodb_error
    def get_collection(self, api_root, id_):
        if api_root not in self.client.list_database_names():
            return None  # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        info = collection_info.find_one({"id": id_})
        if info:
            info.pop("_id", None)
        return info

    @catch_mongodb_error
    def get_object_manifest(self, api_root, id_, filter_args, allowed_filters, start_index, page_size):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": id_},
            allowed_filters,
            start_index,
            page_size,
        )
        total, objects_found = full_filter.process_filter(
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
        return total, objects_found

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
    def get_status(self, api_root, id_):
        api_root_db = self.client[api_root]
        status_info = api_root_db["status"]
        result = status_info.find_one({"id": id_})
        if result:
            result.pop("_id", None)
        return result

    @catch_mongodb_error
    def get_objects(self, api_root, id_, filter_args, allowed_filters, start_index, page_size):
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": id_},
            allowed_filters,
            start_index,
            page_size,
        )
        # Note: error handling was not added to following call as mongo will
        # handle (user supplied) filters gracefully if they don't exist
        total, objects_found = full_filter.process_filter(
            objects,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": id_},
        )
        for obj in objects_found:
            if obj:
                obj.pop("_id", None)
                obj.pop("_collection_id", None)
                obj.pop("_date_added", None)
        return total, create_bundle(objects_found)

    @catch_mongodb_error
    def add_objects(self, api_root, collection_id, objs, request_time):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
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
                existing_entry = objects_info.find_one(mongo_query)
                obj_version = determine_version(new_obj, request_time)
                if existing_entry:
                    failures.append({
                        "id": new_obj["id"],
                        "message": "Unable to process object because identical version exist.",
                    })
                    failed += 1
                else:
                    new_obj.update({"_collection_id": collection_id})
                    if not all(prop in new_obj for prop in ("modified", "created")):
                        new_obj["_date_added"] = obj_version  # Special case for un-versioned objects
                    objects_info.insert_one(new_obj)
                    self._update_manifest(new_obj, api_root, collection_id, request_time)
                    successes.append(new_obj["id"])
                    succeeded += 1
        except Exception as e:
            log.exception(e)
            raise ProcessingError("While processing supplied content, an error occurred", 422, e)

        status = generate_status(
            format_datetime(request_time), "complete", succeeded, failed,
            pending, successes_ids=successes, failures=failures,
        )
        api_root_db["status"].insert_one(status)
        status.pop("_id", None)
        return status

    @catch_mongodb_error
    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": collection_id, "id": object_id},
            allowed_filters,
        )
        count, objects_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": collection_id},
        )
        if objects_found:
            for obj in objects_found:
                if obj:
                    obj.pop("_id", None)
                    obj.pop("_collection_id", None)
                    obj.pop("_date_added", None)
        return create_bundle(objects_found)
