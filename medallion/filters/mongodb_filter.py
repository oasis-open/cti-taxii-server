from bson.son import SON
from pymongo import ASCENDING

import medallion.common
import medallion.filters.common

from ..exceptions import ProcessingError

# These are basically "blueprints" for how to construct mongo queries.  They
# are primarily intended for the more complicated interop match filters, e.g.
# tier 3.  Tier 3 filters require looking in various places inside nested
# structures within objects.  The following describes where to look, within
# which types of STIX objects.
#
# The top level keys are the values in square brackets in "match[...]" style
# TAXII query parameters.  The next level keys are STIX types, which determine
# which type of objects will be examined for that query.  The STIX type keys
# map to a list of mongo query paths specific to the type.  These are used
# directly in mongo queries, so they must follow mongo query syntax rules.
#
# Where None is used for a STIX type (second level key), it means the mapped
# paths should be searched in all object types.  This is appropriate for very
# general facilities which exist across all STIX object types.
_MONGO_MATCH_SPECS = {
    "address_family": {
        "network-traffic": ["extensions.socket-ext.address_family"]
    },
    "external_id": {
        None: ["external_references.external_id"]
    },
    "integrity_level": {
        "process": ["extensions.windows-process-ext.integrity_level"]
    },
    "pe_type": {
        "file": ["extensions.windows-pebinary-ext.pe_type"]
    },
    "phase_name": {
        "attack-pattern": ["kill_chain_phases.phase_name"],
        "indicator": ["kill_chain_phases.phase_name"],
        "infrastructure": ["kill_chain_phases.phase_name"],
        "malware": ["kill_chain_phases.phase_name"],
        "tool": ["kill_chain_phases.phase_name"]
    },
    "service_status": {
        "process": ["extensions.windows-service-ext.service_status"]
    },
    "service_type": {
        "process": ["extensions.windows-service-ext.service_type"]
    },
    "socket_type": {
        "network-traffic": ["extensions.socket-ext.socket_type"]
    },
    "source_name": {
        None: ["external_references.source_name"]
    },
    "start_type": {
        "process": ["extensions.windows-service-ext.start_type"]
    },
    "tlp": {
        None: [
            "object_marking_refs",
            "granular_markings.marking_ref"
        ]
    },
    # Relationships interop filter, for locating embedded relationships
    "relationships-all": {
        None: [
            "created_by_ref",
            "granular_markings.marking_ref",
            "object_marking_refs"
        ],
        "directory": [
            "contains_refs"
        ],
        "domain-name": [
            "resolves_to_refs"
        ],
        "email-addr": [
            "belongs_to_ref"
        ],
        "email-message": [
            "bcc_refs",
            "body_multipart.body_raw_ref",
            "cc_refs",
            "from_ref",
            "raw_email_ref",
            "sender_ref",
            "to_refs"
        ],
        "file": [
            "contains_refs",
            "extensions.archive-ext.contains_refs",
            "content_ref",
            "parent_directory_ref"
        ],
        "grouping": [
            "object_refs"
        ],
        "ipv4-addr": [
            "belongs_to_refs",
            "resolves_to_refs"
        ],
        "ipv6-addr": [
            "belongs_to_refs",
            "resolves_to_refs"
        ],
        "language-content": [
            "object_ref"
        ],
        "malware": [
            "operating_system_refs",
            "sample_refs"
        ],
        "malware-analysis": [
            "analysis_sco_refs",
            "host_vm_ref",
            "installed_software_refs",
            "operating_system_ref",
            "sample_ref"
        ],
        "network-traffic": [
            "dst_payload_ref",
            "dst_ref",
            "encapsulated_by_ref",
            "encapsulates_refs",
            "extensions.http-request-ext.message_body_data_ref",
            "src_payload_ref",
            "src_ref"
        ],
        "note": [
            "object_refs"
        ],
        "observed-data": [
            "object_refs"
        ],
        "opinion": [
            "object_refs"
        ],
        "process": [
            "child_refs",
            "creator_user_ref",
            "image_ref",
            "opened_connection_refs",
            "parent_ref",
            "extensions.windows-service-ext.service_dll_refs"
        ],
        "relationship": [
            "source_ref",
            "target_ref"
        ],
        "report": [
            "object_refs"
        ],
        "sighting": [
            "observed_data_refs",
            "sighting_of_ref",
            "where_sighted_refs"
        ],
        "windows-registry-key": [
            "creator_user_ref"
        ]
    }
}


# Make the hashes entries to the above mapping programmatically... too verbose
# to write it all out directly!
for hash_type in (
    "MD5",
    "SHA-1",
    "SHA-256",
    "SHA-512",
    "SHA3-256",
    "SHA3-512",
    "SSDEEP",
    "TLSH"
):
    _MONGO_MATCH_SPECS[hash_type] = {
        None: ["external_references.hashes." + hash_type],
        "artifact": ["hashes." + hash_type],
        "file": [
            "hashes." + hash_type,
            "extensions.ntfs-ext.alternate_data_streams.hashes." + hash_type,
            "extensions.windows-pebinary-ext.file_header_hashes." + hash_type,
            "extensions.windows-pebinary-ext.optional_header.hashes." + hash_type,
            "extensions.windows-pebinary-ext.sections.hashes." + hash_type,
        ],
        "x509-certificate": ["hashes." + hash_type]
    }


def _coerce_filter_args(filter_args):
    """
    Split query parameter values on commas, and coerce them to python types
    appropriate to the semantics of the TAXII filter and this mongo backend
    implementation.

    Unrecognized parameters are split on commas but their values are otherwise
    not changed.

    :param filter_args: TAXII HTTP query parameters, as a mapping from string
        to string.
    :return: A mapping from string to list of values of other types.
    :raises ProcessingError: If coercion of any parameter value fails
    """

    coerced_filter_args = {}

    for arg_name, arg_value in filter_args.items():

        coerced_values = []
        split_values = arg_value.split(",")
        # use this when iterating over split_values; the catch clause uses it
        # to reference a particular split value which failed coercion.
        split_value = None

        try:

            if arg_name.startswith("match[") and arg_name.endswith("]"):
                match_filter_name = arg_name[6:-1]
                filter_info = medallion.filters.common.get_filter_info(
                    match_filter_name
                )

                if filter_info:
                    for split_value in split_values:
                        coerced_values.append(
                            filter_info.type_coercer(split_value)
                        )

                elif match_filter_name == "version":
                    # Special case match[...] filter: version values have a mix
                    # of formats; can't treat all the same way.
                    for split_value in split_values:
                        if split_value in ("first", "last", "all"):
                            coerced_value = split_value
                        else:
                            coerced_value = medallion.common.timestamp_to_epoch_seconds(
                                split_value
                            )
                        coerced_values.append(coerced_value)

                else:
                    # Unrecognized match[...] filter; use values as-is
                    coerced_values = split_values

            # special non match[...] filter case which still needs coercion
            elif arg_name == "added_after":
                for split_value in split_values:
                    coerced_values.append(
                        medallion.common.timestamp_to_epoch_seconds(split_value)
                    )

            else:
                # Unrecognized non-match[...] filter; use values as-is
                coerced_values = split_values

        except ValueError as e:
            # Catch type coercion errors.  TypeErrors shouldn't happen here I
            # think, since the coercer functions must support conversion from
            # strings, and we are converting from strings here (since the
            # values are coming from a URL).  So if they do, that's a server
            # error (500).
            raise ProcessingError((
                    "Invalid query value for filter '{}': {}"
                ).format(
                    arg_name, split_value
                ), 400
            ) from e

        coerced_filter_args[arg_name] = coerced_values

    return coerced_filter_args


def _mongo_query_from_match_spec(match_spec, coerced_filter_values):
    """
    Given some query parameter values and a spec from the above set of specs,
    create an actual mongo query.

    :param match_spec: A match spec from _MONGO_MATCH_SPECS (the value of a
        top-level key)
    :param coerced_filter_values: List of parameter values, already coerced to
        proper types
    :return: A mongo query, as a dict
    """

    # Empty match spec is malformed
    assert len(match_spec) > 0

    # Top level is an "or", e.g. over STIX types, or property checks not
    # specific to STIX types.
    top_or = []

    for stix_type, query_paths in match_spec.items():

        # If no paths, this is a malformed spec
        assert len(query_paths) > 0

        # path_or contains tests for all places in an object type where a
        # particular property is known to be.
        if len(coerced_filter_values) == 1:
            path_or = [
                {query_path: coerced_filter_values[0]}
                for query_path in query_paths
            ]
        else:
            path_or = [
                {query_path: {"$in": coerced_filter_values}}
                for query_path in query_paths
            ]

        if stix_type:
            # We have a type; combine our above path "or" into an "and"
            # with a STIX type check.
            type_and = {
                "type": stix_type
            }

            # optimize away a length-one "or"
            if len(path_or) == 1:
                type_and.update(path_or[0])
            else:
                type_and["$or"] = path_or

            top_or.append(type_and)

        else:
            # No type check required, thus no "and" is required.  This would
            # result in an "or" inside another "or", which can be optimized:
            # merge the child into the parent.
            top_or.extend(path_or)

    # Another optimization: don't need an "$or" with only one disjunct in it.
    if len(top_or) == 1:
        query = top_or[0]
    else:
        query = {"$or": top_or}

    return query


def _mongo_query_from_filter(filter_name, coerced_filter_values, interop):
    """
    Create a mongo query corresponding to the given TAXII query parameter name
    and corresponding coerced values.  match[version] and match[spec_version]
    are not handled here.  They and any unrecognized filters will be ignored.

    :param filter_name: A TAXII query parameter name
    :param coerced_filter_values: A list of coerced parameter values
    :param interop: Whether to recognize interop filters.  If True, many more
        types of TAXII filters are recognized.
    :return: A mongo query as a dict, or None if the function doesn't recognize
        or handle the given query
    """

    query = None

    if filter_name.startswith("match[") and filter_name.endswith("]"):

        filter_name = filter_name[6:-1]
        match_spec = _MONGO_MATCH_SPECS.get(filter_name)

        if interop:

            if match_spec:
                # Complex case: construct a query from the spec.  This should
                # cover all tier 3 filters at least.
                query = _mongo_query_from_match_spec(
                    match_spec, coerced_filter_values
                )

            elif filter_name in medallion.filters.common.BUILTIN_PROPERTIES \
                    or filter_name in medallion.filters.common.TIER_1_PROPERTIES \
                    or filter_name in medallion.filters.common.TIER_2_PROPERTIES:

                # Can treat tier 1 and 2 filters and some standard filters all
                # the same way
                if len(coerced_filter_values) == 1:
                    query = {
                        filter_name: coerced_filter_values[0]
                    }
                else:
                    query = {
                        filter_name: {"$in": coerced_filter_values}
                    }

            elif filter_name in medallion.filters.common.CALCULATION_PROPERTIES:

                filter_name, op = filter_name.split("-")

                # $gte and $lte are supported mongo operators!
                op = "$" + op

                # Weird, but in case there was more than one value.
                if op == "$gte":
                    value = min(coerced_filter_values)
                else:
                    # op == "$lte", the only other thing it could be,
                    # as of this writing.
                    value = max(coerced_filter_values)

                query = {
                    filter_name: {
                        op: value
                    }
                }

        elif filter_name in medallion.filters.common.BUILTIN_PROPERTIES:
            # interop disabled; consider spec builtin filters only.
            # This is a copy-paste of the builtin/interop tier 1/2 filter code
            # above.  Redundant, but maybe the overall if/then/else logic is
            # simpler this way?
            if len(coerced_filter_values) == 1:
                query = {
                    filter_name: coerced_filter_values[0]
                }
            else:
                query = {
                    filter_name: {"$in": coerced_filter_values}
                }

        # else: a match[...] filter we don't recognize.  Ignore it.

    elif filter_name == "added_after":

        # Just in case there are multiple added_after values... but there
        # shouldn't be.
        min_added_after = min(coerced_filter_values)

        query = {
            "_manifest.date_added": {
                "$gt": min_added_after
            }
        }

    # else: a non match[...] filter we don't recognize.  Ignore it.

    return query


def _make_mongo_query(coerced_filter_args, interop):
    """
    Make a mongo query for TAXII query parameters which can be handled with one
    single query (no additional pipeline stages required).  The version query
    is not handled here since its "first"/"last" query values require a
    different kind of treatment.  spec_version with specific version values
    could be handled, but is not, to keep mongo backend behavior the same as
    the memory backend (it is handled in a later stage).  Latest spec_version
    (i.e. the implicit behavior when no spec_version filter is given) can't be
    handled here.

    :param coerced_filter_args: A mapping from query parameter names to
        coerced values.
    :param interop: Whether to recognize TAXII interop filters when
        constructing the query.
    :return: A mongo query, as a dict
    """

    sub_queries = []
    for arg_name, arg_values in coerced_filter_args.items():
        sub_query = _mongo_query_from_filter(arg_name, arg_values, interop)

        if sub_query:
            sub_queries.append(sub_query)

    if sub_queries:
        if len(sub_queries) == 1:
            query = sub_queries[0]
        else:
            query = {
                "$and": sub_queries
            }
    else:
        # We recognized... nothing!
        query = {}

    return query


def _make_version_pipeline_stages(versions):
    """
    Create a list of pipeline stages which performs the requested version
    filtering.

    :param versions: Iterable of coerced version values.  These can include
        floats and the strings "first", "last", "all".
    :return: A mongo pipeline as a list; will be an empty list if "all" is
        a query value
    """

    pipeline = []

    # If "all" is included, no filtering is necessary at all.
    if "all" not in versions:

        need_first = "first" in versions
        need_last = "last" in versions

        # If "first" or "last" is included, we need to add temp window fields.
        # Track what fields we add, so we can remove them again.
        fields_to_remove = []
        if need_first or need_last:

            window_output = {}

            if need_first:
                window_output["_min_version"] = {
                    "$min": "$_manifest.version"
                }
                fields_to_remove.append("_min_version")

            if need_last:
                window_output["_max_version"] = {
                    "$max": "$_manifest.version"
                }
                fields_to_remove.append("_max_version")

            window_stage = {
                "$setWindowFields": {
                    "partitionBy": "$id",
                    "output": window_output
                }
            }

            pipeline.append(window_stage)

        # Build a "$match" stage which filters documents based on the query
        # parameters and fields present.
        version_checks = []

        explicit_versions = [
            ver for ver in versions if not isinstance(ver, str)
        ]

        if explicit_versions:
            if len(explicit_versions) == 1:
                version_checks.append({
                    "_manifest.version": explicit_versions[0]
                })
            else:
                version_checks.append({
                    "_manifest.version": {
                        "$in": explicit_versions
                    }
                })

        if need_first:
            version_checks.append({
                "$expr": {
                    "$eq": [
                        "$_manifest.version",
                        "$_min_version"
                    ]
                }
            })

        if need_last:
            version_checks.append({
                "$expr": {
                    "$eq": [
                        "$_manifest.version",
                        "$_max_version"
                    ]
                }
            })

        if len(version_checks) == 1:
            version_match = {
                "$match": version_checks[0]
            }
        else:
            version_match = {
                "$match": {
                    "$or": version_checks
                }
            }

        pipeline.append(version_match)

        # remove the extra window fields
        if fields_to_remove:
            pipeline.append({
                "$unset": fields_to_remove
            })

    return pipeline


def _make_spec_version_pipeline_stages(spec_versions=None):
    """
    Create a list of pipeline stages which performs the requested spec_version
    filtering.

    :param spec_versions: Sequence of spec version values, or None.  Sequences
        must be of spec versions as strings, e.g. "2.0", "2.1", etc.  If None,
        construct the pipeline to include only the latest spec versions.
    :return: A mongo pipeline as a list
    """

    if spec_versions:
        # Match specific spec version(s)
        if len(spec_versions) == 1:
            match = {
                "_manifest.media_type": "application/stix+json;version="
                                        + spec_versions[0]
            }

        else:
            media_types = [
                "application/stix+json;version=" + spec_version
                for spec_version in spec_versions
            ]
            match = {
                "_manifest.media_type": {
                    "$in": media_types
                }
            }

        pipeline = [
            {
                "$match": match
            }
        ]

    else:
        # Match latest spec version
        pipeline = [
            {
                "$setWindowFields": {
                    "partitionBy": "$id",
                    "output": {
                        "_max_spec_version": {
                            # This is a string comparison-based maximum.  It
                            # will fail if/when the STIX version reaches 2.10
                            # (since as strings, "2.10" < "2.2").  We will need
                            # to do some redesigning at that point...
                            "$max": "$_manifest.media_type"
                        }
                    }
                }
            },
            {
                "$match": {
                    "$expr": {
                        "$eq": [
                            "$_manifest.media_type",
                            "$_max_spec_version"
                        ]
                    }
                }
            },
            {
                "$unset": "_max_spec_version"
            }
        ]

    return pipeline


def _make_base_mongo_pipeline(basic_filter, filter_args, interop):
    """
    Construct the base Mongo aggregation pipeline, which performs the given
    filtering.

    :param basic_filter: Extra filters to be merged into the initial $match
        stage of the pipeline.
    :param filter_args: TAXII filters, as a mapping taken from the query
        parameters of an HTTP request
    :param interop: Whether to recognize and apply TAXII interop filters
    :return: A Mongo aggregation pipeline, as a list of stages
    """

    coerced_filter_args = _coerce_filter_args(filter_args)

    base_match = _make_mongo_query(coerced_filter_args, interop)
    # this merger results in an implicit "and" between basic_filter and
    # base_match.
    base_match.update(basic_filter)

    pipeline = [
        {"$match": base_match}
    ]

    version_filters = coerced_filter_args.get("match[version]")
    if not version_filters:
        version_filters = ["last"]

    pipeline.extend(
        _make_version_pipeline_stages(version_filters)
    )

    pipeline.extend(
        _make_spec_version_pipeline_stages(
            coerced_filter_args.get("match[spec_version]")
        )
    )

    pipeline.append({
        "$sort": SON([
            ("_manifest.date_added", ASCENDING),
            ("created", ASCENDING),
            ("modified", ASCENDING)
        ])
    })

    return pipeline


class MongoDBFilter:

    def __init__(self, filter_args, basic_filter, record=None, interop=False):
        self.record = record
        self.base_pipeline = _make_base_mongo_pipeline(
            basic_filter, filter_args, interop
        )

    def process_filter(self, data, manifest_info):

        pipeline = self.base_pipeline.copy()

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