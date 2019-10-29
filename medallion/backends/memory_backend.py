import copy
import json

from ..exceptions import ProcessingError
from ..filters.basic_filter import BasicFilter
from ..utils.common import (create_resource, determine_spec_version,
                            determine_version, format_datetime,
                            generate_status, generate_status_details, iterpath)
from .base import Backend


class MemoryBackend(Backend):

    # access control is handled at the views level

    def __init__(self, **kwargs):
        if kwargs.get("filename"):
            self.load_data_from_file(kwargs.get("filename"))
        else:
            self.data = {}

    def load_data_from_file(self, filename):
        with open(filename, "r") as infile:
            self.data = json.load(infile)

    def save_data_to_file(self, filename, **kwargs):
        """The kwargs are passed to ``json.dump()`` if provided."""
        with open(filename, "w") as outfile:
            json.dump(self.data, outfile, **kwargs)

    def _get(self, key):
        for ancestors, item in iterpath(self.data):
            if key in ancestors:
                return item

    def server_discovery(self):
        return self._get("/discovery")

    def _update_manifest(self, new_obj, api_root, collection_id, request_time):
        api_info = self._get(api_root)
        collections = api_info.get("collections", [])
        media_type_fmt = "application/stix+json;version={}"

        for collection in collections:
            if "id" in collection and collection_id == collection["id"]:
                version = determine_version(new_obj, request_time)
                request_time = format_datetime(request_time)
                media_type = media_type_fmt.format(determine_spec_version(new_obj))

                # version is a single value now, therefore a new manifest is always created
                collection["manifest"].append(
                    {
                        "id": new_obj["id"],
                        "date_added": request_time,
                        "version": version,
                        "media_type": media_type,
                    },
                )

                # if the media type is new, attach it to the collection
                if media_type not in collection["media_types"]:
                    collection["media_types"].append(media_type)

                # quit once you have found the collection that needed updating
                break

    def get_collections(self, api_root):
        if api_root not in self.data:
            return None  # must return None so 404 is raised

        api_info = self._get(api_root)
        collections = copy.deepcopy(api_info.get("collections", []))

        # Remove data that is not part of the response.
        for collection in collections:
            collection.pop("manifest", None)
            collection.pop("responses", None)
            collection.pop("objects", None)
        return create_resource("collections", collections)

    def get_collection(self, api_root, collection_id):
        if api_root not in self.data:
            return None  # must return None so 404 is raised

        api_info = self._get(api_root)
        collections = copy.deepcopy(api_info.get("collections", []))

        for collection in collections:
            if "id" in collection and collection_id == collection["id"]:
                collection.pop("manifest", None)
                collection.pop("responses", None)
                collection.pop("objects", None)
                return collection

    def get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            for collection in collections:
                if "id" in collection and collection_id == collection["id"]:
                    manifest = collection.get("manifest", [])
                    full_filter = BasicFilter(filter_args)
                    manifest = full_filter.process_filter(
                        manifest,
                        allowed_filters,
                        None,
                    )
                    return create_resource("objects", manifest)

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

    def get_objects(self, api_root, collection_id, filter_args, allowed_filters):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            objs = []
            for collection in collections:
                if "id" in collection and collection_id == collection["id"]:

                    full_filter = BasicFilter(filter_args)
                    objs.extend(
                        full_filter.process_filter(
                            collection.get("objects", []),
                            allowed_filters,
                            collection.get("manifest", []),
                        ),
                    )

            return create_resource("objects", objs)

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
                if "id" in collection and collection_id == collection["id"]:
                    if "objects" not in collection:
                        collection["objects"] = []
                    try:
                        for new_obj in objs["objects"]:
                            id_and_version_already_present = False
                            for obj in collection["objects"]:
                                id_and_version_already_present = False

                                if new_obj["id"] == obj["id"]:
                                    if "modified" in new_obj:
                                        if new_obj["modified"] == obj["modified"]:
                                            id_and_version_already_present = True
                                    else:
                                        # There is no modified field, so this object is immutable
                                        id_and_version_already_present = True
                            if not id_and_version_already_present:
                                collection["objects"].append(new_obj)
                                self._update_manifest(new_obj, api_root, collection["id"], request_time)
                                status_details = generate_status_details(
                                    new_obj["id"], determine_version(new_obj, request_time)
                                )
                                successes.append(status_details)
                                succeeded += 1
                            else:
                                status_details = generate_status_details(
                                    new_obj["id"], determine_version(new_obj, request_time),
                                    message="Unable to process object",
                                )
                                failures.append(status_details)
                                failed += 1
                    except Exception as e:
                        raise ProcessingError("While processing supplied content, an error occurred", 422, e)

            status = generate_status(
                format_datetime(request_time), "complete", succeeded,
                failed, pending, successes=successes,
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
                if "id" in collection and collection_id == collection["id"]:
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
            return create_resource("objects", objs)

    def get_object_versions(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        if api_root in self.data:
            api_info = self._get(api_root)
            collections = api_info.get("collections", [])

            objs = []
            for collection in collections:
                if "id" in collection and collection_id == collection["id"]:
                    all_manifests = collection.get("manifest", [])
                    for manifest in all_manifests:
                        if object_id == manifest["id"]:
                            objs.append(manifest)
                    # if filter_args:
                    full_filter = BasicFilter(filter_args)
                    objs = full_filter.process_filter(
                        objs,
                        allowed_filters,
                        None,
                    )
                    objs = sorted(map(lambda x: x["version"], objs), reverse=True)
                    return create_resource("versions", objs)
