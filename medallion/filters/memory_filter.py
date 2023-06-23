import collections
import itertools
import operator

from ..common import timestamp_to_datetime, timestamp_to_taxii_json
from ..exceptions import ProcessingError
from .common import (
    BUILTIN_PROPERTIES, TAXII_INTEGER_FILTER, TAXII_STRING_FILTER,
    TAXII_TIMESTAMP_FILTER, TAXII_TLP_SHORT_NAME_FILTER, TIER_1_PROPERTIES,
    TIER_2_PROPERTIES, TIER_3_PROPERTIES
)


def _recurse_simple_valued_properties(value):
    """
    Recursively search for and generate simple-valued property names and
    values.
    """

    if isinstance(value, list):
        for sub_value in value:
            yield from _recurse_simple_valued_properties(sub_value)

    elif isinstance(value, dict):
        for key, sub_value in value.items():
            if isinstance(sub_value, (list, dict)):
                yield from _recurse_simple_valued_properties(sub_value)
            else:
                yield key, sub_value


def _simple_valued_properties(obj, include_toplevel=True):
    """
    Find simple-valued properties of the given object.  I.e. properties which
    are neither dicts nor lists.  This generates the prop names and values.
    (And skip over the __meta info.)

    :param obj: The object to search
    :param include_toplevel: Whether to include top level property names and
        values in what is generated.
    """
    for prop_name, prop_value in obj.items():
        if prop_name != "__meta":
            if isinstance(prop_value, (list, dict)):
                yield from _recurse_simple_valued_properties(prop_value)
            elif include_toplevel:
                yield prop_name, prop_value


def _ref_properties(value):
    """
    Find reference property names and values from the given value.  For _refs
    properties, each value is generated separately, with the same key.

    :param value: The value to search
    """
    if isinstance(value, list):
        for sub_value in value:
            yield from _ref_properties(sub_value)

    elif isinstance(value, dict):
        for key, sub_value in value.items():
            if key.endswith("_ref"):
                yield key, sub_value
            elif key.endswith("_refs"):
                for ref in sub_value:
                    yield key, ref
            elif key != "__meta":
                yield from _ref_properties(sub_value)


class Matcher:
    """
    Abstract base class giving the most basic interface for evaluating an
    object against some values given in a query, and producing a true/false
    value.
    """
    def match(self, obj, match_values):
        """
        Perform a match on the given object using the given query values.

        :param obj: The object to match
        :param match_values: An iterable of query values derived from a query
        :return: True if the object matches; False if not
        """
        raise NotImplementedError()


class SimplePropertyValueMatcher(Matcher):
    """
    Abstract base class for matchers which operate by comparing a property
    value from an object against a set of query values.  This might involve
    coercing both the query and property values to a particular type, to ensure
    proper comparison semantics.  So this class adds support for a type
    coercer function.

    Subclasses will expect that match values (i.e. values taken from a query)
    be coerced before passing them to the match() method.  This is more
    efficient than the match() method coercing the same values repeatedly for
    each object being matched.  The coerce_values() method is provided for
    this.
    """
    def __init__(
        self,
        *,
        filter_info
    ):
        """
        Initialize an instance of this matcher.

        :param filter_info: filter info as a TaxiiFilterInfo object
        """
        # We only need the type coercer function, for now
        self.type_coercer = filter_info.type_coercer

    def coerce_values(self, values):
        """
        Coerce the given iterable of values using this object's type coercer
        function.  Return the results of coercion as a set.  Of course, this
        requires that the type being is coerced to, is hashable.

        :param values: Iterable of values to coerce
        :return: Set of coerced values
        """
        return set(
            self.type_coercer(value)
            for value in values
        )


class TopLevelPropertyMatcher(SimplePropertyValueMatcher):
    """
    A matcher which operates by checking the value of a top-level property on
    an object.  Deeper searches are not supported.  This works on list-valued
    properties as well as plain (non-list, non-object) properties.
    """
    def __init__(
        self,
        toplevel_prop_name,
        *,
        filter_info,
        default_value=None
    ):
        """
        Initialize an instance of this matcher.

        :param toplevel_prop_name: The top-level property name to look for
        :param filter_info: filter info as a TaxiiFilterInfo object
        :param default_value: A default value which will be treated as if it
            were in effect if an object does not have the given top-level
            property.  If None, the given top-level property will not be
            treated as having a default value.
        """
        super().__init__(filter_info=filter_info)

        self.toplevel_prop_name = toplevel_prop_name
        self.default_value = default_value

    def match(self, obj, match_values):
        value = obj.get(self.toplevel_prop_name, self.default_value)

        if value is None:
            # Object does not have the property of interest and no default is
            # defined for it, so we just fail the match.
            result = False

        else:

            if not isinstance(value, list):
                value = [value]

            try:
                coerced_values = self.coerce_values(value)

            except ValueError:
                # Type coercion failure
                result = False

            else:
                result = not coerced_values.isdisjoint(match_values)

        return result


class SubPropertyMatcher(SimplePropertyValueMatcher):
    """
    Matcher which matches on a value of a non-top-level simple-valued property.
    A simple-valued property is one whose value is not a list or dict.  The
    whole object, excluding top-level properties, is searched for property(s)
    of a given name, and their value(s) is checked.
    """
    def __init__(
        self,
        sub_prop_name,
        *,
        filter_info
    ):
        super().__init__(filter_info=filter_info)

        self.sub_prop_name = sub_prop_name

    def match(self, obj, match_values):
        result = False

        # This implementation allows a property name to occur in more than one
        # place, and continues searching until a match is found or all
        # properties are checked.  Should we optimize and give up searching
        # after the first occurrence (i.e. assume a given property never occurs
        # in more than one place in an object)?
        for prop_name, simple_prop_value \
                in _simple_valued_properties(obj, include_toplevel=False):
            if prop_name == self.sub_prop_name:
                try:
                    coerced_value = self.type_coercer(simple_prop_value)
                except ValueError:
                    # Type coercion failure
                    result = False
                else:
                    result = coerced_value in match_values

            if result:
                break

        return result


class TLPMatcher(SimplePropertyValueMatcher):
    """
    Matcher which checks TLP markings, including object and granular markings.
    """

    def __init__(self):
        super().__init__(
            # hard-code this; can't be anything else!
            filter_info=TAXII_TLP_SHORT_NAME_FILTER
        )

    def match(self, obj, match_values):
        # Dump all markings into the same set; there is no need to distinguish
        # object from granular, for this purpose.
        all_marking_refs = set(obj.get("object_marking_refs", []))

        granular_markings = obj.get("granular_markings", [])
        for granular_marking in granular_markings:
            marking_ref = granular_marking.get("marking_ref")
            if marking_ref:
                all_marking_refs.add(marking_ref)

        result = not all_marking_refs.isdisjoint(match_values)

        return result


class RelationshipsAllMatcher(SimplePropertyValueMatcher):
    """
    Matches objects based on their embedded references.
    """
    def __init__(self):
        super().__init__(
            filter_info=TAXII_STRING_FILTER
        )

    def match(self, obj, match_values):

        result = False
        for ref_prop_name, ref_prop_value in _ref_properties(obj):

            result = ref_prop_value in match_values

            if result:
                break

        return result


class CalculationMatcher(SimplePropertyValueMatcher):
    """
    Matches objects based on an arbitrary boolean valued function evaluated on
    a property value and a query value, e.g. the property value be less than
    at least one of the query values.
    """
    def __init__(self, prop_name, op, *, filter_info):
        super().__init__(filter_info=filter_info)

        self.prop_name = prop_name
        self.op = op

    def match(self, obj, match_values):

        result = False
        for prop_name, prop_value in _simple_valued_properties(obj):

            if prop_name == self.prop_name:
                try:
                    prop_value = self.type_coercer(prop_value)

                except ValueError:
                    # Type coercion failure
                    result = False

                else:
                    result = any(
                        self.op(prop_value, match_value)
                        for match_value in match_values
                    )

                if result:
                    break

        return result


class AddedAfterMatcher(SimplePropertyValueMatcher):
    """
    Matches objects based on date_added metadata.
    """
    def __init__(self):
        super().__init__(filter_info=TAXII_TIMESTAMP_FILTER)

    def match(self, obj, match_values):
        # In case there are multiple query values.  But there shouldn't be.
        match_value = min(match_values)

        return obj["__meta"].date_added > match_value


class SpecVersionMatcher(Matcher):
    """
    Matcher which supports the TAXII spec_version match field.
    """
    def __init__(self, data):
        """
        Initialize this matcher.  This prepares the matcher to operate on the
        objects in the given data set, by setting up a data structure to make
        it more efficient.

        :param data: A list of objects from the memory backend, which will be
            subject to this matcher.
        """

        # Build a map from ID to a list of all objects of the latest spec
        # version, with that ID.  We treat plain versioning as being able to
        # span spec versions, i.e. all objects with the same ID are part of
        # the same history, regardless of spec_version.  We need to find all
        # objects of the latest spec version from each ID.
        self.__spec_latest = collections.defaultdict(list)
        for obj in data:

            latest_objects = self.__spec_latest[obj["id"]]

            if latest_objects:
                obj_spec_version = obj["__meta"].spec_version_tuple
                latest_spec_version = latest_objects[0]["__meta"].spec_version_tuple

                if obj_spec_version > latest_spec_version:
                    latest_objects.clear()
                    latest_objects.append(obj)

                elif obj_spec_version == latest_spec_version:
                    latest_objects.append(obj)

            else:
                latest_objects.append(obj)

    def latest_objects(self):
        yield from itertools.chain.from_iterable(self.__spec_latest.values())

    def match(self, obj, match_values):
        """
        Perform the match.  If match_values is None, return a match if obj is
        the latest spec version.

        :param obj: The object to match
        :param match_values: A list of spec versions (strings), or None
        :return: True if obj matches; False if not
        """

        result = False
        if match_values:
            result = obj["__meta"].spec_version in match_values

        else:
            # if match_values is None, we want the latest spec version.
            latest_objects = self.__spec_latest[obj["id"]]

            if latest_objects:
                # Fearing "obj in latest_objects" might be slow.  It might have
                # to search all dict entries to determine equality of two
                # dicts.  But obj and the objects in latest_objects are
                # versions from the same family of objects, so it is only
                # necessary to check for a matching version.
                result = obj["__meta"].version in (
                    o["__meta"].version for o in latest_objects
                )
            # else:  An object we've never seen before??  Eval to false I
            # guess?

        return result


class VersionMatcher(Matcher):
    """
    Matcher which supports the TAXII version match field.
    """
    def __init__(self, data):
        """
        Initialize this matcher.  This prepares the matcher to operate on the
        objects in the given data set, by setting up a data structure to make
        it more efficient.

        :param data: A list of objects from the memory backend, which will be
            subject to this matcher.
        """

        # Map from ID to the earliest and latest versions of objects from that
        # family of objects.  We treat plain versioning as being able to
        # span spec versions, i.e. all objects with the same ID are part of
        # the same history, regardless of spec_version.  This means the
        # earliest and latest versions may not be of the same spec_version.
        self.__earliest_latest_versions = {}
        for obj in data:

            versions = self.__earliest_latest_versions.get(obj["id"])
            if versions:
                earliest, latest = versions
                if obj["__meta"].version < earliest["__meta"].version:
                    versions[0] = obj
                if obj["__meta"].version > latest["__meta"].version:
                    versions[1] = obj

            else:
                self.__earliest_latest_versions[obj["id"]] = [obj, obj]

    def earliest_objects(self):
        """
        Generate the earliest objects from this matcher's internal data
        structure; this enables some optimizations.
        """
        for earliest, _ in self.__earliest_latest_versions.values():
            yield earliest

    def latest_objects(self):
        """
        Generate the latest objects from this matcher's internal data
        structure; this enables some optimizations.
        """
        for _, latest in self.__earliest_latest_versions.values():
            yield latest

    def earliest_latest_objects(self):
        """
        Generate all of the earlist and latest objects from this matcher's
        internal data structure; this enables some optimizations.
        """
        for earliest, latest in self.__earliest_latest_versions.values():
            yield earliest

            if earliest is not latest:
                # In case the earliest and latest are the same, don't cause
                # duplication of objects!
                yield latest

    def match(self, obj, match_values):
        """
        Perform the match.  If match_values is None, return a match if obj is
        the latest version.

        :param obj: The object to match
        :param match_values: A list of versions, each of which can be "first",
            "last", "all", or a datetime object; or None
        :return: True if obj matches; False if not
        """

        versions = self.__earliest_latest_versions.get(obj["id"])

        result = False
        if versions:
            earliest, latest = versions

            if match_values:
                for match_value in match_values:
                    if match_value == "all":
                        result = True
                    elif match_value == "first":
                        result = obj is earliest
                    elif match_value == "last":
                        result = obj is latest
                    else:
                        # match_value is a datetime object
                        result = obj["__meta"].version == match_value

                    if result:
                        break

            else:
                # match_values is None; match only the latest object.
                result = obj is latest

        # else: an object we've never seen before??  Eval to false I guess?

        return result


# These defined by the TAXII spec itself.
_BUILTIN_MATCHERS = {
    match_type: TopLevelPropertyMatcher(match_type, filter_info=filter_info)
    for match_type, filter_info in BUILTIN_PROPERTIES.items()
}


# Tier 1 defined as "simple top-level properties".
_INTEROP_TIER_1_MATCHERS = {
    match_type: TopLevelPropertyMatcher(
        match_type,
        filter_info=filter_info,
        # "revoked" is the one case where we have a default to consider
        default_value=False if match_type == "revoked" else None
    )
    for match_type, filter_info in TIER_1_PROPERTIES.items()
}


# Tier 2 defined as "array elements (lists) defined as top-level properties".
_INTEROP_TIER_2_MATCHERS = {
    match_type: TopLevelPropertyMatcher(match_type, filter_info=filter_info)
    for match_type, filter_info in TIER_2_PROPERTIES.items()
}


# Tier 3 defined as "properties defined within nested structures".
_INTEROP_TIER_3_MATCHERS = {
    match_type:
        TLPMatcher() if match_type == "tlp"  # special matcher for tlp
        else SubPropertyMatcher(match_type, filter_info=filter_info)
    for match_type, filter_info in TIER_3_PROPERTIES.items()
}


_INTEROP_RELATIONSHIPS_MATCHERS = {
    "relationships-all": RelationshipsAllMatcher()
}


_INTEROP_CALCULATION_MATCHERS = {
    "confidence-gte": CalculationMatcher(
        "confidence", operator.ge, filter_info=TAXII_INTEGER_FILTER
    ),
    "confidence-lte": CalculationMatcher(
        "confidence", operator.le, filter_info=TAXII_INTEGER_FILTER
    ),
    "modified-gte": CalculationMatcher(
        "modified", operator.ge, filter_info=TAXII_TIMESTAMP_FILTER
    ),
    "modified-lte": CalculationMatcher(
        "modified", operator.le, filter_info=TAXII_TIMESTAMP_FILTER
    ),
    "number-gte": CalculationMatcher(
        "number", operator.ge, filter_info=TAXII_INTEGER_FILTER
    ),
    "number-lte": CalculationMatcher(
        "number", operator.le, filter_info=TAXII_INTEGER_FILTER
    ),
    "src_port-gte": CalculationMatcher(
        "src_port", operator.ge, filter_info=TAXII_INTEGER_FILTER
    ),
    "src_port-lte": CalculationMatcher(
        "src_port", operator.le, filter_info=TAXII_INTEGER_FILTER
    ),
    "dst_port-gte": CalculationMatcher(
        "dst_port", operator.ge, filter_info=TAXII_INTEGER_FILTER
    ),
    "dst_port-lte": CalculationMatcher(
        "dst_port", operator.le, filter_info=TAXII_INTEGER_FILTER
    ),
    "valid_until-gte": CalculationMatcher(
        "valid_until", operator.ge, filter_info=TAXII_TIMESTAMP_FILTER
    ),
    "valid_from-lte": CalculationMatcher(
        "valid_from", operator.le, filter_info=TAXII_TIMESTAMP_FILTER
    )
}


# Special case filter query param which does not use the match[...] syntax.
_ADDED_AFTER_MATCHER = AddedAfterMatcher()


def _speed_tier(filter_name):
    """
    As an optimization, filters can be sorted such that faster matchers run
    first.  If a fast matcher rejects an object, it prevents slower matchers
    from needing to run, which speeds up the filtering process.  This function
    is usable as a sort key function on filter names, to sort by speed.  It
    returns an integer "speed tier" which is just a simple integer performance
    rating, where smaller is faster.

    :param filter_name: A filter name
    :return: A speed tier as an integer
    """

    if filter_name.startswith("match[") and filter_name.endswith("]"):
        filter_name = filter_name[6:-1]

    # Simple matchers on fixed properties should be quick
    if filter_name in _BUILTIN_MATCHERS \
            or filter_name in _INTEROP_TIER_1_MATCHERS \
            or filter_name == "added_after":
        speed_tier = 1

    # Similarly quick to tier 1, but these need to search through list
    # valued properties, so a bit slower
    elif filter_name in _INTEROP_TIER_2_MATCHERS:
        speed_tier = 2

    # These need to search whole objects, which can be slow
    elif filter_name in _INTEROP_TIER_3_MATCHERS \
            or filter_name in _INTEROP_RELATIONSHIPS_MATCHERS \
            or filter_name in _INTEROP_CALCULATION_MATCHERS:
        speed_tier = 3

    else:
        speed_tier = 4

    return speed_tier


def _get_property_matcher(filter_arg, interop):
    """
    Get a pre-instantiated property matcher for the given filter, if one
    exists.  Most filters are like this; match[version] and match[spec_version]
    are notable exceptions, since their behavior must depend on a larger
    context than just the object being filtered.  This means those matchers
    can't be pre-instantiated, i.e. the same matcher instance can't be used for
    all datasets.

    :param filter_arg: The value of a filter query parameter, e.g. "match[foo]"
    :param interop: Whether to recognize interop filters.  If True, additional
        types of matchers may be returned.
    :return: A matcher object, or None if one could not be found for the given
        query parameter.
    """
    matcher = None

    if filter_arg == "added_after":
        matcher = _ADDED_AFTER_MATCHER

    elif filter_arg.startswith("match[") and filter_arg.endswith("]"):
        filter_name = filter_arg[6:-1]
        matcher = _BUILTIN_MATCHERS.get(filter_name)

        if not matcher and interop:
            matcher = _INTEROP_TIER_1_MATCHERS.get(filter_name) \
                or _INTEROP_TIER_2_MATCHERS.get(filter_name) \
                or _INTEROP_TIER_3_MATCHERS.get(filter_name) \
                or _INTEROP_RELATIONSHIPS_MATCHERS.get(filter_name) \
                or _INTEROP_CALCULATION_MATCHERS.get(filter_name)

    return matcher


def _do_version_filter(objects, version_match_values):
    """
    Performs match[version] filtering.

    :param objects: The objects to filter
    :param version_match_values: The value of the match[version] query
        parameter, or None.  If None, treat as "last".
    :return: A list of matching objects
    """
    if version_match_values:
        version_match_values = version_match_values.split(",")
    else:
        version_match_values = ["last"]

    # Do nothing if "all" is included as a match value.  VersionMatcher does
    # handle it correctly, but as an optimization we should just skip the
    # filtering altogether if we can.
    if "all" in version_match_values:
        matched_objects = objects

    else:

        # Must coerce datetime strings to objects; also convert to a set,
        # which makes subsequent code simpler.
        for idx, value in enumerate(version_match_values):
            if value not in ("first", "last", "all"):
                try:
                    version_match_values[idx] = timestamp_to_datetime(value)
                except ValueError:
                    raise ProcessingError(
                        "Invalid query value for match[version]: " + value,
                        400
                    )

        version_match_values = set(version_match_values)

        version_matcher = VersionMatcher(objects)

        # We can do some more optimizations: since construction of
        # VersionMatcher above sets up a data structure where the earliest and
        # latest versions of all objects are readily available, if the
        # match values include only "first"/"last", we can use that directly
        # and avoid looping through all the objects again.
        if version_match_values == {"first"}:
            matched_objects = list(version_matcher.earliest_objects())

        elif version_match_values == {"last"}:
            matched_objects = list(version_matcher.latest_objects())

        elif version_match_values == {"first", "last"}:
            matched_objects = list(version_matcher.earliest_latest_objects())

        else:
            matched_objects = [
                obj for obj in objects
                if version_matcher.match(obj, version_match_values)
            ]

    return matched_objects


def _do_spec_version_filter(objects, spec_version_match_values):
    """
    Performs match[spec_version] filtering.

    :param objects: The objects to filter
    :param spec_version_match_values: The value of the match[spec_version]
        query parameter, or None.  If None, retain only the latest spec
        versions of objects.
    :return: A list of matching objects
    """
    if spec_version_match_values:
        spec_version_match_values = spec_version_match_values.split(",")

    spec_version_matcher = SpecVersionMatcher(objects)

    if spec_version_match_values:
        matched_objects = [
            obj for obj in objects
            if spec_version_matcher.match(obj, spec_version_match_values)
        ]

    else:
        # match[spec_version] not given.  We must retain the latest spec
        # versions of objects.
        #
        # As an optimization, take advantage of the data structure which
        # SpecVersionMatcher has already created, to get the latest versions
        # of everything.
        matched_objects = list(spec_version_matcher.latest_objects())

    return matched_objects


class MemoryFilter(object):

    def __init__(self, filter_args, interop=False):
        self.filter_args = filter_args
        self.interop = interop

        # Optimization: order filter application such that faster filters
        # run first.
        self.filter_order = sorted(self.filter_args, key=_speed_tier)

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
            headers["X-TAXII-Date-Added-First"] = timestamp_to_taxii_json(
                new[0]["__meta"].date_added
            )
            headers["X-TAXII-Date-Added-Last"] = timestamp_to_taxii_json(
                new[-1]["__meta"].date_added
            )

        return new, next_save, headers

    def process_filter(self, data, limit=None):

        # Collect the match objects and relevant information we need to do
        # the filtering.  This weeds out filter args we don't recognize, and
        # which aren't simple filters we can handle in a uniform way.  We can
        # handle the bulk of them uniformly like this.
        prop_matchers = []
        for filter_key in self.filter_order:
            matcher = _get_property_matcher(filter_key, self.interop)

            if matcher:
                filter_values = set(self.filter_args[filter_key].split(","))

                if isinstance(matcher, SimplePropertyValueMatcher):
                    try:
                        filter_values = matcher.coerce_values(filter_values)
                    except ValueError:
                        # Type coercion failure.
                        raise ProcessingError(
                            "Invalid query value(s) for " + filter_key, 400
                        )

                prop_matchers.append((matcher, filter_values))

        matched_objects = []
        for obj in data:
            for matcher, match_values in prop_matchers:
                if not matcher.match(obj, match_values):
                    break
            else:
                matched_objects.append(obj)

        # match[version] and match[spec_version] need more specialized handling
        # due to their requirement to handle "first" and "last" type values.
        # Those evaluations can't be done solely based on an individual object.
        matched_objects = _do_version_filter(
            matched_objects, self.filter_args.get("match[version]")
        )

        matched_objects = _do_spec_version_filter(
            matched_objects, self.filter_args.get("match[spec_version]")
        )

        # sort objects by date_added and paginate as necessary
        final_match, save_next, headers = self.sort_and_paginate(
            matched_objects, limit
        )

        return final_match, save_next, headers