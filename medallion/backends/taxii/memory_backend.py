import codecs
import copy
import json
import logging

from ...exceptions import ProcessingError
from ...filters.basic_filter import BasicFilter
from ...utils.common import (create_bundle, determine_spec_version,
                             determine_version, format_datetime,
                             generate_status, iterpath)
from .base import Backend

# Module-level logger
log = logging.getLogger(__name__)


class MemoryBackend(Backend):

    # access control is handled at the views level

    def __init__(self, **kwargs):
        filename = kwargs.get("filename")
        if filename:
            self.load_data_from_file(filename)
        else:
            self.data = {}

    def load_data_from_file(self, filename):
        with codecs.open(filename, mode="r", encoding="utf8") as infile:
            self.data = json.load(infile)

    def save_data_to_file(self, filename, **kwargs):
        """The kwargs are passed to ``json.dump()`` if provided."""
        with codecs.open(filename, mode="w", encoding="utf8") as outfile:
            json.dump(self.data, outfile, **kwargs)

    def _get(self, key):
        for ancestors, item in iterpath(self.data):
            if key in ancestors:
                return item

    def _update_manifest(self, new_obj, api_root, collection_id, request_time):
        api_info = self._get(api_root)
        collections = api_info.get("collections", [])
        media_type_fmt = "application/vnd.oasis.stix+json; version={}"
        media_type = media_type_fmt.format(determine_spec_version(new_obj))
        version = determine_version(new_obj, request_time)
        request_time = format_datetime(request_time)

        for collection in collections:
            if collection_id == collection["id"]:
                if "manifest" not in collection:
                    collection["manifest"] = []
                for entry in collection["manifest"]:
                    if new_obj["id"] == entry["id"]:
                        if "modified" in new_obj:
                            entry["versions"].append(version)
                            entry["versions"] = sorted(entry["versions"], reverse=True)
                        # If the new_obj is there, and it has no modified
                        # property, then it is immutable, and there is nothing
                        # to do.
                        break
                else:
                    collection["manifest"].append(
                        {
                            "id": new_obj["id"],
                            "date_added": request_time,
                            "versions": [version],
                            "media_types": [media_type],
                        },
                    )

                # if the media type is new, attach it to the collection
                if media_type not in collection["media_types"]:
                    collection["media_types"].append(media_type)

                # quit once you have found the collection that needed updating
                break

    def server_discovery(self):
        if "/discovery" in self.data:
            return self._get("/discovery")

    def get_collections(self, api_root, start_index, end_index):
        if api_root not in self.data:
            return None, None  # must return None so 404 is raised

        api_info = self._get(api_root)
        collections = copy.deepcopy(api_info.get("collections", []))
        count = len(collections)

        collections = collections[start_index:end_index]
        # Remove data that is not part of the response.
        for collection in collections:
            collection.pop("manifest", None)
            collection.pop("objects", None)
        return count, collections

    def get_collection(self, api_root, collection_id):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = copy.deepcopy(api_info.get("collections", []))

            for collection in collections:
                if collection_id == collection["id"]:
                    collection.pop("manifest", None)
                    collection.pop("objects", None)
                    return collection

    def get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters, start_index, end_index):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            for collection in collections:
                if collection_id == collection["id"]:
                    full_filter = BasicFilter(filter_args)
                    manifest = full_filter.process_filter(
                        collection.get("manifest", []),
                        allowed_filters,
                        None,
                    )

                    count = len(manifest)
                    result = manifest[start_index:end_index]
                    return count, result

    def get_api_root_information(self, api_root):
        if api_root in self.data:
            api_info = self._get(api_root)

            if "information" in api_info:
                return api_info["information"]

    def get_status(self, api_root, status_id):
        if api_root in self.data:
            api_info = self._get(api_root)

            for status in api_info.get("status", []):
                if status_id == status["id"]:
                    return status

    def get_objects(self, api_root, collection_id, filter_args, allowed_filters, start_index, end_index):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])
            objs = []

            for collection in collections:
                if collection_id == collection["id"]:
                    full_filter = BasicFilter(filter_args)
                    objs = full_filter.process_filter(
                        collection.get("objects", []),
                        allowed_filters,
                        collection.get("manifest", []),
                    )
                    break

            count = len(objs)
            result = objs[start_index:end_index]
            return count, create_bundle(result)

    def add_objects(self, api_root, collection_id, objs, request_time):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])
            failed = 0
            succeeded = 0
            pending = 0
            successes = []
            failures = []

            for collection in collections:
                if collection_id == collection["id"]:
                    if "objects" not in collection:
                        collection["objects"] = []
                    try:
                        for new_obj in objs["objects"]:
                            id_and_version_already_present = False
                            for obj in collection["objects"]:
                                if new_obj["id"] == obj["id"]:
                                    if "modified" in new_obj and new_obj["modified"] == obj["modified"]:
                                        id_and_version_already_present = True
                                        break
                                    else:
                                        # There is no modified field, so this object is immutable
                                        id_and_version_already_present = True
                                        break
                            if id_and_version_already_present is False:
                                collection["objects"].append(new_obj)
                                self._update_manifest(new_obj, api_root, collection["id"], request_time)
                                successes.append(new_obj["id"])
                                succeeded += 1
                            else:
                                failures.append({
                                    "id": new_obj["id"],
                                    "message": "Unable to process object because identical version exist."
                                })
                                failed += 1
                    except Exception as e:
                        log.exception(e)
                        raise ProcessingError("While processing supplied content, an error occurred", 422, e)

            status = generate_status(
                format_datetime(request_time), "complete", succeeded,
                failed, pending, successes_ids=successes,
                failures=failures,
            )
            api_info["status"].append(status)
            return status

    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            objs = []
            manifests = []
            for collection in collections:
                if collection_id == collection["id"]:
                    for obj in collection.get("objects", []):
                        if object_id == obj["id"]:
                            objs.append(obj)
                    manifests = collection.get("manifest", [])
                    break

            full_filter = BasicFilter(filter_args)
            objs = full_filter.process_filter(
                objs,
                allowed_filters,
                manifests
            )
            return create_bundle(objs)
