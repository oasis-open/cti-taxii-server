import datetime as dt

from medallion.utils import common


class BasicFilter(object):

    def __init__(self, filter_args):
        self.filter_args = filter_args

    @staticmethod
    def _belongs_in_class(c, obj):
        return c[0]["id"] == obj["id"]

    @staticmethod
    def _equivalence_partition_by_id(initial_results):
        classes = []
        for o in initial_results:  # for each object
            # find the class it is in
            found = False
            for c in classes:
                if BasicFilter._belongs_in_class(c, o):  # is it equivalent to this class?
                    c.append(o)
                    found = True
                    break
            if not found:  # it is in a new class
                classes.append([o])
        return classes

    @staticmethod
    def filter_by_id(data, id_):
        id_ = id_.split(",")

        match_objects = []

        for obj in data:
            if "id" in obj and any(s == obj["id"] for s in id_):
                match_objects.append(obj)

        return match_objects

    @staticmethod
    def filter_by_version(data, version):
        # There can be more than one filter, using v_filter for looping through
        # each filter. For example ?match[version]=first,last
        match_objects = []
        version_indicators = version.split(",")

        if "all" in version_indicators:
            # if "all" is in the list, just return everything
            return data

        actual_dates = [x for x in version_indicators if x != "first" and x != "last"]

        first = last = None
        t_first = t_last = None

        for obj in data:
            if obj["id"].startswith("marking-definition--"):
                prop = "created"
            else:
                prop = "modified"

            time_of_obj = dt.datetime.strptime(obj[prop], "%Y-%m-%dT%H:%M:%S.%fZ")

            if first is None:
                first = last = obj
                t_first = time_of_obj
                t_last = time_of_obj
            else:
                if time_of_obj < t_first:
                    first = obj
                    t_first = time_of_obj
                elif time_of_obj > t_last:
                    last = obj
                    t_last = time_of_obj

            if obj[prop] in actual_dates:
                match_objects.append(obj)

        if "first" in version_indicators:
            match_objects.append(first)

        if "last" in version_indicators:
            match_objects.append(last)

        return match_objects

    @staticmethod
    def is_manifest_entry(obj):
        # "id" is required, all other properties are optional.
        return any(prop in obj for prop in ("id", "date_added", "versions", "media_types"))

    @staticmethod
    def filter_manifest_entries_by_version(data, version):
        match_objects = []
        version_indicators = version.split(",")

        if "all" in version_indicators:
            # if "all" is in the list, just return everything
            return data

        actual_dates = [x for x in version_indicators if (x != "first" and x != "last")]
        for obj in data:
            versions_returned = []
            first = last = None
            t_first = t_last = None

            for t in obj["versions"]:
                timestamp = dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%fZ")
                if first is None:
                    first = last = t
                    t_first = timestamp
                    t_last = timestamp
                else:
                    if timestamp < t_first:
                        first = t
                        t_first = timestamp
                    elif timestamp > t_last:
                        last = t
                        t_last = timestamp

                if t in actual_dates:
                    versions_returned.append(t)

            if "first" in version_indicators:
                versions_returned.append(first)

            if "last" in version_indicators:
                versions_returned.append(last)

            if versions_returned:
                obj["versions"] = versions_returned
                match_objects.append(obj)

        return match_objects

    @staticmethod
    def filter_by_type(data, type_):
        type_ = type_.split(",")
        match_objects = []

        for obj in data:
            if "type" in obj and any(s == obj["type"] for s in type_):
                match_objects.append(obj)
            elif "id" in obj and any(s == obj["id"].split("--")[0] for s in type_):
                match_objects.append(obj)

        return match_objects

    def process_filter(self, data, allowed, manifest_info):
        filtered_by_type = []
        filtered_by_id = []

        match_type = self.filter_args.get("match[type]")
        if match_type and "type" in allowed:
            filtered_by_type = self.filter_by_type(data, match_type)

        match_id = self.filter_args.get("match[id]")
        if match_id and "id" in allowed:
            filtered_by_id = self.filter_by_id(data, match_id)

        results = []

        if filtered_by_type and filtered_by_id:
            for type_match in filtered_by_type:
                for id_match in filtered_by_id:
                    if type_match == id_match:
                        results.append(type_match)

        elif match_type:
            if filtered_by_type:
                results.extend(filtered_by_type)

        elif match_id:
            if filtered_by_id:
                results.extend(filtered_by_id)

        else:
            results = data

        match_version = self.filter_args.get("match[version]")
        if "version" in allowed:
            if not match_version:
                match_version = "last"
            # manifest_info must be None when called from get_object_manifest()
            if len(data) > 0 and self.is_manifest_entry(data[0]) and manifest_info is None:
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
                info = None
                for item in manifest_info:
                    if item["id"] == obj["id"]:
                        info = item
                        break
                if info:
                    added_date_timestamp = common.convert_to_stix_datetime(info["date_added"])
                    if added_date_timestamp > added_after_timestamp:
                        new_results.append(obj)
            return new_results
        else:
            return results
