from medallion.utils import common

from .basic_filter import BasicFilter


class MongoDBFilter(BasicFilter):

    def __init__(self, filter_args, basic_filter, allowed):
        super(MongoDBFilter, self).__init__(filter_args)
        self.basic_filter = basic_filter
        self.full_query = self._query_parameters(allowed)

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
        # if not self.filter_args:
        #     return list(data.find(self.full_query))
        results = []
        date_filter = []
        version_filter = []
        match_filter = {'$match': self.full_query}
        pipeline = [match_filter]
        # create added_after filter
        added_after_date = self.filter_args.get("added_after")
        if added_after_date:
            added_after_timestamp = common.convert_to_stix_datetime(added_after_date)
            date_filter = {'$match': {'date_added': {'$gt': added_after_timestamp}}}
            pipeline.append(date_filter)

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
                    '$project':
                    {
                        'id': 1,
                        'date_added': 1,
                        'versions': version_selector,
                        'media_types': 1
                    }
                }
                pipeline.append(version_filter)

        if data._Collection__name == "manifests":
            cursor = data.aggregate(pipeline)
            results = list(cursor)
        else:
            # Join the filtered manifest(s) to the objects collection
            join_objects = {
                '$lookup':
                {
                    'from': "objects",
                    'localField': "id",
                    'foreignField': "id",
                    'as': "obj"
                }
            }
            pipeline.append(join_objects)
            # Copy the filtered version list to the embedded object document
            project_objects = {
                '$project': {
                    'obj.versions': '$versions',
                    'obj.id': 1,
                    'obj.modified': 1,
                    'obj.created': 1,
                    'obj.labels': 1,
                    'obj.name': 1,
                    'obj.pattern': 1,
                    'obj.type': 1,
                    'obj.valid_from': 1,
                    'obj.created_by_ref': 1,
                    'obj.object_marking_refs': 1
                }
            }
            pipeline.append(project_objects)
            # denormalise the embedded objects and replace the document root
            pipeline.append({'$unwind': '$obj'})
            pipeline.append({'$replaceRoot': {'newRoot': "$obj"}})
            # Redact the result set removing objects where the modified date is not in
            # the versions array
            redact_objects = {
                '$redact': {
                    '$cond': {
                        'if': {
                            '$setIsSubset': [
                                ["$modified"], "$versions"
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
            cursor = manifest_info["mongodb_collection"].aggregate(pipeline)
            results = list(cursor)

        return results
