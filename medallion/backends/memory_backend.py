import json
import logging
import os
import uuid

import environ

from ..common import (
    APPLICATION_INSTANCE, create_resource, datetime_to_float,
    datetime_to_string, determine_spec_version, generate_status,
    generate_status_details, get_application_instance_config_values,
    get_timestamp, string_to_datetime
)
from ..exceptions import MemoryBackendError, ProcessingError
from ..filters.basic_filter import BasicFilter
from .base import Backend

# Module-level logger
log = logging.getLogger(__name__)


class Meta:
    """
    Contains metadata about a STIX object, for use in the memory backend.
    Having this allows me to have data which is useful but should not be
    stored in the memory backend datafile.  Having a custom type lets me
    customize JSON-serialization.
    """
    def __init__(self, date_added, media_type, version):
        if isinstance(date_added, str):
            self.date_added = string_to_datetime(date_added)
        else:
            self.date_added = date_added

        if isinstance(version, str):
            self.version = string_to_datetime(version)
        else:
            self.version = version

        self.media_type = media_type

    def __repr__(self):
        return 'Meta("{}", "{}", "{}")'.format(
            datetime_to_string(self.date_added),
            self.media_type,
            datetime_to_string(self.version)
        )


def _metafy_object(obj, *, date_added=None, media_type=None):
    """
    Given a plain STIX object or object with a __meta key from the memory
    backend data file, replace/add the value of __meta with an instance of
    the Meta class, containing handy metadata.

    :param obj: The object to metafy
    :param date_added: A value to use for date_added; the value from a
        pre-existing __meta object is preferred, if it exists.  This is just a
        fallback.
    :param media_type: A value to use for media_type; the value from a
        pre-existing __meta object is preferred, if it exists.  This is just a
        fallback.
    """
    obj_meta = obj.get("__meta", {})
    date_added = obj_meta.get("date_added", date_added)
    media_type = obj_meta.get("media_type", media_type)
    version = obj.get("modified") or obj.get("created") or date_added

    if not date_added:
        # Should not happen.  We are responsible for maintaining our own
        # date_added timestamps.
        raise MemoryBackendError(
            "Internal error: object lacks a date_added timestamp:"
            " {}/{}".format(
                obj["id"], version
            ),
            500
        )

    if not media_type:
        # Again, should not happen.  Clients don't give us media types in their
        # requests.  We need to figure it out for ourselves.
        raise MemoryBackendError(
            "Internal error: object lacks a media_type: {}/{}".format(
                obj["id"], version
            ),
            500
        )

    obj["__meta"] = Meta(date_added, media_type, version)


def meta_decoder(obj):
    """A function used as a JSON decoder hook to instantiate Meta objects."""
    if "__meta" in obj:
        _metafy_object(obj)

    return obj


class MetaEncoder(json.JSONEncoder):
    """
    The JSON encoder associated with the above Meta class.  Ensures meta
    properties which should not be written to the data file, are masked.
    """
    def default(self, value):
        if isinstance(value, Meta):
            return {
                "date_added": datetime_to_string(value.date_added),
                "media_type": value.media_type
            }
        return super().default(value)


def _make_plain_objects(objs):
    """
    From an iterable of memory backend object structures (which contain both
    the STIX object and associated metadata), create a list of plain STIX
    object structures.  This removes any "extra" implementation detail stuff,
    like the "__meta" key.  A new list is returned; the given list is not
    modified.

    :param objects: iterable of merged object/manifest structures
    :return: list of plain STIX objects
    """
    plain_objs = []
    for obj in objs:
        # Shallow copy, to share object substructure, to reduce memory usage.
        obj_copy = obj.copy()
        obj_copy.pop("__meta", None)
        plain_objs.append(obj_copy)

    return plain_objs


def _make_manifests(objects):
    """
    From an iterable of memory backend object structures (which contain both
    the STIX object and associated metadata), create a list of manifest
    resources.

    :param objects: iterable of merged object/manifest structures
    :return: list of manifest resources
    """
    manifests = [
        {
            "id": obj["id"],
            "date_added": datetime_to_string(obj["__meta"].date_added),
            "version": datetime_to_string(obj["__meta"].version),
            "media_type": obj["__meta"].media_type
        }

        for obj in objects
    ]

    return manifests


class MemoryBackend(Backend):

    # access control is handled at the views level

    @environ.config(prefix="MEMORY")
    class Config(object):
        filename = environ.var(None)

    def __init__(self, **kwargs):
        # Refuse to run under a WSGI server since this is an internal backend
        if (
            "SERVER_SOFTWARE" in os.environ and
            kwargs.get("force_wsgi", False) is not True
        ):
            raise RuntimeError(
                "The memory backend should not be run by a WSGI server since "
                "it does not provide an external data backend. "
                "Set the 'force_wsgi' backend option to true to skip this."
            )
        if "filename" in kwargs:
            self.__discovery, self.__api_roots = \
                self.load_data_from_file(kwargs.get("filename"))
        else:
            self.__discovery = {}
            self.__api_roots = {}
        super(MemoryBackend, self).__init__(**kwargs)

    def _pop_expired_sessions(self):
        expired_ids = []
        boundary = datetime_to_float(get_timestamp())
        for next_id, record in self.next.items():
            if boundary - record["request_time"] > self.timeout:
                expired_ids.append(next_id)

        for item in expired_ids:
            self.next.pop(item)

    def _pop_old_statuses(self):
        api_roots = self._get_all_api_roots()
        boundary = datetime_to_float(get_timestamp())
        ids_to_del = []
        for ar in api_roots:
            status_map = self.__api_roots.get(ar, {}).get("status", {})
            ids_to_del.clear()
            for status_id, status in status_map.items():
                status_age = boundary - datetime_to_float(string_to_datetime(status["request_timestamp"]))
                if status_age > self.status_retention:
                    ids_to_del.append(status_id)

            for status_id in ids_to_del:
                del status_map[status_id]
                log.info("Status {} was deleted from {} because it was older than the status retention time".format(status_id, ar))

    def set_next(self, objects, args):
        u = str(uuid.uuid4())
        args.pop("limit", None)
        for arg in args:
            new_list = args[arg].split(',')
            new_list.sort()
            args[arg] = new_list
        d = {"objects": objects, "args": args, "request_time": datetime_to_float(get_timestamp())}
        self.next[u] = d
        return u

    def get_next(self, filter_args, lim):
        n = filter_args["next"]
        paging_record = self.next.get(n)
        if paging_record:
            for arg in filter_args:
                new_list = filter_args[arg].split(',')
                new_list.sort()
                filter_args[arg] = new_list
            del filter_args["next"]
            filter_args.pop("limit", None)
            if filter_args != paging_record["args"]:
                raise ProcessingError("The server did not understand the request or filter parameters: params changed over subsequent transaction", 400)

            remaining_objs = paging_record["objects"]
            next_page = remaining_objs[:lim]
            remaining_objs = remaining_objs[lim:]

            if remaining_objs:
                paging_record["objects"] = remaining_objs
                more = True
            else:
                self.next.pop(n)
                more = False

            headers = {
                "X-TAXII-Date-Added-First": datetime_to_string(
                    next_page[0]["__meta"].date_added
                ),
                "X-TAXII-Date-Added-Last": datetime_to_string(
                    next_page[-1]["__meta"].date_added
                )
            }

            return next_page, more, headers
        else:
            raise ProcessingError("The server did not understand the request or filter parameters: 'next' not valid", 400)

    def load_data_from_file(self, filename):
        if isinstance(filename, str):
            with open(filename, "r", encoding="utf-8") as infile:
                data = json.load(infile, object_hook=meta_decoder)
        else:
            data = json.load(filename, object_hook=meta_decoder)

        api_roots = data
        discovery = data.pop("/discovery")

        return discovery, api_roots

    def save_data_to_file(self, filename, **kwargs):
        """The kwargs are passed to ``json.dump()`` if provided."""
        file_contents = {
            "/discovery": self.__discovery,
            **self.__api_roots
        }
        if isinstance(filename, str):
            with open(filename, "w", encoding="utf-8") as outfile:
                json.dump(file_contents, outfile, cls=MetaEncoder, **kwargs)
        else:
            json.dump(file_contents, filename, cls=MetaEncoder, **kwargs)

    def server_discovery(self):
        return self.__discovery

    def get_collections(self, api_root_name):
        api_root = self.__api_roots.get(api_root_name)
        if not api_root:
            return None  # must return None so 404 is raised

        collections = api_root.get("collections", {})
        collection_resources = []
        # Remove data that is not part of the response.
        for collection_id, collection in collections.items():
            collection = collection.copy()
            collection.pop("objects", None)
            collection["id"] = collection_id  # just in case
            collection_resources.append(collection)
        # interop wants results sorted by id
        if get_application_instance_config_values(APPLICATION_INSTANCE, "taxii", "interop_requirements"):
            collection_resources = sorted(collection_resources, key=lambda o: o["id"])

        return create_resource("collections", collection_resources)

    def get_collection(self, api_root, collection_id):
        collection = self.__api_roots.get(api_root, {}) \
            .get("collections", {}) \
            .get(collection_id)

        if not collection:
            return None  # must return None so 404 is raised

        collection = collection.copy()
        collection.pop("objects", None)
        collection["id"] = collection_id  # just in case

        return collection

    def _get_objects(
        self, api_root, collection_id, filter_args, allowed_filters,
        limit
    ):
        """
        Search/page the given collection via the given filters.  If filter_args
        contains a "next" parameter, a paging record is looked up and consulted;
        the collection is not searched.

        :param api_root: An API root name
        :param collection_id: A collection ID
        :param filter_args: HTTP filtering query parameters
        :param allowed_filters: Tuple of allowed filter names
        :param limit: A page size limit; may be less than requested in HTTP
            query parameters due to server-enforced max page size
        :return: None if API root or collection were not found; a 4-tuple
            otherwise.  The 4-tuple contains: (list of objects in the first/next
            page, a "more" boolean value representing whether there are any
            more pages, paging key for use in a TAXII envelope or similar
            resource to get subsequent pages, map containing special
            X-TAXII-Date-Added-First/Last headers to be added to an HTTP
            response).  If no matching objects were found,
            ([], False, None, {}) is returned.
        """
        collection = self.__api_roots.get(api_root) \
            .get("collections", {}) \
            .get(collection_id)

        result = None
        if collection:

            paging_key = filter_args.get("next")
            if paging_key:
                page_objects, more, headers = self.get_next(filter_args, limit)
            else:
                objects = collection.get("objects", [])
                full_filter = BasicFilter(filter_args)
                page_objects, next_save, headers = full_filter.process_filter(
                    objects,
                    allowed_filters,
                    limit
                )

                if next_save:
                    more = True
                    paging_key = self.set_next(next_save, filter_args)
                else:
                    more = False

            result = page_objects, more, paging_key, headers

        return result

    def get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters, limit):

        result = self._get_objects(
            api_root, collection_id, filter_args, allowed_filters, limit
        )

        manifest_resource = headers = None
        if result:
            page_objects, more, paging_key, headers = result

            manifests = _make_manifests(page_objects)
            manifest_resource = create_resource("objects", manifests, more, paging_key)

        return manifest_resource, headers

    def get_api_root_information(self, api_root_name):
        api_info = self.__api_roots.get(api_root_name, {}).get("information")

        return api_info

    def _get_api_root_statuses(self, api_root_name):
        status_map = self.__api_roots.get(api_root_name, {}).get("status", {})
        return status_map.values()

    def get_status(self, api_root_name, status_id):
        status = self.__api_roots.get(api_root_name, {}) \
            .get("status", {}) \
            .get(status_id)

        if status is not None:
            status["id"] = status_id  # just in case

        return status

    def get_objects(self, api_root, collection_id, filter_args, allowed_filters, limit):

        result = self._get_objects(
            api_root, collection_id, filter_args, allowed_filters, limit
        )

        envelope_resource = headers = None
        if result:
            page_objects, more, paging_key, headers = result

            page_objects = _make_plain_objects(page_objects)
            envelope_resource = create_resource("objects", page_objects, more, paging_key)

        return envelope_resource, headers

    def _add_status(self, api_root_name, status):
        api_root = self.__api_roots.get(api_root_name)
        if api_root:
            status_map = api_root.get("status")
            if status_map is None:
                status_map = {}
                api_root["status"] = status_map

            status_map[status["id"]] = status

    def add_objects(self, api_root_name, collection_id, objs, request_time):

        api_root = self.__api_roots.get(api_root_name)
        if api_root:
            collection = api_root.get("collections", {}).get(collection_id)

        status = None
        if collection:
            successes = []
            failures = []

            collection_objects = collection.get("objects")
            if collection_objects is None:
                collection_objects = []
                collection["objects"] = collection_objects

            if not isinstance(objs, dict):
                raise ProcessingError(
                    "Invalid TAXII envelope", 422
                )

            if "objects" not in objs:
                raise ProcessingError(
                    'Invalid TAXII envelope: missing "objects" property', 422
                )

            for new_obj in objs["objects"]:

                if not isinstance(new_obj, dict):
                    failures.append(
                        generate_status_details(
                            "<unknown id>",
                            "<unknown version>",
                            "Not an object: " + str(new_obj)
                        )
                    )
                    continue

                spec_version = determine_spec_version(new_obj)
                media_type = "application/stix+json;version=" \
                             + spec_version

                try:

                    _metafy_object(
                        new_obj,
                        date_added=request_time,
                        media_type=media_type
                    )

                    id_and_version_already_present = False
                    for obj in collection_objects:
                        if new_obj["id"] == obj["id"] \
                                and new_obj["__meta"].version == obj["__meta"].version:
                            id_and_version_already_present = True
                            break

                    if id_and_version_already_present:
                        message = "Object already added"

                    else:
                        message = None

                        collection_objects.append(new_obj)

                        # if the media type is new, attach it to the collection
                        # (Note: aren't we supposed to be enforcing the
                        # collection setting, not allowing users to change it?)
                        if media_type not in collection["media_types"]:
                            collection["media_types"].append(media_type)

                    status_details = generate_status_details(
                        new_obj["id"],
                        datetime_to_string(new_obj["__meta"].version),
                        message
                    )
                    successes.append(status_details)

                except Exception as e:
                    # Who knows how messed up this object is... maybe don't
                    # assume it has any property we need.
                    version = getattr(new_obj.get("__meta"), "version", None)
                    if version:
                        version = datetime_to_string(version)

                    failures.append(
                        generate_status_details(
                            new_obj.get("id", "<unknown id>"),
                            version
                            or new_obj.get("modified")
                            or new_obj.get("created")
                            or "<unknown version>",
                            str(e)
                        )
                    )

            status = generate_status(
                datetime_to_string(request_time), "complete",
                successes=successes, failures=failures
            )

            status_map = api_root.get("status")
            if status_map is None:
                status_map = {}
                api_root["status"] = status_map

            status_map[status["id"]] = status

        return status

    def _object_id_exists(self, api_root, collection_id, object_id):
        """
        Inefficiently check for existence of an object with a given ID.
        """

        id_exists = False

        collection_objects = self.__api_roots.get(api_root) \
            .get("collections", {}) \
            .get(collection_id, {}) \
            .get("objects")

        if collection_objects:
            id_exists = any(
                obj["id"] == object_id for obj in collection_objects
            )

        return id_exists

    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):

        # Need to do this silly special case check because the get object
        # endpoint is defined behaviorally differently than get objects, so
        # this can't be implemented simply in terms of that.  If no object with
        # the given ID exists, we must produce a 404; get objects produces 200
        # and an empty envelope.  If an object with the given ID exists but the
        # filters filtered all objects out, we must produce a 200 and empty
        # envelope (this is compatible with get objects).  So if no object
        # matches all of the criteria, we need to know why so we can
        # distinguish these two cases.  Sadly, we have no efficient way to
        # do an ID existence check at the moment... :\

        if not self._object_id_exists(api_root, collection_id, object_id):
            raise ProcessingError(
                "Object '{}' not found".format(object_id), 404
            )

        # From here on out, we can delegate to get_objects.
        filter_args["match[id]"] = object_id
        allowed_filters += ("id",)

        envelope_resource, headers = self.get_objects(
            api_root, collection_id, filter_args, allowed_filters, limit
        )

        return envelope_resource, headers

    def delete_object(self, api_root_name, collection_id, obj_id, filter_args, allowed_filters):

        api_root = self.__api_roots.get(api_root_name)

        collection = None
        if api_root:
            collection = api_root.get("collections", {}).get(collection_id)
        else:
            raise ProcessingError(
                "API root '{}' not found".format(api_root_name), 404
            )

        if collection:
            objs = []
            coll = collection.get("objects", [])
            for obj in coll:
                if obj_id == obj["id"]:
                    objs.append(obj)

            if not objs:
                raise ProcessingError(
                    "Object '{}' not found".format(obj_id), 404
                )

            full_filter = BasicFilter(filter_args)
            objs, _, _ = full_filter.process_filter(
                objs,
                allowed_filters
            )

            for obj in objs:
                coll.remove(obj)
        else:
            raise ProcessingError(
                "Collection '{}' not found".format(collection_id), 404
            )

    def get_object_versions(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):

        # Need a special case for object ID not found.  _get_objects() will
        # return no results, but we won't know why, so we need this
        # disambiguating check.
        if not self._object_id_exists(api_root, collection_id, object_id):
            raise ProcessingError(
                "Object '{}' not found".format(object_id), 404
            )

        filter_args["match[id]"] = object_id
        allowed_filters += ("id",)

        # If I just delegate to get_object(), I'll get a resource ready for a
        # response, without the __meta bits which I would like to use to get
        # the versions.  So I'll use _get_objects() directly instead.
        result = self._get_objects(
            api_root, collection_id, filter_args, allowed_filters, limit
        )

        versions_resource = headers = None
        if result:

            page_objects, more, paging_key, headers = result

            # Transform the page of objects into a versions resource, by
            # extracting all of the version information.
            versions = [
                datetime_to_string(obj["__meta"].version)
                for obj in page_objects
            ]

            versions_resource = create_resource(
                "versions", versions, more, paging_key
            )

        return versions_resource, headers
