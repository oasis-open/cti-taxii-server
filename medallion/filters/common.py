"""
Some informational and convenience APIs for filters.
"""
import collections
import enum

import medallion.common

# A type which collects common info about a TAXII filter.
TaxiiFilterInfo = collections.namedtuple(
    "TaxiiFilterInfo", [
        # One of the StixType enum values.  Should reflect the STIX-defined
        # semantics of the property being filtered.  I thought it might be
        # useful in case someone wanted to make decisions based on the property
        # type, beyond doing type coercion.
        "stix_type",

        # This must be a function of one argument, which returns a value likely
        # to be usable in the context of the aforementioned type.  So, no
        # one-size-fits-all here, but the defaults chosen in this module should
        # hopefully be reasonable.  Backend implementations can treat decisions
        # in this module as defaults, and override them.
        #
        # It must at minimum be capable of converting from a string (useful
        # for converting values from URL query parameters), and should also be
        # idempotent (passing through a value if its type is already correct).
        "type_coercer"
    ]
)


class StixType(enum.Enum):
    """
    STIX types, used as the value of the stix_type attribute of the namedtuple
    above.
    """

    BOOLEAN = enum.auto()
    INTEGER = enum.auto()
    STRING = enum.auto()
    TIMESTAMP = enum.auto()


_TLP_SHORT_NAME_MAP = {
    "white": "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",
    "green": "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
    "amber": "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82",
    "red": "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed"
}


def tlp_short_name_to_id(tlp_short_name):
    """
    Utility for the TAXII interop tier 3 "tlp" filter.  That filter uses the
    short names "white", "green", etc instead of marking definition IDs.  This
    function resolves a TLP short name as used in that filter, to a marking
    definition ID.

    Raises TypeError/ValueError on type or value errors, to act similarly to
    type coercers, rather than returning null (I'm imagining this function
    could be used that way).  Passes through valid TLP marking definition IDs,
    for the sake of idempotence.

    :param tlp_short_name: A TLP "short name"
    :raises ValueError: if tlp_short_name is not a recognized TLP short name
    :raises TypeError: if tlp_short_name is not a string
    """

    if not isinstance(tlp_short_name, str):
        raise TypeError(
            "TLP marking short name must be a string: " + str(tlp_short_name)
        )

    # For idempotence
    if tlp_short_name in _TLP_SHORT_NAME_MAP.values():
        marking_id = tlp_short_name

    else:
        marking_id = _TLP_SHORT_NAME_MAP.get(tlp_short_name)

        if not marking_id:
            raise ValueError(
                "Unrecognized TLP marking short name: " + tlp_short_name
            )

    return marking_id


def bool_coerce(value):
    """
    A coercer function to bool, which treats "false" as False.  That's how
    the STIX/TAXII boolean values are defined.  In Python, bool("false") is
    True, so we require something slightly more complex.

    :param value: The value to coerce to a bool
    :return: True or False
    """

    result = bool(value) and value != "false"

    return result


# Some default sets of settings for the various STIX types.
# The type coercion functions may not be suitable for everyone, but these are
# some reasonable defaults, hopefully.
TAXII_STRING_FILTER = TaxiiFilterInfo(StixType.STRING, str)
TAXII_INTEGER_FILTER = TaxiiFilterInfo(StixType.INTEGER, int)
TAXII_BOOLEAN_FILTER = TaxiiFilterInfo(StixType.BOOLEAN, bool_coerce)
TAXII_TIMESTAMP_FILTER = TaxiiFilterInfo(
    StixType.TIMESTAMP, medallion.common.timestamp_to_datetime
)
# Does not actually do a type coercion, but I think it has a useful default
# effect: convert the short name used in the TAXII interop tlp filter to a
# value to be used in a query (a marking definition ID).
TAXII_TLP_SHORT_NAME_FILTER = TaxiiFilterInfo(
    StixType.STRING, tlp_short_name_to_id
)


BUILTIN_PROPERTIES = {
    "id": TAXII_STRING_FILTER,
    "type": TAXII_STRING_FILTER,

    # skipping version, spec_version, added_after, as special cases
}


TIER_1_PROPERTIES = {
    "account_type": TAXII_STRING_FILTER,
    "confidence": TAXII_INTEGER_FILTER,
    "context": TAXII_STRING_FILTER,
    "data_type": TAXII_STRING_FILTER,
    "dst_port": TAXII_INTEGER_FILTER,
    "encryption_algorithm": TAXII_STRING_FILTER,
    "identity_class": TAXII_STRING_FILTER,
    "name": TAXII_STRING_FILTER,
    "number": TAXII_INTEGER_FILTER,
    "opinion": TAXII_STRING_FILTER,
    "pattern": TAXII_STRING_FILTER,
    "pattern_type": TAXII_STRING_FILTER,
    "primary_motivation": TAXII_STRING_FILTER,
    "region": TAXII_STRING_FILTER,
    "relationship_type": TAXII_STRING_FILTER,
    "resource_level": TAXII_STRING_FILTER,
    "result": TAXII_STRING_FILTER,
    "revoked": TAXII_BOOLEAN_FILTER,
    "src_port": TAXII_INTEGER_FILTER,
    "sophistication": TAXII_STRING_FILTER,
    "subject": TAXII_STRING_FILTER,
    "value": TAXII_STRING_FILTER
}


TIER_2_PROPERTIES = {
    "aliases": TAXII_STRING_FILTER,
    "architecture_execution_envs": TAXII_STRING_FILTER,
    "capabilities": TAXII_STRING_FILTER,
    "extension_types": TAXII_STRING_FILTER,
    "implementation_languages": TAXII_STRING_FILTER,
    "indicator_types": TAXII_STRING_FILTER,
    "infrastructure_types": TAXII_STRING_FILTER,
    "labels": TAXII_STRING_FILTER,
    "malware_types": TAXII_STRING_FILTER,
    "personal_motivations": TAXII_STRING_FILTER,
    "report_types": TAXII_STRING_FILTER,
    "roles": TAXII_STRING_FILTER,
    "secondary_motivations": TAXII_STRING_FILTER,
    "sectors": TAXII_STRING_FILTER,
    "threat_actor_types": TAXII_STRING_FILTER,
    "tool_types": TAXII_STRING_FILTER
}


TIER_3_PROPERTIES = {
    "address_family": TAXII_STRING_FILTER,
    "external_id": TAXII_STRING_FILTER,
    "MD5": TAXII_STRING_FILTER,
    "SHA-1": TAXII_STRING_FILTER,
    "SHA-256": TAXII_STRING_FILTER,
    "SHA-512": TAXII_STRING_FILTER,
    "SHA3-256": TAXII_STRING_FILTER,
    "SHA3-512": TAXII_STRING_FILTER,
    "SSDEEP": TAXII_STRING_FILTER,
    "TLSH": TAXII_STRING_FILTER,
    "integrity_level": TAXII_STRING_FILTER,
    "pe_type": TAXII_STRING_FILTER,
    "phase_name": TAXII_STRING_FILTER,
    "service_status": TAXII_STRING_FILTER,
    "service_type": TAXII_STRING_FILTER,
    "socket_type": TAXII_STRING_FILTER,
    "source_name": TAXII_STRING_FILTER,
    "start_type": TAXII_STRING_FILTER,
    "tlp": TAXII_TLP_SHORT_NAME_FILTER
}


RELATIONSHIP_PROPERTIES = {
    "relationships-all": TAXII_STRING_FILTER
}


CALCULATION_PROPERTIES = {
    "confidence-gte": TAXII_INTEGER_FILTER,
    "confidence-lte": TAXII_INTEGER_FILTER,
    "modified-gte": TAXII_TIMESTAMP_FILTER,
    "modified-lte": TAXII_TIMESTAMP_FILTER,
    "number-gte": TAXII_INTEGER_FILTER,
    "number-lte": TAXII_INTEGER_FILTER,
    "src_port-gte": TAXII_INTEGER_FILTER,
    "src_port-lte": TAXII_INTEGER_FILTER,
    "dst_port-gte": TAXII_INTEGER_FILTER,
    "dst_port-lte": TAXII_INTEGER_FILTER,
    "valid_until-gte": TAXII_TIMESTAMP_FILTER,
    "valid_from-lte": TAXII_TIMESTAMP_FILTER
}


def get_filter_info(filter_name):
    """
    Given a match filter name (the part inside square brackets in a
    "match[...]" TAXII query parameter), find a TaxiiFilterInfo object for
    the filter.  The object gives some helpful info about the filter.

    :param filter_name: A match filter name (without surrounding "match[...]")
    :return: A TaxiiFilterInfo object, or None if nothing is known about the
        filter
    """
    return BUILTIN_PROPERTIES.get(filter_name) \
        or TIER_1_PROPERTIES.get(filter_name) \
        or TIER_2_PROPERTIES.get(filter_name) \
        or TIER_3_PROPERTIES.get(filter_name) \
        or CALCULATION_PROPERTIES.get(filter_name) \
        or RELATIONSHIP_PROPERTIES.get(filter_name)