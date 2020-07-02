from bson.son import SON
from pymongo import ASCENDING

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
                    parameters["type"] = {"$eq": types_[0]}
                else:
                    parameters["type"] = {"$in": types_}
            match_id = self.filter_args.get("match[id]")
            if match_id and "id" in allowed:
                ids_ = match_id.split(",")
                if len(ids_) == 1:
                    parameters["id"] = {"$eq": ids_[0]}
                else:
                    parameters["id"] = {"$in": ids_}
            match_spec_version = self.filter_args.get("match[spec_version]")
            if match_spec_version and "spec_version" in allowed:
                spec_versions = match_spec_version.split(",")
                media_fmt = "application/stix+json;version={}"
                if len(spec_versions) == 1:
                    parameters["_manifest.media_type"] = {
                        "$eq": media_fmt.format(spec_versions[0])
                    }
                else:
                    parameters["_manifest.media_type"] = {
                        "$in": [media_fmt.format(x) for x in spec_versions]
                    }
            added_after_date = self.filter_args.get("added_after")
            if added_after_date:
                added_after_timestamp = datetime_to_float(string_to_datetime(added_after_date))
                parameters["_manifest.date_added"] = {
                    "$gt": added_after_timestamp,
                }
        return parameters

    def process_filter(self, data, allowed, manifest_info):
        pipeline = [
            {"$match": {"$and": [self.full_query]}},
        ]

        # when no filter is provided only latest is considered.
        match_spec_version = self.filter_args.get("match[spec_version]")
        if not match_spec_version and "spec_version" in allowed:
            latest_pipeline = list(pipeline)
            latest_pipeline.append({"$sort": {"_manifest.media_type": ASCENDING}})
            latest_pipeline.append({"$group": SON([("_id", "$id"), ("media_type", SON([("$last", "$_manifest.media_type")]))])})

            query = [
                {"id": x["_id"], "_manifest.media_type": x["media_type"]}
                for x in list(data.aggregate(latest_pipeline))
            ]
            if query:
                pipeline.append({"$match": {"$or": query}})

        # create version filter
        if "version" in allowed:
            match_version = self.filter_args.get("match[version]")
            if not match_version:
                match_version = "last"
            if "all" not in match_version:
                actual_dates = [datetime_to_float(string_to_datetime(x)) for x in match_version.split(",") if (x != "first" and x != "last")]

                latest_pipeline = list(pipeline)
                latest_pipeline.append({"$sort": {"_manifest.version": ASCENDING}})
                latest_pipeline.append({"$group": SON([("_id", "$id"), ("versions", SON([("$push", "$_manifest.version")]))])})

                # The documents are sorted in ASCENDING order.
                version_selector = []
                if "last" in match_version:
                    version_selector.append({"$arrayElemAt": ["$versions", -1]})
                if "first" in match_version:
                    version_selector.append({"$arrayElemAt": ["$versions", 0]})
                for d in actual_dates:
                    version_selector.append({"$arrayElemAt": ["$versions", {"$indexOfArray": ["$versions", d]}]})
                latest_pipeline.append({"$addFields": {"versions": version_selector}})
                if actual_dates:
                    latest_pipeline.append({"$match": {"versions": {"$in": actual_dates}}})

                query = [
                    {"id": x["_id"], "_manifest.version": {"$in": x["versions"]}}
                    for x in list(data.aggregate(latest_pipeline))
                ]
                if query:
                    pipeline.append({"$match": {"$or": query}})

        pipeline.append({"$sort": SON([("_manifest.date_added", ASCENDING), ("created", ASCENDING), ("modified", ASCENDING)])})

        if manifest_info == "manifests":
            # Project the final results
            pipeline.append({"$project": {"_manifest": 1}})
            pipeline.append({"$replaceRoot": {"newRoot": "$_manifest"}})

            count = self.get_result_count(pipeline, data)
            self.add_pagination_operations(pipeline)
            results = list(data.aggregate(pipeline))
        elif manifest_info == "objects":
            # Project the final results
            pipeline.append({"$project": {"_id": 0, "_collection_id": 0, "_manifest": 0}})

            count = self.get_result_count(pipeline, data)
            self.add_pagination_operations(pipeline)
            results = list(data.aggregate(pipeline))
        else:
            # Return raw data from Mongodb
            count = self.get_result_count(pipeline, data)
            self.add_pagination_operations(pipeline)
            results = list(data.aggregate(pipeline))

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
