import logging

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from medallion.exceptions import MongoBackendError, ProcessingError
from medallion.filters.mongodb_filter import MongoDBFilter
from medallion.utils.common import (create_bundle, format_datetime,
                                    generate_status, get_timestamp)

from .base import Backend

# Module-level logger
log = logging.getLogger(__name__)


def catch_mongodb_error(func):
    """catch mongodb availability error"""

    def api_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ConnectionFailure, ServerSelectionTimeoutError) as err:
            raise MongoBackendError("Unable to connect to MongoDB", err)

    return api_wrapper


class MongoBackend(Backend):

    # access control is handled at the views level

    def __init__(self, uri=None, **kwargs):
        try:
            self.client = MongoClient(uri)
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command("ismaster")
        except ConnectionFailure:
            log.error("Unable to establish a connection to MongoDB server {}".format(uri))

    @catch_mongodb_error
    def _update_manifest(self, new_obj, api_root, _collection_id):
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        entry = manifest_info.find_one(
            {"_collection_id": _collection_id, "id": new_obj["id"]}
        )
        if entry:
            if "modified" in new_obj:
                entry["versions"].append(new_obj["modified"])
                manifest_info.update_one(
                    {"_collection_id": _collection_id, "id": new_obj["id"]},
                    {"$set": {"versions": sorted(entry["versions"], reverse=True)}}
                )
            # If the new_obj is there, and it has no modified property,
            # then it is immutable, and there is nothing to do.
        else:
            version = new_obj.get("modified", new_obj["created"])
            manifest_info.insert_one(
                {"id": new_obj["id"],
                 "_collection_id": _collection_id,
                 "_type": new_obj["type"],
                 "date_added": get_timestamp(),
                 "versions": [version],
                 "media_types": ["application/vnd.oasis.stix+json; version=2.0"]}
            )  # media_types hardcoded for now...

    @catch_mongodb_error
    def server_discovery(self):
        discovery_db = self.client["discovery_database"]
        collection = discovery_db["discovery_information"]
        pipeline = [{
            "$lookup": {
                "from": "api_root_info",
                "localField": "api_roots",
                "foreignField": "_name",
                "as": "roots"
            }
        }, {
            "$project": {
                "_id": 0,
                "title": 1,
                "description": 1,
                "contact": 1,
                "api_roots": "$roots._url"
            }
        }]
        info = list(collection.aggregate(pipeline))[0]
        return info

    @catch_mongodb_error
    def get_collections(self, api_root, start_index, end_index):
        if api_root not in self.client.list_database_names():
            return None, None   # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        count = collection_info.count()

        pipeline = [{'$match': {}}, {'$sort': {'_id': 1}}]
        pipeline.append({"$skip": start_index})
        pipeline.append({"$limit": (end_index - start_index) + 1})
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
            page_size
        )
        total, objects_found = full_filter.process_filter(manifest_info,
                                                          allowed_filters, None)
        if objects_found:
            for obj in objects_found:
                if obj:
                    obj.pop("_id", None)
                    obj.pop("_collection_id", None)
                    obj.pop("_type", None)
                    # format date_added which is an ISODate object
                    obj['date_added'] = format_datetime(obj['date_added'])
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
            page_size
        )
        # Note: error handling was not added to following call as mongo will
        # handle (user supplied) filters gracefully if they don't exist
        total, objects_found = full_filter.process_filter(
            objects,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": id_}
        )
        for obj in objects_found:
            if obj:
                obj.pop("_id", None)
                obj.pop("_collection_id", None)
        return total, create_bundle(objects_found)

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
                    failures.append({"id": new_obj["id"],
                                     "message": "Unable to process object"})
                    failed += 1
                else:
                    new_obj.update({"_collection_id": collection_id})
                    objects.insert_one(new_obj)
                    self._update_manifest(new_obj, api_root, collection_id)
                    successes.append(new_obj["id"])
                    succeeded += 1
        except Exception as e:
            raise ProcessingError("While processing supplied content, an error occurred", e)

        status = generate_status(request_time, "complete", succeeded, failed,
                                 pending, successes_ids=successes, failures=failures)
        api_root_db["status"].insert_one(status)
        status.pop("_id", None)
        return status

    @catch_mongodb_error
    def get_object(self, api_root, id_, object_id, filter_args, allowed_filters):
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": id_, "id": object_id},
            allowed_filters
        )
        count, objects_found = full_filter.process_filter(
            objects,
            allowed_filters,
            {"mongodb_collection": api_root_db["manifests"], "_collection_id": id_}
        )
        if objects_found:
            for obj in objects_found:
                if obj:
                    obj.pop("_id", None)
                    obj.pop("_collection_id", None)
        return create_bundle(objects_found)
