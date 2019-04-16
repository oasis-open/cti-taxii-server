from medallion.utils import common

from .basic_filter import BasicFilter


class MongoDBFilter(BasicFilter):

    def __init__(self, filter_args, basic_filter, allowed, start_index=None, end_index=None):
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
                    parameters["_type"] = types_[0]
                else:
                    parameters["_type"] = {"$in": types_}
            match_id = self.filter_args.get("match[id]")
            if match_id and "id" in allowed:
                ids_ = match_id.split(",")
                if len(ids_) == 1:
                    parameters["id"] = ids_[0]
                else:
                    parameters["id"] = {"$in": ids_}
        return parameters

    def process_filter(self, data, allowed, manifest_info):
        match_filter = {'$match': self.full_query}
        pipeline = [match_filter]

        # create added_after filter
        added_after_date = self.filter_args.get("added_after")
        if added_after_date:
            added_after_timestamp = common.convert_to_stix_datetime(added_after_date)
            date_filter = {'$match': {'date_added': {'$gt': added_after_timestamp}}}
            pipeline.append(date_filter)

        # need to handle marking-definitions differently as they are not versioned like SDO's
        if self.filter_contains_marking_definition(pipeline):
            # If we are finding marking-definitions from the objects collection we need to change the match criteria from "_type" to "type"
            if data.name == "objects" and "_type" in pipeline[0]["$match"].keys():
                pipeline[0]["$match"]["type"] = pipeline[0]["$match"].pop("_type")

            # Calculate total number of matching documents
            if data.name == "objects":
                count = self.get_result_count(pipeline, manifest_info["mongodb_collection"])
            else:
                count = self.get_result_count(pipeline, data)

            self.add_pagination_operations(pipeline)

            cursor = data.aggregate(pipeline)
            results = list(cursor)

            return count, results

        # create version filter
        if "version" in allowed:
            match_version = self.filter_args.get("match[version]")
            if not match_version:
                match_version = "last"
            if "all" not in match_version:
                actual_dates = [x for x in match_version.split(",") if (x != "first" and x != "last")]
                # If specific dates have been selected, then we add these to the $match criteria
                # created from the self.full_query at the beginning of this method. The reason we need
                # to do this is because the $indexOfArray function below will return -1 if the date
                # doesn't exist in the versions array. -1 will be interrpreted by $arrayElemAt as the
                # final element in the array and we will return the wrong result. i.e. not only will the
                # version dates be incorrect, but we shouldn't have returned a result at all.
                # if actual_dates:
                if len(actual_dates) > 0:
                    pipeline.insert(1, {'$match': {'versions': {'$all': [",".join(actual_dates)]}}})

                # The versions array in the mongodb document is ordered newest to oldest, so the 'last'
                # (most recent date) is in first position in the list and the oldest 'first' is in
                # the last position (equal to index -1 for $arrayElemAt)
                version_selector = []
                if "last" in match_version:
                    version_selector.append({'$arrayElemAt': ["$versions", 0]})
                if "first" in match_version:
                    version_selector.append({'$arrayElemAt': ["$versions", -1]})
                for d in actual_dates:
                    version_selector.append({'$arrayElemAt': ["$versions", {'$indexOfArray': ["$versions", d]}]})
                version_filter = {
                    '$project': {
                        'id': 1,
                        'date_added': 1,
                        'versions': version_selector,
                        'media_types': 1
                    }
                }
                pipeline.append(version_filter)

        if data._Collection__name == "manifests":
            count = self.get_result_count(pipeline, data)
            self.add_pagination_operations(pipeline)

            cursor = data.aggregate(pipeline)
            results = list(cursor)
        else:
            # Get the count of matching documents - need to unwind the versions selected to get accurate count.
            count_pipeline = list(pipeline)
            count_pipeline.append({'$unwind': '$versions'})
            count = self.get_result_count(count_pipeline, manifest_info["mongodb_collection"])

            # Join the filtered manifest(s) to the objects collection
            join_objects = {
                '$lookup': {
                    'from': "objects",
                    'localField': "id",
                    'foreignField': "id",
                    'as': "obj"
                }
            }
            pipeline.append(join_objects)
            # Copy the filtered version list to the embedded object document
            add_versions = {
                '$addFields': {'obj.versions': '$versions'}
            }
            pipeline.append(add_versions)
            # denormalise the embedded objects and replace the document root
            pipeline.append({'$unwind': '$obj'})
            pipeline.append({'$replaceRoot': {'newRoot': "$obj"}})
            # Redact the result set removing objects where the modified date is not in
            # the versions array and the object isn't in the correct collection.
            # The collection filter is required because the join between manifests and objects
            # does not include collection_id
            col_id = self.full_query['_collection_id']
            redact_objects = {
                '$redact': {
                    '$cond': {
                        'if': {
                            '$and': [
                                {'$eq': ["$_collection_id", col_id]},
                                {'$or': [
                                    {'$eq': ["$type", "marking-definition"]},
                                    {'$setIsSubset': [["$modified"], "$versions"]}
                                ]}
                            ]
                        },
                        'then': "$$KEEP",
                        'else': "$$PRUNE"
                    }
                }
            }
            pipeline.append(redact_objects)
            # Project the final results
            project_results = {
                '$project': {
                    'versions': 0
                }
            }
            pipeline.append(project_results)
            self.add_pagination_operations(pipeline)

            cursor = manifest_info["mongodb_collection"].aggregate(pipeline)
            results = list(cursor)

        return count, results

    def add_pagination_operations(self, pipeline):
        if self.start_index is not None and self.end_index is not None:
            pipeline.append({"$skip": self.start_index})
            pipeline.append({"$limit": self.end_index - self.start_index})

    def get_result_count(self, pipeline, data):
        count_pipeline = list(pipeline)
        count_pipeline.append({"$count": "total_count"})
        count_result = list(data.aggregate(count_pipeline))

        if len(count_result) == 0:
            # No results
            return 0

        count = count_result[0]['total_count']

        return count

    def filter_contains_marking_definition(self, pipeline):
        # If we are matching on id (either match[id]= or /{id}), then check if
        # we are trying to find a marking definition. If so, we don't want do
        # filter by version as marking-definition objects are not versioned.
        if "id" in pipeline[0]["$match"].keys() and pipeline[0]["$match"]["id"].startswith("marking-definition"):
            return True

        if "_type" in pipeline[0]["$match"].keys():
            if ((isinstance(pipeline[0]["$match"]["_type"], dict) and
                    "$in" in pipeline[0]["$match"]["_type"].keys()) and
                    ("marking-definition" in pipeline[0]["$match"]["_type"]["$in"])):
                return True
            elif pipeline[0]["$match"]["_type"].startswith("marking-definition"):
                return True

        return False
