import pymongo

from ..common import datetime_to_float, string_to_datetime
from .basic_filter import BasicFilter


class MongoDBFilter(BasicFilter):

    def __init__(self, filter_args, basic_filter, allowed, record=None):
        super(MongoDBFilter, self).__init__(filter_args)
        self.basic_filter = basic_filter
        self.full_query = self._query_parameters(allowed)
        self.record = record

    def _query_parameters(self, allowed):
        parameters = self.basic_filter
        if self.filter_args:
            match_type = self.filter_args.get("match[type]")
            if match_type and "type" in allowed:
                types_ = match_type.split(",")
                if len(types_) == 1:
                    parameters["_type"] = {"$eq": types_[0]}
                else:
                    parameters["_type"] = {"$in": types_}
            match_id = self.filter_args.get("match[id]")
            if match_id and "id" in allowed:
                ids_ = match_id.split(",")
                if len(ids_) == 1:
                    parameters["id"] = {"$eq": ids_[0]}
                else:
                    parameters["id"] = {"$in": ids_}
        return parameters

    def process_filter(self, data, allowed, manifest_info):
        match_filter = {
            "$match": {
                "$and": [self.full_query],
                "$comment": "Step #1: Match against an object/manifest id or type present in a collection.",
            },
        }
        pipeline = [match_filter]

        # create added_after filter
        added_after_date = self.filter_args.get("added_after")
        if added_after_date:
            added_after_timestamp = datetime_to_float(string_to_datetime(added_after_date))
            date_filter = {
                "$match": {
                    "date_added": {"$gt": added_after_timestamp},
                    "$comment": "Step #2: If added_after is provided, remove all objects/manifests older than the provided time",
                }
            }
            pipeline.append(date_filter)

        # create spec_version filter. when no filter is provided only latest is considered.
        if "spec_version" in allowed:
            match_spec_version = self.filter_args.get("match[spec_version]")
            if match_spec_version:
                spec_versions = match_spec_version.split(",")
                media_fmt = "application/stix+json;version={}"
                if len(spec_versions) == 1:
                    pipeline[0]["$match"]["$and"].append({"media_type": {"$eq": media_fmt.format(spec_versions[0])}})
                else:
                    pipeline[0]["$match"]["$and"].append({"media_type": {"$in": [media_fmt.format(x) for x in spec_versions]}})
            else:
                pipeline.append({"$group": {"_id": "$id", "media_types": {"$push": "$$ROOT"}}})
                pipeline.append({"$sort": {"media_types.media_type": pymongo.ASCENDING}})
                pipeline.append({"$addFields": {"media_types": {"$arrayElemAt": ["$media_types", -1]}}})
                pipeline.append({"$replaceRoot": {"newRoot": "$media_types"}})

        # create version filter
        if "version" in allowed:
            match_version = self.filter_args.get("match[version]")
            if not match_version:
                match_version = "last"
            if "all" not in match_version:
                actual_dates = [datetime_to_float(string_to_datetime(x)) for x in match_version.split(",") if (x != "first" and x != "last")]
                # If specific dates have been selected, then we add these to the $match criteria
                # created from the self.full_query at the beginning of this method. This will make
                # sure we can pick the correct manifests even if `added_after` later modifies this results.
                if len(actual_dates) > 0:
                    pipeline[0]["$match"]["$and"].append({"version": {"$in": actual_dates}})

                pipeline.append({"$group": {"_id": "$id", "versions": {"$push": "$$ROOT"}}})
                pipeline.append({"$sort": {"versions.version": pymongo.ASCENDING}})

                # The versions array in the mongodb document is ordered oldest to newest, so the 'last'
                # (most recent date) is in last position in the list and the oldest 'first' is in
                # the first position.
                version_selector = []
                if "last" in match_version:
                    version_selector.append({"$arrayElemAt": ["$versions", -1]})
                if "first" in match_version:
                    version_selector.append({"$arrayElemAt": ["$versions", 0]})
                for d in actual_dates:
                    version_selector.append({"$arrayElemAt": ["$versions", {"$indexOfArray": ["$versions", d]}]})
                pipeline.append({"$addFields": {"versions": version_selector}})

                # denormalize the embedded objects, remove duplicates and replace the document root. Could be improved
                pipeline.append({"$unwind": "$versions"})
                pipeline.append({"$replaceRoot": {"newRoot": "$versions"}})
                pipeline.append({"$group": {"_id": "$$ROOT"}})
                pipeline.append({"$replaceRoot": {"newRoot": "$_id"}})
        pipeline.append({"$sort": {"date_added": pymongo.ASCENDING}})

        if data.name == "manifests":
            # Project the final results
            project_results = {"$project": {"_id": 0, "_collection_id": 0, "_type": 0}}
            pipeline.append(project_results)

            count = self.get_result_count(pipeline, data)
            self.add_pagination_operations(pipeline)
            cursor = data.aggregate(pipeline)
            results = list(cursor)
        else:
            # Join the filtered manifest(s) to the objects collection
            join_objects = {
                "$lookup": {
                    "from": "objects",
                    "localField": "id",
                    "foreignField": "id",
                    "as": "obj",
                },
            }
            pipeline.append(join_objects)

            # Copy the filtered version list to the embedded object document
            add_versions = {
                "$addFields": {"obj.version": "$version"},
            }
            pipeline.append(add_versions)

            # Copy the media_type we a looking for into the embedded object document
            add_media_type = {
                "$addFields": {"obj.media_type": "$media_type"},
            }
            pipeline.append(add_media_type)

            # denormalize the embedded objects and replace the document root
            pipeline.append({"$unwind": "$obj"})
            pipeline.append({"$replaceRoot": {"newRoot": "$obj"}})

            # Redact the result set removing objects where the modified date is not in
            # the version field and the object isn't in the correct collection.
            # The collection filter is required because the join between manifests and objects
            # does not include collection_id.
            #
            col_id = self.full_query["_collection_id"]["$eq"]
            redact_objects = {
                "$redact": {
                    "$cond": {
                        "if": {
                            "$and": [
                                {"$eq": ["$_collection_id", col_id]},
                                {
                                    "$switch": {
                                        "branches": [
                                            {"case": {"$eq": ["$modified", "$version"]}, "then": True},
                                            {"case": {"$and": [
                                                {"$eq": ["$created", "$version"]}, {"$not": ["$modified"]}
                                            ]}, "then": True},
                                            {"case": {"$eq": ["$_date_added", "$version"]}, "then": True},
                                        ],
                                        "default": False,
                                    },
                                },
                                {
                                    "$switch": {
                                        "branches": [
                                            {"case": {"$eq": ["$spec_version", {"$substrBytes": ["$media_type", 30, 4]}]}, "then": True},
                                            {"case": {"$and": [
                                                {"$eq": ["2.0", {"$substrBytes": ["$media_type", 30, 4]}]}, {"$not": ["$spec_version"]}
                                            ]}, "then": True},
                                        ],
                                        "default": False,
                                    },
                                }
                            ],
                        },
                        "then": "$$KEEP",
                        "else": "$$PRUNE",
                    },
                },
            }
            pipeline.append(redact_objects)

            # denormalize the embedded objects, remove duplicates and replace the document root. Could be improved
            pipeline.append({"$group": {"_id": "$$ROOT"}})
            pipeline.append({"$replaceRoot": {"newRoot": "$_id"}})
            pipeline.append({"$sort": {"_date_added": pymongo.ASCENDING, "created": pymongo.ASCENDING, "modified": pymongo.ASCENDING}})

            # Project the final results
            project_results = {"$project": {"version": 0, "media_type": 0, "_id": 0, "_collection_id": 0, "_date_added": 0}}
            pipeline.append(project_results)

            count = self.get_result_count(pipeline, manifest_info["mongodb_manifests_collection"])
            self.add_pagination_operations(pipeline)

            cursor = manifest_info["mongodb_manifests_collection"].aggregate(pipeline)
            results = list(cursor)

        return count, results

    def add_pagination_operations(self, pipeline):
        if self.record:
            pipeline.append({"$skip": self.record["skip"]})
            pipeline.append({"$limit": self.record["limit"]})

    def get_result_count(self, pipeline, data):
        count_pipeline = list(pipeline)
        count_pipeline.append({"$count": "total"})
        count_result = list(data.aggregate(count_pipeline))

        if len(count_result) == 0:
            # No results
            return 0

        count = count_result[0]["total"]
        return count
