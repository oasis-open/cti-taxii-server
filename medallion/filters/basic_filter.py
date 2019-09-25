import copy

from ..utils.common import convert_to_stix_datetime


def find_att(obj):
    if "version" in obj:
        return "version"
    elif "modified" in obj:
        return "modified"
    elif "created" in obj:
        return "created"
    else:
        # TO DO: PUT DEFAULT VALUE HERE
        pass


class BasicFilter(object):

    def __init__(self, filter_args):
        self.filter_args = filter_args

    @staticmethod
    def filter_by_id(data, id_):
        id_ = id_.split(",")

        match_objects = []

        for obj in data:
            if "id" in obj and any(s == obj["id"] for s in id_):
                match_objects.append(obj)

        return match_objects

    @staticmethod
    def filter_by_added_after(data, manifest_info, added_after_date):
        added_after_timestamp = convert_to_stix_datetime(added_after_date)
        new_results = []
        # for manifest objects
        if manifest_info is None:
            for obj in data:
                if obj in new_results:
                    continue
                added_date_timestamp = convert_to_stix_datetime(obj["date_added"])
                if added_date_timestamp > added_after_timestamp:
                    new_results.append(obj)
        # for other objects with manifests
        else:
            for obj in data:
                if obj in new_results:
                    continue
                for item in manifest_info:
                    if item["id"] == obj["id"]:
                        added_date_timestamp = convert_to_stix_datetime(item["date_added"])
                        if added_date_timestamp > added_after_timestamp:
                            new_results.append(obj)
        return new_results

    @staticmethod
    # this could be put together into one for loop
    # is the ordering of the results important?
    def filter_by_version(data, version):
        match_objects = []
        # return most recent object versions unless otherwise specified
        if version is None:
            version = "last"
        if "first" not in version and "last" not in version:
            version = version + ",last"
        version_indicators = version.split(",")

        if "all" in version_indicators:
            # if "all" is in the list, just return everything
            return data

        actual_dates = [x for x in version_indicators if x != "first" and x != "last"]
        # if a specific version is given, filter for objects with that value
        if actual_dates:
            for obj in data:
                obj_att = find_att(obj)
                if obj[obj_att] in actual_dates:
                    match_objects.append(obj)
        else:
            match_objects = copy.deepcopy(data)

        if "first" in version_indicators and match_objects:
            for obj in match_objects:
                obj_att = find_att(obj)
                obj_time = convert_to_stix_datetime(obj[obj_att])
                for compare in match_objects:
                    comp_att = find_att(compare)
                    comp_time = convert_to_stix_datetime(compare[comp_att])
                    if compare is not obj and compare["id"] == obj["id"] and comp_time <= obj_time:
                        match_objects.remove(obj)
                        break

        if match_objects and "last" in version_indicators:
            for obj in match_objects:
                obj_att = find_att(obj)
                obj_time = convert_to_stix_datetime(obj[obj_att])
                for compare in match_objects:
                    comp_att = find_att(compare)
                    comp_time = convert_to_stix_datetime(compare[comp_att])
                    if compare is not obj and compare["id"] == obj["id"] and comp_time >= obj_time:
                        match_objects.remove(obj)
                        break

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

    @staticmethod
    def filter_by_spec_version(data, spec_):
        spec_ = spec_.split(",")

        match_objects = []

        for obj in data:
            if "spec_version" in obj and any(s == obj["spec_version"] for s in spec_):
                match_objects.append(obj)
            elif "media_type" in obj and any(s == obj["media_type"].split("version=")[1] for s in spec_):
                # this is assuming all manifests will have the media_type attribute
                # change this if there is another way
                match_objects.append(obj)

        return match_objects

    def process_filter(self, data, allowed, manifest_info):
        filtered_by_type = []
        filtered_by_id = []
        filtered_by_version = []
        filtered_by_spec_version = []
        filtered_by_added_after = []

        # match for type and id filters first
        match_type = self.filter_args.get("match[type]")
        if match_type and "type" in allowed:
            filtered_by_type = self.filter_by_type(data, match_type)

        match_id = self.filter_args.get("match[id]")
        if match_id and "id" in allowed:
            filtered_by_id = self.filter_by_id(data, match_id)

        initial_results = []

        if filtered_by_type and filtered_by_id:
            for type_match in filtered_by_type:
                for id_match in filtered_by_id:
                    if type_match == id_match:
                        initial_results.append(type_match)
        elif match_type:
            if filtered_by_type:
                initial_results.extend(filtered_by_type)
        elif match_id:
            if filtered_by_id:
                initial_results.extend(filtered_by_id)
        else:
            initial_results = copy.deepcopy(data)

        # match for spec_version
        match_spec_version = self.filter_args.get("match[spec_version]")
        if match_spec_version and "spec_version" in allowed:
            filtered_by_spec_version = self.filter_by_spec_version(initial_results, match_spec_version)
        else:
            filtered_by_spec_version = initial_results

        # match for added_after
        added_after_date = self.filter_args.get("added_after")
        if added_after_date is not None:
            filtered_by_added_after = self.filter_by_added_after(filtered_by_spec_version, manifest_info, added_after_date)
        else:
            filtered_by_added_after = filtered_by_spec_version

        # match for version, and get rid of duplicates as appropriate
        match_version = self.filter_args.get("match[version]")
        filtered_by_version = self.filter_by_version(filtered_by_added_after, match_version)

        return filtered_by_version
