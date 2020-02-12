from ..utils.common import datetime_to_float, string_to_datetime
from .basic_filter import BasicFilter


class MongoDBFilter(BasicFilter):

    def __init__(self, filter_args, basic_filter, allowed, start_index=0, end_index=None):
        super(MongoDBFilter, self).__init__(filter_args)
        self.basic_filter = basic_filter
        self.full_query = self._query_parameters(allowed)
        self.start_index = start_index
        self.end_index = end_index

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

        # create version filter
        if "version" in allowed:
            match_version = self.filter_args.get("match[version]")
            if not match_version:
                match_version = "last"
            if "all" not in match_version:
                actual_dates = [datetime_to_float(string_to_datetime(x)) for x in match_version.split(",") if (x != "first" and x != "last")]
                # If specific dates have been selected, then we add these to the $match criteria
                # created from the self.full_query at the beginning of this method. The reason we need
                # to do this is because the $indexOfArray function below will return -1 if the date
                # doesn't exist in the versions array. -1 will be interpreted by $arrayElemAt as the
                # final element in the array and we will return the wrong result. i.e. not only will the
                # version dates be incorrect, but we shouldn't have returned a result at all.
                # if actual_dates:
                if len(actual_dates) > 0:
                    pipeline[0]["$match"]["$and"].append({"versions": {"$all": actual_dates}})

                # The versions array in the mongodb document is ordered newest to oldest, so the 'last'
                # (most recent date) is in first position in the list and the oldest 'first' is in
                # the last position (equal to index -1 for $arrayElemAt)
                version_selector = []
                if "last" in match_version:
                    version_selector.append({"$arrayElemAt": ["$versions", 0]})
                if "first" in match_version:
                    version_selector.append({"$arrayElemAt": ["$versions", -1]})
                for d in actual_dates:
                    version_selector.append({"$arrayElemAt": ["$versions", {"$indexOfArray": ["$versions", d]}]})
                version_filter = {
                    "$addFields": {
                        "versions": version_selector,
                    },
                }
                pipeline.append(version_filter)

        if data.name == "manifests":
            # Project the final results
            project_results = {"$project": {"_id": 0, "_collection_id": 0, "_type": 0}}
            pipeline.append(project_results)
            count = self.get_result_count(pipeline, data)
            self.add_pagination_operations(pipeline)

            cursor = data.aggregate(pipeline)
            results = list(cursor)
        else:
            results = []
            # Get the count of matching documents - need to unwind the versions selected to get accurate count.
            count_pipeline = list(pipeline)
            count_pipeline.append({"$unwind": "$versions"})
            count = self.get_result_count(count_pipeline, manifest_info["mongodb_collection"])

            # only bother doing the rest of the query if the start index is less than the total number of results.
            if self.start_index < count:
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
                    "$addFields": {"obj.versions": "$versions"},
                }
                pipeline.append(add_versions)
                # denormalize the embedded objects and replace the document root
                pipeline.append({"$unwind": "$obj"})
                pipeline.append({"$replaceRoot": {"newRoot": "$obj"}})
                # Redact the result set removing objects where the modified date is not in
                # the versions array and the object isn't in the correct collection.
                # The collection filter is required because the join between manifests and objects
                # does not include collection_id
                col_id = self.full_query["_collection_id"]
                redact_objects = {
                    "$redact": {
                        "$cond": {
                            "if": {
                                "$and": [
                                    {"$eq": ["$_collection_id", col_id]},
                                    {
                                        "$switch": {
                                            "branches": [
                                                {"case": {"$in": ["$modified", "$versions"]}, "then": True},
                                                {"case": {"$and": [{"$in": ["$created", "$versions"]}, {"$not": ["$modified"]}]}, "then": True},
                                                {"case": {"$in": ["$_date_added", "$versions"]}, "then": True},
                                            ],
                                            "default": False,
                                        },
                                    },
                                ],
                            },
                            "then": "$$KEEP",
                            "else": "$$PRUNE",
                        },
                    },
                }
                pipeline.append(redact_objects)
                # Project the final results
                project_results = {"$project": {"versions": 0, "_id": 0, "_collection_id": 0, "_date_added": 0}}
                pipeline.append(project_results)
                self.add_pagination_operations(pipeline)

                cursor = manifest_info["mongodb_collection"].aggregate(pipeline)
                results = list(cursor)

        return count, results

    def add_pagination_operations(self, pipeline):
        if self.start_index is not None and self.end_index is not None:
            pipeline.append({"$skip": self.start_index})
            pipeline.append({"$limit": (self.end_index - self.start_index) + 1})

    @staticmethod
    def get_result_count(pipeline, data):
        count_pipeline = list(pipeline)
        count_pipeline.append({"$count": "total_count"})
        count_result = list(data.aggregate(count_pipeline))

        if len(count_result) == 0:
            # No results
            return 0

        count = count_result[0]["total_count"]
        return count
