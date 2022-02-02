import bisect
import operator

from ..common import determine_spec_version, find_att, string_to_datetime


def check_for_dupes(final_match, final_track, res):
    for obj in res:
        found = 0
        pos = bisect.bisect_left(final_track, obj["id"])
        if not final_match or pos > len(final_track) - 1 or final_track[pos] != obj["id"]:
            final_track.insert(pos, obj["id"])
            final_match.insert(pos, obj)
        else:
            obj_time = find_att(obj)
            while pos != len(final_track) and obj["id"] == final_track[pos]:
                if find_att(final_match[pos]) == obj_time:
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
            if relate(find_att(obj), find_att(res[pos])):
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

    def sort_and_paginate(self, data, limit, manifest):
        temp = None
        next_save = {}
        headers = {}
        new = []
        if len(data) == 0:
            return new, next_save, headers
        if manifest:
            manifest.sort(key=lambda x: x['date_added'])
            for man in manifest:
                man_time = find_att(man)
                for check in data:
                    check_time = find_att(check)
                    if check['id'] == man['id'] and check_time == man_time:
                        if len(headers) == 0:
                            headers["X-TAXII-Date-Added-First"] = man["date_added"]
                        new.append(check)
                        temp = man
                        if len(new) == limit:
                            headers["X-TAXII-Date-Added-Last"] = man["date_added"]
                        break
            if limit and limit < len(data):
                next_save = new[limit:]
                new = new[:limit]
            else:
                headers["X-TAXII-Date-Added-Last"] = temp["date_added"]
        else:
            data.sort(key=lambda x: x['date_added'])
            if limit and limit < len(data):
                next_save = data[limit:]
                data = data[:limit]
            headers["X-TAXII-Date-Added-First"] = data[0]["date_added"]
            headers["X-TAXII-Date-Added-Last"] = data[-1]["date_added"]
            new = data
        return new, next_save, headers

    @staticmethod
    def check_added_after(obj, manifest_info, added_after_date):
        added_after_timestamp = string_to_datetime(added_after_date)
        # for manifest objects and versions
        if manifest_info is None:
            if string_to_datetime(obj["date_added"]) > added_after_timestamp:
                return True
            return False
        # for other objects with manifests
        else:
            obj_time = find_att(obj)
            for item in manifest_info:
                item_time = find_att(item)
                if item["id"] == obj["id"] and item_time == obj_time and string_to_datetime(item["date_added"]) > added_after_timestamp:
                    return True
                    break
            return False

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
                obj_time = find_att(obj)
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

    def process_filter(self, data, allowed=(), manifest_info=(), limit=None):
        filtered_by_version = []
        final_match = []
        save_next = []
        headers = {}
        match_objects = []
        # match for type and id filters first
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
                    if not self.check_added_after(obj, manifest_info, self.added_after_date):
                        continue

                if "spec_version" in allowed:
                    if not self.check_by_spec_version(obj, self.match_spec_version, data):
                        continue
                match_objects.append(obj)
        else:
            match_objects = data
        # match for version, and get rid of duplicates as appropriate
        if "version" in allowed:
            match_version = self.filter_args.get("match[version]")
            filtered_by_version = self.filter_by_version(match_objects, match_version)
        else:
            filtered_by_version = match_objects

        # sort objects by date_added of manifest and paginate as necessary
        final_match, save_next, headers = self.sort_and_paginate(filtered_by_version, limit, manifest_info)
        return final_match, save_next, headers
