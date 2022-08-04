import io
import json
import logging
import uuid

import environ
from pymongo import ASCENDING, IndexModel, MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from six import string_types

# from ..config import get_application_instance_config_values
from ..common import (
    APPLICATION_INSTANCE, create_resource, datetime_to_float,
    datetime_to_string, datetime_to_string_stix, determine_spec_version,
    determine_version, float_to_datetime, generate_status,
    generate_status_details, get_application_instance_config_values,
    get_custom_headers, get_timestamp, parse_request_parameters,
    string_to_datetime
)
from ..exceptions import (
    InitializationError, MongoBackendError, ProcessingError
)
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

    @environ.config(prefix="MONGO")
    class Config(object):
        uri = environ.var()

    def __init__(self, **kwargs):
        try:

            self.pages = {}
            self.client = MongoClient(kwargs.get("uri"))

            # unless clearing the db has been explicitly specified, don't initialize if the discovery_database exits
            # the discovery_databases is a minimally viable database,
            if not self.database_established() or kwargs.get("clear_db"):
                self.clear_db()
                if kwargs.get("filename"):
                    log.info("Initializing Mongo DB backend using " + kwargs.get("filename"))
                    self.initialize_mongodb_with_data(kwargs.get("filename"))
                    self.object_manifest_check()

            super(MongoBackend, self).__init__(**kwargs)

        except ConnectionFailure:
            log.error("Unable to establish a connection to MongoDB server {}".format(kwargs.get("uri")))

    def database_established(self):
        """
        Checks to see if a medallion database exists
        """
        return "discovery_database" in self.client.list_database_names()

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

    def _pop_old_statuses(self):
        if "discovery_database" in self.client.list_database_names():
            api_roots = self._get_all_api_roots()
            if api_roots:
                status_retention_in_milliseconds = self.status_retention * 1000
                for ar in api_roots:
                    statuses_of_api_root = self._get_api_root_statuses(ar)
                    result = statuses_of_api_root.aggregate([
                            {
                                "$project": {
                                    "id": 1,
                                    "date_difference": {
                                        "$subtract": [
                                            "$$NOW",
                                            {
                                                "$dateFromString": {
                                                    "dateString": "$request_timestamp"
                                                }
                                            }
                                        ]
                                    },
                                }
                            },
                            {
                                "$match": {
                                    "date_difference": {
                                        "$gt": status_retention_in_milliseconds
                                    }
                                }
                            }
                        ]
                    )
                    for doc in result:
                        log.info("Status {} was deleted from {} because it was older than the status retention time".format(doc["id"], ar))
                        statuses_of_api_root.delete_one({"_id": doc["_id"]})

    def _get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters, limit, internal=False):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        next_id, record = self._process_params(filter_args, limit)

        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}},
            allowed_filters,
            record
        )
        count, objects_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            "manifests",
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

    def object_manifest_check(self):
        """
        Checks for manifests in each object, throws an error if not present.
        """
        db = self.client
        objects_exists = False
        for api_root in db.list_database_names():
            cols = db[api_root].list_collection_names()
            if "objects" not in cols:
                continue
            objects_exists = True
            api_root_db = db[api_root]
            objects = api_root_db["objects"]
            for result in objects.find({}):
                if "_manifest" not in result:
                    field_to_use = 'created'
                    if "modified" in result:
                        field_to_use = 'modified'
                    raise InitializationError("Object {} from {} is missing a manifest".format(result['id'], result[field_to_use]), 408)
                if not result['_manifest']:
                    field_to_use = 'created'
                    if "modified" in result:
                        field_to_use = 'modified'
                    raise InitializationError("Object {} from {} has a null manifest".format(result['id'], result[field_to_use]), 408)
        if not objects_exists:
            raise InitializationError("Could not find any objects in database", 408)

    @catch_mongodb_error
    def _update_manifest(self, api_root, collection_id, media_type):
        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]

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
        info = discovery_info.find_one()
        if info:
            info.pop("_id")
        return info

    @catch_mongodb_error
    def get_collections(self, api_root):
        if api_root not in self.client.list_database_names():
            return None  # must return None, so 404 is raised

        api_root_db = self.client[api_root]
        collection_info = api_root_db["collections"]
        collections = list(collection_info.find({}, {"_id": 0}))
        # interop wants results sorted by id - no need to check for interop option
        if get_application_instance_config_values(APPLICATION_INSTANCE, "taxii", "interop_requirements"):
            collections = sorted(collections, key=lambda o: o["id"])
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
    def _get_api_root_statuses(self, api_root):
        api_root_db = self.client[api_root]
        return api_root_db["status"]

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
            "objects"
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
    def _add_status(self, api_root_name, status):
        api_root_db = self.client[api_root_name]
        api_root_db["status"].insert_one(status)

    @catch_mongodb_error
    def add_objects(self, api_root, collection_id, objs, request_time):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        successes = []
        media_fmt = "application/stix+json;version={}"

        try:
            for new_obj in objs["objects"]:
                media_type = media_fmt.format(determine_spec_version(new_obj))
                mongo_query = {"_collection_id": collection_id, "id": new_obj["id"], "_manifest.media_type": media_type}
                if "modified" in new_obj:
                    mongo_query["_manifest.version"] = datetime_to_float(string_to_datetime(new_obj["modified"]))
                existing_entry = objects_info.find_one(mongo_query)
                obj_version = determine_version(new_obj, request_time)

                if existing_entry:
                    message = "Object already added"

                else:
                    message = None
                    new_obj.update({"_collection_id": collection_id})
                    if "modified" in new_obj:
                        new_obj["modified"] = datetime_to_float(string_to_datetime(new_obj["modified"]))
                    if "created" in new_obj:
                        new_obj["created"] = datetime_to_float(string_to_datetime(new_obj["created"]))
                    _manifest = {
                        "id": new_obj["id"],
                        "date_added": datetime_to_float(request_time),
                        "version": datetime_to_float(obj_version),
                        "media_type": media_type,
                    }
                    new_obj.update({"_manifest": _manifest})
                    objects_info.insert_one(new_obj)
                    self._update_manifest(api_root, collection_id, media_type)

                # else: we already have the object, so this is a
                # no-op.

                status_detail = generate_status_details(
                    new_obj["id"], datetime_to_string(obj_version), message
                )
                successes.append(status_detail)
        except Exception as e:
            # log.exception(e)
            raise ProcessingError("While processing supplied content, an error occurred", 422, e)

        status = generate_status(
            datetime_to_string(request_time), "complete", successes=successes
        )
        api_root_db["status"].insert_one(status)
        status.pop("_id", None)
        return status

    @catch_mongodb_error
    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        # set manually to properly retrieve manifests, and early to not break the pagination checks
        filter_args["match[id]"] = object_id
        next_id, record = self._process_params(filter_args, limit)

        self._validate_object_id(objects_info, collection_id, object_id)

        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}, "id": {"$eq": object_id}},
            allowed_filters,
            record
        )
        count, objects_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            "objects"
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

        self._validate_object_id(objects_info, collection_id, object_id)

        # Currently it will delete the object and the matching manifest from the backend
        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}, "id": {"$eq": object_id}},
            allowed_filters,
        )
        count, objects_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            "raw"
        )
        if objects_found:
            for obj in objects_found:
                obj_version = obj["_manifest"]["version"]
                objects_info.delete_one(
                    {"_collection_id": collection_id, "id": object_id, "_manifest.version": obj_version}
                )
        else:
            raise ProcessingError("Object '{}' not found".format(object_id), 404)

    @catch_mongodb_error
    def get_object_versions(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):
        api_root_db = self.client[api_root]
        objects_info = api_root_db["objects"]
        # set manually to properly retrieve manifests, and early to not break the pagination checks
        filter_args["match[id]"] = object_id
        filter_args["match[version]"] = "all"
        next_id, record = self._process_params(filter_args, limit)

        self._validate_object_id(objects_info, collection_id, object_id)

        full_filter = MongoDBFilter(
            filter_args,
            {"_collection_id": {"$eq": collection_id}, "id": {"$eq": object_id}},
            allowed_filters,
            record
        )
        count, manifests_found = full_filter.process_filter(
            objects_info,
            allowed_filters,
            "manifests",
        )

        manifest_resource = self._get_object_manifest(api_root, collection_id, filter_args, ("id", "type", "version", "spec_version"), limit, True)
        headers = get_custom_headers(manifest_resource)

        manifests_found = list(map(lambda x: datetime_to_string_stix(float_to_datetime(x["version"])), manifests_found))
        next_id, more = self._update_record(next_id, count)
        return create_resource("versions", manifests_found, more, next_id), headers

    def load_data_from_file(self, filename):
        try:
            if isinstance(filename, string_types):
                with io.open(filename, "r", encoding="utf-8") as infile:
                    self.json_data = json.load(infile)
            else:
                self.json_data = json.load(filename)
        except Exception as e:
            raise InitializationError("Problem loading initialization data from {0}".format(filename), 408, e)

    def initialize_mongodb_with_data(self, filename):
        self.load_data_from_file(filename)
        if "/discovery" in self.json_data:
            db = self.client["discovery_database"]
            db["discovery_information"].insert_one(self.json_data["/discovery"])
        else:
            raise InitializationError("No discovery information provided when initializing the Mongo DB")
        api_root_info_db = db["api_root_info"]
        for api_root_name, api_root_data in self.json_data.items():
            if api_root_name == "/discovery":
                continue
            url = list(filter(lambda a: api_root_name in a, self.json_data["/discovery"]["api_roots"]))[0]
            api_root_data["information"]["_url"] = url
            api_root_data["information"]["_name"] = api_root_name
            api_root_info_db.insert_one(api_root_data["information"])
            self.client.drop_database(api_root_name)
            api_db = self.client[api_root_name]
            if api_root_data["status"]:
                api_db["status"].insert_many(api_root_data["status"].values())
            else:
                api_db.create_collection("status")
            api_db.create_collection("collections")
            api_db.create_collection("objects")
            for collection_id, collection in api_root_data["collections"].items():
                # these are not in the collections mongodb collection (both TAXII and Mongo DB use the term collection)
                objects = collection.pop("objects")
                api_db["collections"].insert_one(collection)
                for obj in objects:
                    obj_meta = obj.pop("__meta")
                    obj["_collection_id"] = collection_id
                    date_added = string_to_datetime(obj_meta["date_added"])
                    version = string_to_datetime(
                        obj.get("modified")
                        or obj.get("created")
                        or obj_meta["date_added"]
                    )
                    obj["_manifest"] = {
                        "date_added": datetime_to_float(date_added),
                        "id": obj["id"],
                        "media_type": obj_meta["media_type"],
                        "version": datetime_to_float(version)
                    }
                    obj["created"] = datetime_to_float(string_to_datetime(obj["created"]))
                    if "modified" in obj:
                        # not for data markings
                        obj["modified"] = datetime_to_float(string_to_datetime(obj["modified"]))
                    api_db["objects"].insert_one(obj)
                id_index = IndexModel([("id", ASCENDING)])
                type_index = IndexModel([("type", ASCENDING)])
                collection_index = IndexModel([("_collection_id", ASCENDING)])
                date_index = IndexModel([("_manifest.date_added", ASCENDING)])
                version_index = IndexModel([("_manifest.version", ASCENDING)])
                date_and_spec_index = IndexModel([("_manifest.media_type", ASCENDING), ("_manifest.date_added", ASCENDING)])
                version_and_spec_index = IndexModel([("_manifest.media_type", ASCENDING), ("_manifest.version", ASCENDING)])
                collection_and_date_index = IndexModel([("_collection_id", ASCENDING), ("_manifest.date_added", ASCENDING)])
                api_db["objects"].create_indexes(
                    [id_index, type_index, date_index, version_index, collection_index, date_and_spec_index,
                     version_and_spec_index, collection_and_date_index]
                )

    def clear_db(self):
        if "discovery_database" in self.client.list_database_names():
            log.info("Clearing database")
            self.client.drop_database("discovery_database")
        discovery_db = self.client["discovery_database"]
        api_root_info = discovery_db["api_root_info"]
        for api_info in api_root_info.find({}):
            self.client.drop_database(api_info["_name"])
        self.client.drop_database("discovery_database")
        # db with empty tables
        log.info("Creating empty database")
        discovery_db = self.client.get_database("discovery_database")
        discovery_db.create_collection("discovery_information")
        discovery_db.create_collection("api_root_info")
        return discovery_db
