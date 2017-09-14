from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from medallion.filters.mongodb_filter import MongoDBFilter
from medallion.utils.builder import create_bundle
from medallion.utils.common import (format_datetime, generate_status,
                                    get_timestamp)

from .base import Backend


class MongoBackend(Backend):

    # access control is handled at the views level

    def __init__(self, uri):
        try:
            self.client = MongoClient(uri)
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command('ismaster')
        except ConnectionFailure:
            print("Mongo DB not available")

    def _update_manifest(self, new_obj, api_root, collection_id):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        entry = manifest_info.find_one({"collection_id": collection_id, "id": new_obj["id"]})
        if entry:
            entry["versions"].append(new_obj["modified"])
            manifest_info.update_one({"collection_id": collection_id, "id": new_obj["id"]}, {"$set": {"versions": entry["versions"]}})
            return
        manifest_info.insert_one({"id": new_obj["id"],
                                  "collection_id": collection_id,
                                  "date_added": format_datetime(get_timestamp()),
                                  "versions": [new_obj["modified"]],
                                  # hardcoded for now
                                  "media_types": ["application/vnd.oasis.stix+json; version=2.0"]
                                  })

    def server_discovery(self):
        # TODO: Handle if mongodb is not available
        discovery_db = self.client["discovery_database"]
        collection = discovery_db["discovery_information"]
        info = collection.find_one()
        del info["_id"]
        return info

    def get_collections(self, api_root):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        collections = list(collection_info.find({}))
        for c in collections:
            del c["_id"]
        return {'collections': collections}

    def get_collection(self, api_root, id_):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        return collection_info.find_one({"id": id_})

    def get_object_manifest(self, api_root, id_, filter_args, allowed_filters):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        manifest_info = api_root_db["manifests"]
        full_filter = MongoDBFilter(filter_args, {"collection_id": id_}, allowed_filters)
        objects_found = full_filter.process_filter(manifest_info, allowed_filters, None)
        if objects_found:
            for obj in objects_found:
                del obj["_id"]
                del obj["collection_id"]
        return objects_found

    def get_api_root_information(self, api_root):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        api_root_info = api_root_db["api_root_info"]
        info = api_root_info.find_one()
        if info:
            del info["_id"]
        return info

    def get_status(self, api_root, id_):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        status_info = api_root_db["status"]
        result = status_info.find_one({"id": id_})
        if result:
            del result["_id"]
        return result

    def get_objects(self, api_root, id_, filter_args, allowed_filters):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        full_filter = MongoDBFilter(filter_args, {"collection_id": id_}, allowed_filters)
        objects_found = full_filter.process_filter(objects,
                                                   allowed_filters,
                                                   {"mongodb_collection": api_root_db["manifests"],
                                                    "collection_id": id_})
        for obj in objects_found:
            del obj["_id"]
            del obj["collection_id"]
        return create_bundle(objects_found)

    def add_objects(self, api_root, id_, objs, request_time):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        failed = 0
        succeeded = 0
        for new_obj in objs["objects"]:
            existing_entry = objects.find_one({"collection_id": id_,
                                               "id": new_obj["id"],
                                               "modified": new_obj["modified"]})
            if existing_entry:
                failed += 1
            else:
                new_obj.update({"collection_id": id_})
                objects.insert_one(new_obj)
                self._update_manifest(new_obj, api_root, id_)
                succeeded += 1

        status = generate_status(request_time, succeeded, failed, 0)
        api_root_db["status"].insert_one(status)
        del status["_id"]
        return status

    def get_object(self, api_root, id_, object_id, filter_args, allowed_filters):
        # TODO: Handle if mongodb is not available
        api_root_db = self.client[api_root]
        objects = api_root_db["objects"]
        full_filter = MongoDBFilter(filter_args, {"collection_id": id_, "id": object_id}, allowed_filters)
        objects_found = full_filter.process_filter(objects,
                                                   allowed_filters,
                                                   {"mongodb_collection": api_root_db["manifests"], "collection_id": id_})
        if objects_found:
            for obj in objects_found:
                del obj["_id"]
                del obj["collection_id"]
        return create_bundle(objects_found)
