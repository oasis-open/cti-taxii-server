import json
import operator
import tempfile

import pytest

from medallion import exceptions
import medallion.backends.memory_backend
import medallion.common
import medallion.filters.common
import medallion.filters.memory_filter


def test_memory_backend_malformed_datafile():

    content = {
        "/discovery": {},
        "apiroot": {
            "collections": {
                "00000000-0000-0000-0000-000000000000": {
                    "objects": [
                        {
                            "id": "foo",
                            "__meta": {}
                        }
                    ]
                }
            }
        }
    }

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as fp:
        json.dump(content, fp)

        # Exercise the error about missing date_added in object meta
        fp.seek(0)
        with pytest.raises(exceptions.MemoryBackendError):
            medallion.backends.memory_backend.MemoryBackend(
                filename=fp
            )

        # Add date_added; try now to exercise the error about missing
        # media_type.
        content["apiroot"]["collections"]["00000000-0000-0000-0000-000000000000"]["objects"][0]["__meta"]["date_added"] = "tomorrow"
        fp.seek(0)
        json.dump(content, fp)
        fp.truncate()

        fp.seek(0)
        with pytest.raises(exceptions.MemoryBackendError):
            medallion.backends.memory_backend.MemoryBackend(
                filename=fp
            )


def test_meta_repr():
    meta = medallion.backends.memory_backend.Meta(
        "1952-06-14T11:28:21.123456Z",
        "application/stix+json;version=2.1",
        "2006-11-28T07:01:52.654321Z"
    )

    assert repr(meta) == 'Meta("1952-06-14T11:28:21.123456Z", "application/stix+json;version=2.1", "2006-11-28T07:01:52.654321Z")'


def test_toplevel_property_matcher():
    matcher = medallion.filters.memory_filter.TopLevelPropertyMatcher(
        "type", filter_info=medallion.filters.common.TAXII_STRING_FILTER
    )

    obj = {
        "type": "foo"
    }

    assert matcher.match(obj, {"foo"})
    assert matcher.match(obj, {"foo", "bar"})
    assert matcher.match(obj, ["foo", "bar"])
    assert not matcher.match(obj, {"bar"})

    del obj["type"]

    assert not matcher.match(obj, {"foo"})


def test_toplevel_property_matcher_list():
    matcher = medallion.filters.memory_filter.TopLevelPropertyMatcher(
        "names", filter_info=medallion.filters.common.TAXII_STRING_FILTER
    )

    obj = {
        "names": ["alice", "bob"]
    }

    assert matcher.match(obj, {"alice"})
    assert matcher.match(obj, {"alice", "carol"})
    assert not matcher.match(obj, {"carol"})


def test_toplevel_property_matcher_coerce():
    matcher = medallion.filters.memory_filter.TopLevelPropertyMatcher(
        "confidence", filter_info=medallion.filters.common.TAXII_INTEGER_FILTER
    )

    obj = {
        "confidence": "01"
    }

    match_values = matcher.coerce_values(["04"])
    assert match_values == {4}

    assert matcher.match(obj, {1})
    assert matcher.match(obj, {1, 2})
    assert not matcher.match(obj, {2})


def test_toplevel_property_matcher_type_mismatch():
    matcher = medallion.filters.memory_filter.TopLevelPropertyMatcher(
        "confidence", filter_info=medallion.filters.common.TAXII_INTEGER_FILTER
    )

    obj = {
        "confidence": "foo"
    }

    assert not matcher.match(obj, {1})

    obj = {
        "confidence": ["foo", "bar"]
    }

    assert not matcher.match(obj, {1})


def test_sub_property_matcher():
    matcher = medallion.filters.memory_filter.SubPropertyMatcher(
        "foo", filter_info=medallion.filters.common.TAXII_INTEGER_FILTER
    )

    assert not matcher.match({
        "foo": "04"
    }, {4})
    assert matcher.match({
        "bar": {
            "foo": "04"
        }
    }, {4, 8})
    assert matcher.match({
        "bar": {
            "baz": {
                "foo": "04"
            }
        }
    }, {4, 8})
    assert matcher.match({
        "bar": {
            "foo": "99",
            "baz": {
                "foo": "04"
            }
        }
    }, {4, 8})
    assert not matcher.match({
        "bar": {
            "foo": "04"
        }
    }, {2})
    assert not matcher.match({
        "bar": {
            "foo": ["04"]
        }
    }, {4})
    assert matcher.match({
        "bar": [
            {
                "foo": "04"
            },
            {
                "foo": "99"
            }
        ]
    }, {5, 4})
    assert not matcher.match({
        "__meta": {
            "foo": 4
        }
    }, {4})
    assert not matcher.match({
        "bar": {
            "foo": "not_an_int"
        }
    }, {1})


def test_tlp_matcher():

    matcher = medallion.filters.memory_filter.TLPMatcher()

    white = medallion.filters.common.tlp_short_name_to_id("white")
    green = medallion.filters.common.tlp_short_name_to_id("green")
    amber = medallion.filters.common.tlp_short_name_to_id("amber")
    red = medallion.filters.common.tlp_short_name_to_id("red")

    obj = {
        "object_marking_refs": [green],
        "granular_markings": [
            {
                "marking_ref": red,
                "selectors": []
            }
        ]
    }

    assert matcher.match(obj, {green})
    assert matcher.match(obj, {red})
    assert matcher.match(obj, {red, white})
    assert not matcher.match(obj, {amber})
    assert not matcher.match(obj, {"foo"})
    assert not matcher.match(obj, {amber, "foo"})


def test_ref_property_matcher():

    matcher = medallion.filters.memory_filter.RelationshipsAllMatcher()

    obj = {
        "prop": [
            {
                "foo_ref": "a--1"
            },
            {
                "foo_ref": "b--2"
            }
        ]
    }

    assert matcher.match(obj, {"a--1"})
    assert matcher.match(obj, {"b--2"})
    assert matcher.match(obj, {"a--1", "c--3"})
    assert not matcher.match(obj, {"c--3"})
    assert not matcher.match(obj, {"c--3", "d--4"})


def test_refs_property_matcher():

    matcher = medallion.filters.memory_filter.RelationshipsAllMatcher()

    obj = {
        "prop": [
            {
                "foo_refs": ["a--1", "b--2"]
            },
            {
                "foo_refs": ["c--3", "d--4"]
            }
        ]
    }

    assert matcher.match(obj, {"a--1"})
    assert matcher.match(obj, {"b--2"})
    assert matcher.match(obj, {"c--3"})
    assert matcher.match(obj, {"d--4", "f--6"})
    assert not matcher.match(obj, {"f--6", "g--7"})


def test_calculation_matcher():

    matcher = medallion.filters.memory_filter.CalculationMatcher(
        "foo", operator.gt,
        filter_info=medallion.filters.common.TAXII_INTEGER_FILTER
    )

    obj = {
        "foo": "05",
        "bar": {
            "foo": "007"
        },
        "__meta": {
            "foo": 8
        }
    }

    assert matcher.match(obj, {3})
    assert matcher.match(obj, {3, 6})
    assert matcher.match(obj, {6})
    assert not matcher.match(obj, {7})

    obj = {
        "foo": "not_an_int"
    }

    assert not matcher.match(obj, {3})


def test_added_after_matcher():
    matcher = medallion.filters.memory_filter.AddedAfterMatcher()

    obj = {
        "someprop": "somevalue",
        "__meta": {
            "date_added": "1991-02-09T08:28:23.474Z",
            "media_type": "application/stix+json;version=2.1"
        }
    }

    medallion.backends.memory_backend._metafy_object(obj)

    assert matcher.match(obj, {
        medallion.common.string_to_datetime("1981-08-01T05:14:03.489Z")
    })
    assert not matcher.match(obj, {
        medallion.common.string_to_datetime("1992-02-01T20:05:17.485Z")
    })


def test_spec_version_matcher():
    # Three spec versions of the same object (as identified by ID),
    # and one different object.
    objs = [
        {
            "id": "id--1",
            "modified": "1976-03-02T11:21:56.624Z",
            "__meta": {
                "date_added": "1987-05-27T16:37:09.111Z",
                "media_type": "application/stix+json;version=2.0"
            }
        },
        {
            "id": "id--1",
            "modified": "1979-08-09T14:57:29.634Z",
            "__meta": {
                "date_added": "1995-09-15T17:57:40.692Z",
                "media_type": "application/stix+json;version=2.2"
            }
        },
        {
            "id": "id--1",
            "modified": "1989-11-15T16:13:20.523Z",
            "__meta": {
                "date_added": "1996-01-17T14:09:36.932Z",
                "media_type": "application/stix+json;version=2.10"
            }
        },
        {
            "id": "id--2",
            "modified": "1999-07-14T22:52:47.345Z",
            "__meta": {
                "date_added": "2000-03-24T20:40:05.295Z",
                "media_type": "application/stix+json;version=4.2"
            }
        }
    ]

    for obj in objs:
        medallion.backends.memory_backend._metafy_object(obj)

    spec_matcher = medallion.filters.memory_filter.SpecVersionMatcher(objs)

    assert spec_matcher.match(objs[0], ["2.0"])
    assert spec_matcher.match(objs[0], ["2.0", "88.88"])
    assert not spec_matcher.match(objs[0], ["2.2", "12.34"])
    assert spec_matcher.match(objs[3], ["4.2"])

    assert spec_matcher.match(objs[2], None)
    assert spec_matcher.match(objs[3], None)
    assert not spec_matcher.match(objs[1], None)


def test_version_matcher():
    # Three versions of the same object (as identified by ID),
    # and one different object.
    objs = [
        {
            "id": "id--1",
            "modified": "1977-01-16T06:59:55.589Z",
            "__meta": {
                "date_added": "1996-01-17T14:09:36.932Z",
                "media_type": "application/stix+json;version=2.0"
            }
        },
        {
            "id": "id--1",
            "modified": "1991-05-31T06:22:51.473Z",
            "__meta": {
                "date_added": "1995-09-15T17:57:40.692Z",
                "media_type": "application/stix+json;version=2.2"
            }
        },
        {
            "id": "id--1",
            "modified": "1996-08-06T03:08:59.121Z",
            "__meta": {
                "date_added": "1987-05-27T16:37:09.111Z",
                "media_type": "application/stix+json;version=2.10"
            }
        },
        {
            "id": "id--2",
            "modified": "1999-07-14T22:52:47.345Z",
            "__meta": {
                "date_added": "2000-03-24T20:40:05.295Z",
                "media_type": "application/stix+json;version=2.2"
            }
        }
    ]

    for obj in objs:
        medallion.backends.memory_backend._metafy_object(obj)

    version_matcher = medallion.filters.memory_filter.VersionMatcher(objs)

    assert version_matcher.match(
        objs[0], [
            medallion.common.string_to_datetime("1977-01-16T06:59:55.589Z")
        ]
    )
    assert version_matcher.match(
        objs[0], [
            medallion.common.string_to_datetime("1977-01-16T06:59:55.589Z"),
            medallion.common.string_to_datetime("1975-06-14T10:13:53.619Z")
        ]
    )
    assert not version_matcher.match(
        objs[0], [
            medallion.common.string_to_datetime("1999-02-10T14:01:40.234Z"),
            medallion.common.string_to_datetime("1975-06-14T10:13:53.619Z")
        ]
    )
    assert version_matcher.match(
        objs[3], [
            medallion.common.string_to_datetime("1999-07-14T22:52:47.345Z"),
        ]
    )

    assert version_matcher.match(objs[0], ["first"])
    assert version_matcher.match(objs[0], ["first", "last"])
    assert not version_matcher.match(objs[1], ["first", "last"])
    assert version_matcher.match(objs[2], ["first", "last"])
    assert version_matcher.match(objs[0], ["all"])
    assert not version_matcher.match(objs[0], ["last"])
    assert version_matcher.match(objs[2], ["last"])

    assert version_matcher.match(objs[2], None)
    assert version_matcher.match(objs[3], None)
    assert not version_matcher.match(objs[1], None)


def test_interop_tier1_filter():
    data = [
        {
            "id": "aaaaa--f513d13a-383d-49e7-88c2-da80941a86e9",
            "created": "1994-02-17T16:10:59.672Z",
            "spec_version": "2.1",
            "confidence": 10,
            "__meta": {
                "media_type": "application/stix+json;version=2.1",
                "date_added": "1992-02-23T23:33:31.342Z"
            }
        },
        {
            "id": "bbbbb--be960f96-4a5f-4943-926e-5d0c9c8c7a10",
            "created": "1978-01-02T06:57:16.129Z",
            "__meta": {
                "media_type": "application/stix+json;version=2.1",
                "date_added": "1993-05-27T23:00:44.323Z"
            }
        }
    ]

    for obj in data:
        medallion.backends.memory_backend._metafy_object(obj)

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[confidence]": "10"
        },
        interop=True
    )

    results, _, _ = filter.process_filter(data)

    assert results == [data[0]]

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[confidence]": "10,20,30"
        },
        interop=True
    )

    results, _, _ = filter.process_filter(data)

    assert results == [data[0]]

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[confidence]": "20"
        },
        interop=True
    )

    results, _, _ = filter.process_filter(data)

    assert not results

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[confidence]": "foo"
        },
        interop=True
    )
    with pytest.raises(exceptions.ProcessingError) as e:
        filter.process_filter(data)

    assert e.value.status == 400

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[confidence]": "10"
        },
        interop=False
    )

    results, _, _ = filter.process_filter(data)

    assert all(obj in results for obj in data)
    assert len(results) == len(data)


def test_interop_tier2_filter():
    data = [
        {
            "id": "aaaaa--f513d13a-383d-49e7-88c2-da80941a86e9",
            "created": "1994-02-17T16:10:59.672Z",
            "spec_version": "2.1",
            "labels": ["A", "B", "C"],
            "__meta": {
                "media_type": "application/stix+json;version=2.1",
                "date_added": "1992-02-23T23:33:31.342Z"
            }
        },
        {
            "id": "bbbbb--be960f96-4a5f-4943-926e-5d0c9c8c7a10",
            "created": "1978-01-02T06:57:16.129Z",
            "labels": ["B", "C", "D"],
            "__meta": {
                "media_type": "application/stix+json;version=2.0",
                "date_added": "1993-05-27T23:00:44.323Z"
            }
        },
        {
            "id": "ccccc--13374fca-c972-4503-a287-7eaeac21a004",
            "created": "1990-12-06T18:10:47.496Z",
            "__meta": {
                "media_type": "application/stix+json;version=2.0",
                "date_added": "1993-05-27T23:00:44.323Z"
            }
        }
    ]

    for obj in data:
        medallion.backends.memory_backend._metafy_object(obj)

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[labels]": "B"
        },
        interop=True
    )

    results, _, _ = filter.process_filter(data)

    assert len(results) == 2
    assert data[0] in results
    assert data[1] in results

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[labels]": "X,B,foo"
        },
        interop=True
    )

    results, _, _ = filter.process_filter(data)

    assert len(results) == 2
    assert data[0] in results
    assert data[1] in results

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[labels]": "Z"
        },
        interop=True
    )

    results, _, _ = filter.process_filter(data)

    assert not results

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[labels]": "B"
        },
        interop=False
    )

    results, _, _ = filter.process_filter(data)

    assert all(obj in results for obj in data)
    assert len(results) == len(data)


def test_interop_tier3_filter():
    data = [
        {
            "id": "aaaaa--d6b0ab07-8fbe-4503-8943-97417c601cdc",
            "foo": {
                "address_family": "A"
            },
            "__meta": {
                "media_type": "application/stix+json;version=2.1",
                "date_added": "1980-09-17T07:18:19.141Z"
            }
        },
        {
            "id": "bbbbb--436af759-54fa-4cb4-8395-b0286216e8b6",
            "foo": [
                {
                    "address_family": "A"
                }
            ],
            "__meta": {
                "media_type": "application/stix+json;version=2.1",
                "date_added": "1979-06-23T07:03:24.893Z"
            }
        },
        {
            "id": "ccccc--38fb2092-23b5-471f-a7c9-5715b995ad85",
            "address_family": "A",
            "__meta": {
                "media_type": "application/stix+json;version=2.1",
                "date_added": "1997-12-12T11:29:41.196Z"
            }
        },
        {
            "id": "ddddd--70f0802e-a73f-4b62-829d-6bc3dd0e39a7",
            "foo": {
                "address_family": "B"
            },
            "__meta": {
                "media_type": "application/stix+json;version=2.1",
                "date_added": "1991-03-25T09:40:56.942Z"
            }
        }
    ]

    for obj in data:
        medallion.backends.memory_backend._metafy_object(obj)

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[address_family]": "A,X"
        },
        interop=True
    )

    results, _, _ = filter.process_filter(data)
    assert data[0] in results
    assert data[1] in results
    assert data[2] not in results
    assert data[3] not in results

    filter = medallion.filters.memory_filter.MemoryFilter(
        {
            "match[address_family]": "A,X"
        },
        interop=False
    )

    results, _, _ = filter.process_filter(data)

    assert all(obj in results for obj in data)
    assert len(results) == len(data)


def test_filter_order():

    filters = sorted(
        [
            "match[address_family]",
            "match[version]",
            "match[aliases]",
            "match[number]"
        ],
        key=medallion.filters.memory_filter._speed_tier
    )

    correct_order = [
        "match[number]",
        "match[aliases]",
        "match[address_family]",
        "match[version]"
    ]

    assert filters == correct_order


def test_revoked_default():
    obj = {
        "id": "foo--f127ea5c-4e08-47ee-9e29-c4ef0883b394",
        "type": "foo",
        "created": "1988-12-05T21:21:50.423Z"
        # "revoked" defaults to false
    }

    matcher = medallion.filters.memory_filter.TopLevelPropertyMatcher(
        "revoked",
        default_value=False,
        filter_info=medallion.filters.common.TAXII_BOOLEAN_FILTER
    )

    assert matcher.match(obj, {False})
    assert matcher.match(obj, {False, True})
    assert not matcher.match(obj, {True})

    obj_revoked_false = {
        "id": "foo--f127ea5c-4e08-47ee-9e29-c4ef0883b394",
        "type": "foo",
        "created": "1988-12-05T21:21:50.423Z",
        "revoked": "false"  # will coerce to False
    }

    assert matcher.match(obj_revoked_false, {False})
    assert matcher.match(obj_revoked_false, {False, True})
    assert not matcher.match(obj_revoked_false, {True})

    obj_revoked_true = {
        "id": "foo--f127ea5c-4e08-47ee-9e29-c4ef0883b394",
        "type": "foo",
        "created": "1988-12-05T21:21:50.423Z",
        "revoked": "true"  # will coerce to True
    }

    assert not matcher.match(obj_revoked_true, {False})
    assert matcher.match(obj_revoked_true, {False, True})
    assert matcher.match(obj_revoked_true, {True})


def test_toplevel_property_matcher_list_default():
    obj = {
        "id": "foo--f127ea5c-4e08-47ee-9e29-c4ef0883b394",
        "type": "foo",
        "created": "1988-12-05T21:21:50.423Z"
    }

    # defaulted property is "defaulted"
    matcher = medallion.filters.memory_filter.TopLevelPropertyMatcher(
        "defaulted",
        filter_info=medallion.filters.common.TAXII_INTEGER_FILTER,
        default_value=[1, "2", 3]
    )

    assert matcher.match(
        obj, {2, 4, 6}
    )

    assert not matcher.match(
        obj, {6, 7, 8}
    )

    obj_with_defaulted = {
        "id": "foo--f127ea5c-4e08-47ee-9e29-c4ef0883b394",
        "type": "foo",
        "created": "1988-12-05T21:21:50.423Z",
        "defaulted": [4, "5", 6]
    }

    assert matcher.match(
        obj_with_defaulted, {5, 10, 15}
    )

    assert not matcher.match(
        obj_with_defaulted, {1, 2, 3}
    )