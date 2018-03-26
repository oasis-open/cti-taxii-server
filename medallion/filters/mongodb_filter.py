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
                    parameters["type"] = types_[0]
                else:
                    parameters["type"] = {"$in": types_}
            match_id = self.filter_args.get("match[id]")
            if match_id and "id" in allowed:
                ids_ = match_id.split(",")
                if len(ids_) == 1:
                    parameters["id"] = ids_[0]
                else:
                    parameters["id"] = {"$in": ids_}
        return parameters

    def process_filter(self, data, allowed, manifest_info):
        results = list(data.find(self.full_query))
        if results and self.filter_args:
            if "version" in allowed:
                match_version = self.filter_args.get("match[version]")
                if not match_version:
                    match_version = "last"
                if self.is_manifest_entry(results[0]):
                    results = self.filter_manifest_entries_by_version(results, match_version)
                else:
                    new_results = []
                    for bucket in BasicFilter._equivalence_partition_by_id(results):
                        new_results.extend(self.filter_by_version(bucket, match_version))
                    results = new_results
            added_after_date = self.filter_args.get("added_after")
            if added_after_date:
                added_after_timestamp = common.convert_to_stix_datetime(added_after_date)
                new_results = []
                for obj in results:
                    info = manifest_info["mongodb_collection"].find_one(
                        {"id": obj["id"], "_collection_id": manifest_info["_collection_id"]}
                    )
                    if info:
                        added_date_timestamp = common.convert_to_stix_datetime(info["date_added"])
                        if added_date_timestamp > added_after_timestamp:
                            new_results.append(obj)
                return new_results
            else:
                return results
        return results
