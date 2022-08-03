import bisect
import operator

from ..common import determine_spec_version, string_to_datetime, datetime_to_string


def check_for_dupes(final_match, final_track, res):
    for obj in res:
        found = 0
        pos = bisect.bisect_left(final_track, obj["id"])
        if not final_match or pos > len(final_track) - 1 or final_track[pos] != obj["id"]:
            final_track.insert(pos, obj["id"])
            final_match.insert(pos, obj)
        else:
            obj_time = obj["__meta"].version
            while pos != len(final_track) and obj["id"] == final_track[pos]:
                if final_match[pos]["__meta"].version == obj_time:
                    found = 1
                    break
                else:
                    pos = pos + 1
            if found == 1:
                continue
            else:
                final_track.insert(pos, obj["id"])
                final_match.insert(pos, obj)


def check_version(data, relate):
    id_track = []
    res = []
    for obj in data:
        pos = bisect.bisect_left(id_track, obj["id"])
        if not res or pos >= len(id_track) or id_track[pos] != obj["id"]:
            id_track.insert(pos, obj["id"])
            res.insert(pos, obj)
        else:
            incoming_ver = obj["__meta"].version
            existing_ver = res[pos]["__meta"].version
            if relate(incoming_ver, existing_ver):
                res[pos] = obj
    return res


class BasicFilter(object):

    def __init__(self, filter_args):
        self.filter_args = filter_args
        self.match_type = self.filter_args.get("match[type]")
        if self.match_type:
            self.match_type = self.match_type.split(",")
        self.match_id = self.filter_args.get("match[id]")
        if self.match_id:
            self.match_id = self.match_id.split(",")
        self.added_after_date = self.filter_args.get("added_after")
        self.match_spec_version = self.filter_args.get("match[spec_version]")
        if self.match_spec_version:
            self.match_spec_version = self.match_spec_version.split(",")

    def sort_and_paginate(self, data, limit):
        data.sort(key=lambda x: x["__meta"].date_added)

        if limit is None:
            new = data
            next_save = []
        else:
            new = data[:limit]
            next_save = data[limit:]

        headers = {}
        if new:
            headers["X-TAXII-Date-Added-First"] = datetime_to_string(
                new[0]["__meta"].date_added
            )
            headers["X-TAXII-Date-Added-Last"] = datetime_to_string(
                new[-1]["__meta"].date_added
            )

        return new, next_save, headers

    @staticmethod
    def check_added_after(obj, added_after_date):
        added_after_timestamp = string_to_datetime(added_after_date)
        obj_added = obj["__meta"].date_added
        return obj_added > added_after_timestamp

    @staticmethod
    def filter_by_version(data, version):
        # final_match is a sorted list of objects
        final_match = []
        # final_track is a sorted list of id's
        final_track = []

        # return most recent object versions unless otherwise specified
        if version is None:
            version = "last"
        version_indicators = version.split(",")

        if "all" in version_indicators:
            # if "all" is in the list, just return everything
            return data

        actual_dates = [string_to_datetime(x) for x in version_indicators if x != "first" and x != "last"]
        # if a specific version is given, filter for objects with that value
        if actual_dates:
            id_track = []
            res = []
            for obj in data:
                obj_time = obj["__meta"].version
                if obj_time in actual_dates:
                    pos = bisect.bisect_left(id_track, obj["id"])
                    id_track.insert(pos, obj["id"])
                    res.insert(pos, obj)
            final_match = res
            final_track = id_track

        if "first" in version_indicators:
            res = check_version(data, operator.lt)
            check_for_dupes(final_match, final_track, res)

        if "last" in version_indicators:
            res = check_version(data, operator.gt)
            check_for_dupes(final_match, final_track, res)

        return final_match

    @staticmethod
    def check_by_spec_version(obj, spec_, data):
        if spec_:
            if "media_type" in obj:
                if any(s == obj["media_type"].split("version=")[1] for s in spec_):
                    return True
            elif any(s == determine_spec_version(obj) for s in spec_):
                return True
        else:
            add = True
            if "media_type" in obj:
                s1 = obj["media_type"].split("version=")[1]
            else:
                s1 = determine_spec_version(obj)
            for match in data:
                if "media_type" in match:
                    s2 = match["media_type"].split("version=")[1]
                else:
                    s2 = determine_spec_version(match)
                if obj["id"] == match["id"] and s2 > s1:
                    add = False
            if add:
                return True
        return False

    def process_filter(self, data, allowed=(), limit=None):
        filtered_by_version = []
        final_match = []
        save_next = []
        headers = {}
        match_objects = []
        if (self.match_type and "type" in allowed) or (self.match_id and "id" in allowed) \
           or (self.added_after_date) or ("spec_version" in allowed):
            for obj in data:
                if self.match_type and "type" in allowed:
                    if not (any(s == obj.get("type") for s in self.match_type)) and not (any(s == obj.get("id").split("--")[0] for s in self.match_type)):
                        continue
                if self.match_id and "id" in allowed:
                    if not ("id" in obj and any(s == obj["id"] for s in self.match_id)):
                        continue

                if self.added_after_date:
                    if not self.check_added_after(obj, self.added_after_date):
                        continue

                if "spec_version" in allowed:
                    if not self.check_by_spec_version(obj, self.match_spec_version, data):
                        continue
                match_objects.append(obj)
        else:
            match_objects = data
        if "version" in allowed:
            match_version = self.filter_args.get("match[version]")
            filtered_by_version = self.filter_by_version(match_objects, match_version)
        else:
            filtered_by_version = match_objects

        # sort objects by date_added and paginate as necessary
        final_match, save_next, headers = self.sort_and_paginate(filtered_by_version, limit)
        return final_match, save_next, headers
