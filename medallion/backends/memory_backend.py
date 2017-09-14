import copy
import json

from six import StringIO

from medallion.filters.basic_filter import BasicFilter
from medallion.utils.builder import create_bundle
from medallion.utils.common import (format_datetime, generate_status,
                                    get_timestamp, iterpath)

from .base import Backend


class MemoryBackend(Backend):

    # access control is handled at the views level

    def __init__(self):
        self.data = {}

    def load_data_from_file(self, filename):
        self.data = json.load(StringIO(open(filename, "r").read()))

    def save_data_to_file(self, filename):
        with open(filename, 'w') as outfile:
            json.dump(self.data,
                      outfile,
                      indent=4,
                      separators=(',', ': '),
                      sort_keys=True)

    def _get(self, key):
        for ancestors, item in iterpath(self.data):
            if key in ancestors:
                return item

    def server_discovery(self):
        return self._get("/discovery")

    def _update_manifest(self, new_obj, api_root, collection_id):
        api_info = self._get(api_root)
        collections = api_info.get("collections", [])

        for collection in collections:
            if "id" in collection and collection_id == collection["id"]:
                for entry in collection["manifest"]:
                    if entry["id"] == new_obj["id"]:
                        # only called when modified is different
                        entry["versions"].append(new_obj["modified"])
                        return
                collection["manifest"].append({"id": new_obj["id"],
                                               "date_added": format_datetime(get_timestamp()),
                                               "versions": [new_obj["modified"]],
                                               # hardcoded for nowmed
                                               "media_types": ["application/vnd.oasis.stix+json; version=2.0"]})

    def get_collections(self, api_root):

        if api_root in self.data:
            api_info = self._get(api_root)
            result = dict(collections=copy.deepcopy(api_info.get("collections", [])))

            # Remove data that is not part of the response.
            for collection in result["collections"]:
                if "manifest" in collection:
                    del collection["manifest"]
                if "responses" in collection:
                    del collection["responses"]
                if "objects" in collection:
                    del collection["objects"]
            return result
        return None

    def get_collection(self, api_root, id_):

        if api_root in self.data:
            api_info = self._get(api_root)
            collections = copy.deepcopy(api_info.get("collections", []))

            for collection in collections:
                if "id" in collection and id_ == collection["id"]:
                    if "manifest" in collection:
                        del collection["manifest"]
                    if "responses" in collection:
                        del collection["responses"]
                    if "objects" in collection:
                        del collection["objects"]
                    return collection
        return None

    def get_object_manifest(self, api_root, id_, filter_args, allowed_filters):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            for collection in collections:
                if "id" in collection and id_ == collection["id"]:
                    manifest = collection.get("manifest", [])
                    if filter_args:
                        full_filter = BasicFilter(filter_args)
                        manifest = full_filter.process_filter(manifest, allowed_filters, None)
                    return manifest
        return None

    def get_api_root_information(self, api_root):

        if api_root in self.data:
            api_info = self._get(api_root)

            if "information" in api_info:
                return api_info["information"]

        return None

    def get_status(self, api_root, id_):

        if api_root in self.data:
            api_info = self._get(api_root)

            for status in api_info.get("status", []):
                if id_ == status["id"]:
                    return status

        return None

    def get_objects(self, api_root, id_, filter_args, allowed_filters):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            objs = []
            for collection in collections:
                if "id" in collection and id_ == collection["id"]:

                    if filter_args:
                        full_filter = BasicFilter(filter_args)
                        objs.extend(full_filter.process_filter(collection.get("objects", []),
                                                               allowed_filters,
                                                               collection.get("manifest", [])))
                    else:
                        objs.extend(collection.get("objects", []))
            return create_bundle(objs)

        return None

    def add_objects(self, api_root, id_, objs, request_time):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            for collection in collections:
                if "id" in collection and id_ == collection["id"]:
                    if "objects" not in collection:
                        collection["objects"] = []
                    failed = 0
                    succeeded = 0
                    for new_obj in objs["objects"]:
                        found = False
                        for current_obj in collection["objects"]:
                            if new_obj['id'] == current_obj['id'] and new_obj['modified'] == current_obj['modified']:
                                found = True
                                break
                        if not found:
                            collection["objects"].append(new_obj)
                            self._update_manifest(new_obj, api_root, collection["id"])
                            succeeded += 1
                        else:
                            failed += 1

            status = generate_status(request_time, succeeded, failed, 0)
            api_info["status"].append(status)
            return status

    def get_object(self, api_root, id_, object_id, filter_args, allowed_filters):

        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            objs = []
            for collection in collections:
                if "id" in collection and id_ == collection["id"]:
                    for obj in collection.get("objects", []):
                        if object_id == obj["id"]:
                            objs.append(obj)
                if filter_args:
                    full_filter = BasicFilter(filter_args)
                    objs = full_filter.process_filter(objs,
                                                      allowed_filters,
                                                      collection.get("manifest", []))
            return create_bundle(objs)

        return None
