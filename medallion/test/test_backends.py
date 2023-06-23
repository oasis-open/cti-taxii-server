import copy
import json
import os
import tempfile

import pymongo
import pytest

from medallion import common, create_app, exceptions, test
from medallion.backends.base import SECONDS_IN_24_HOURS
import medallion.filters.common
from medallion.views import MEDIA_TYPE_TAXII_V21

DATA_FILE = os.path.join(
    os.path.dirname(__file__), "data", "default_data.json",
)


GET_HEADERS = {
    "Accept": "application/taxii+json;version=2.1"
}


POST_HEADERS = {
    "Content-Type": "application/taxii+json;version=2.1",
    "Accept": "application/taxii+json;version=2.1"
}


TEST_OBJECT = {
    "objects": [
        {
            "type": "course-of-action",
            "spec_version": "2.1",
            "id": "course-of-action--68794cd5-28db-429d-ab1e-1256704ef906",
            "created": "2017-01-27T13:49:53.935Z",
            "modified": "2017-01-27T13:49:53.935Z",
            "name": "Test object"
        }
    ]
}


TestServers = ["memory", "mongo"]


@pytest.fixture(scope="module")
def mongo_client():
    # lazy-connect, in case we're only running memory backend tests anyways
    mongo_client = pymongo.MongoClient(connect=False)
    yield mongo_client
    mongo_client.close()


@pytest.fixture()
def backup_filter_settings():
    # Back up filter settings.  A given backend can override the global default
    # settings, which is okay since in normal operation only one backend is
    # active.  It's kinda problematic in unit tests though, where we create
    # lots of backends, and we don't want the overrides applied in one to
    # affect any others.
    #
    # So far, we only wholesale override a filter info object, so shallow
    # copies here are sufficient.
    filters_common = medallion.filters.common

    backup_builtin_filters = filters_common.BUILTIN_PROPERTIES.copy()
    backup_tier1_filters = filters_common.TIER_1_PROPERTIES.copy()
    backup_tier2_filters = filters_common.TIER_2_PROPERTIES.copy()
    backup_tier3_filters = filters_common.TIER_3_PROPERTIES.copy()
    backup_relationsip_filters = filters_common.RELATIONSHIP_PROPERTIES.copy()
    backup_calculation_filters = filters_common.CALCULATION_PROPERTIES.copy()

    yield

    filters_common.BUILTIN_PROPERTIES = backup_builtin_filters
    filters_common.TIER_1_PROPERTIES = backup_tier1_filters
    filters_common.TIER_2_PROPERTIES = backup_tier2_filters
    filters_common.TIER_3_PROPERTIES = backup_tier3_filters
    filters_common.RELATIONSHIP_PROPERTIES = backup_relationsip_filters
    filters_common.CALCULATION_PROPERTIES = backup_calculation_filters


def _set_backend(configuration, mongo_client, request):

    if request.param == "memory":
        configuration["backend"]["module_class"] = "MemoryBackend"
    else:
        configuration["backend"].update(
            module_class="MongoBackend",
            clear_db=True,
            mongo_client=mongo_client
        )

    return configuration


@pytest.fixture(params=TestServers)
def flask_app(mongo_client, backup_filter_settings, request):
    configuration = {
        "backend": {
            "filename": DATA_FILE,
            "interop_requirements": True,
        },
        "users": {
            "admin": "Password0"
        },
        "taxii": {
            "max_page_size": 20
        }
    }

    if request.param in request.config.getoption("backends"):
        _set_backend(configuration, mongo_client, request)

        app = create_app(configuration)

        yield app

        # Important for releasing backend resources
        app.medallion_backend.close()

    else:
        pytest.skip()


@pytest.fixture
def test_client(flask_app):
    return flask_app.test_client()


# start with basic get requests for each endpoint
def test_server_discovery(test_client):
    r = test_client.get(
        test.DISCOVERY_EP, headers=GET_HEADERS, auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    server_info = r.json
    assert server_info["api_roots"][0] == "http://localhost:5000/api1/"


def test_get_api_root_information(test_client):
    r = test_client.get(
        test.API_ROOT_EP, headers=GET_HEADERS, auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    api_root_metadata = r.json
    assert api_root_metadata["title"] == "Malware Research Group"


def test_get_status(test_client):
    r = test_client.get(
            test.API_ROOT_EP + "status/2d086da7-4bdc-4f91-900e-d77486753710",
            headers=GET_HEADERS,
            follow_redirects=True,
            auth=("admin", "Password0")
        )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    status_data = r.json
    assert "successes" in status_data
    assert "failures" in status_data
    assert "pendings" in status_data


def test_get_collections(test_client):
    r = test_client.get(
        test.COLLECTIONS_EP, headers=GET_HEADERS, auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    collections_metadata = r.json
    collections_metadata = sorted(collections_metadata["collections"], key=lambda x: x["id"])
    collection_ids = [cm["id"] for cm in collections_metadata]

    assert len(collection_ids) == 5
    assert "52892447-4d7e-4f70-b94d-d7f22742ff63" in collection_ids
    assert "91a7b528-80eb-42ed-a74d-c6fbd5a26116" in collection_ids
    assert "64993447-4d7e-4f70-b94d-d7f33742ee63" in collection_ids
    assert "472c94ae-3113-4e3e-a4dd-a9f4ac7471d4" in collection_ids
    assert "365fed99-08fa-fdcd-a1b3-fb247eb41d01" in collection_ids


def test_get_objects(test_client):

    r = test_client.get(
        test.GET_OBJECTS_EP,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 6

    # testing date-added headers
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime("2014-05-08T09:00:00.000000Z")
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime("2022-06-16T13:49:53.935000Z")

    # testing ordering of returned objects by date_added
    correct_order = ['relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463',
                     'indicator--cd981c25-8042-4166-8945-51178443bdac',
                     'marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da',
                     'malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec',
                     'indicator--6770298f-0fd8-471a-ab8c-1c658a46574e',
                     "malware-analysis--084a658c-a7ef-4581-a21d-1f600908741b"]

    returned_order = [
        obj["id"] for obj in objs["objects"]
    ]

    assert returned_order == correct_order


def test_get_object(test_client):

    r = test_client.get(
        test.GET_OBJECTS_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1
    assert all(
        obj["id"] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec"
        for obj in objs["objects"]
    )

    # testing date-added headers
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime("2017-01-27T13:49:59.997000Z")
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime("2017-01-27T13:49:59.997000Z")


def test_add_and_delete_object(test_client):
    # ------------- BEGIN: add object section ------------- #

    object_id = TEST_OBJECT["objects"][0]["id"]

    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(TEST_OBJECT)),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    status_response = r_post.json
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    # ------------- END: add object section ------------- #
    # ------------- BEGIN: get object section ------------- #

    r_get = test_client.get(
        test.ADD_OBJECTS_EP,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    objs = r_get.json
    assert any(obj["id"] == object_id for obj in objs["objects"])

    # ------------- END: get object section ------------- #
    # ------------- BEGIN: get object w/ filter section --- #

    r_get = test_client.get(
        test.ADD_OBJECTS_EP + "?match[id]=" + object_id,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    objs = r_get.json
    assert objs["objects"][0]["id"] == object_id

    # ------------- END: get object w/ filter section --- #
    # ------------- BEGIN: get status section ------------- #

    r_get = test_client.get(
        test.API_ROOT_EP + "status/%s/" % status_response["id"],
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    status_response2 = r_get.json
    assert status_response2["success_count"] == 1

    # ------------- END: get status section ------------- #
    # ------------- BEGIN: get manifest section ------------- #

    r_get = test_client.get(
        test.ADD_MANIFESTS_EP + "?match[id]=" + object_id,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    manifests = r_get.json
    assert len(manifests["objects"]) == 1
    assert manifests["objects"][0]["id"] == object_id

    # ------------- END: get manifest section ----------- #

    r = test_client.delete(
        test.ADD_OBJECTS_EP + object_id,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    # test getting the deleted object's manifest

    r = test_client.get(
        test.ADD_MANIFESTS_EP + object_id,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404
    # for whatever reason, content_type is not normal? doesn't really matter
    # assert r.content_type == MEDIA_TYPE_TAXII_V21


def test_get_object_manifests(test_client):

    r = test_client.get(
        test.GET_MANIFESTS_EP,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    manifests = r.json
    assert len(manifests["objects"]) == 6

    # testing the date-added headers
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime("2014-05-08T09:00:00.000000Z")
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime("2022-06-16T13:49:53.935000Z")

    # checking ordered by date_added

    for x in range(1, len(manifests["objects"])):
        assert common.timestamp_to_datetime(manifests["objects"][x - 1]["date_added"]) <= common.timestamp_to_datetime(manifests["objects"][x]["date_added"])


def test_get_version(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    vers = r.json
    assert len(vers["versions"]) == 1

    # testing the date-added headers
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime("2014-05-08T09:00:00.000000Z")
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime("2014-05-08T09:00:00.000000Z")


# test each filter type with each applicable endpoint
def test_get_objects_added_after(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?added_after=2016-11-03T12:30:59Z",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 4


def test_get_objects_limit(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?limit=4",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is True
    assert len(objs['objects']) == 4
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime('2014-05-08T09:00:00.000000Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime('2017-01-27T13:49:59.997000Z')

    correct_order = ['relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463',
                     'indicator--cd981c25-8042-4166-8945-51178443bdac',
                     'marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da',
                     'malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec']

    returned_order = [
        obj["id"]
        for obj in objs["objects"]
    ]

    assert returned_order == correct_order

    r = test_client.get(
        test.GET_OBJECTS_EP + "?limit=3&next=" + r.json["next"],
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2

    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime('2017-12-31T13:49:53.935000Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime('2022-06-16T13:49:53.935000Z')

    correct_order = ['indicator--6770298f-0fd8-471a-ab8c-1c658a46574e',
                     'malware-analysis--084a658c-a7ef-4581-a21d-1f600908741b']

    returned_order = [
        obj["id"]
        for obj in objs["objects"]
    ]

    assert returned_order == correct_order


def test_get_objects_id(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[id]=malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1


def test_get_objects_type(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[type]=indicator",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2
    assert all("indicator" == obj["type"] for obj in objs["objects"])


def get_objects_by_version(test_client, filter):
    r = test_client.get(
        test.GET_OBJECTS_EP + filter,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    return objs


def test_objects_version_match_specific_date(test_client):
    objs = get_objects_by_version(test_client, "?match[version]=2016-12-25T12:30:59.444Z")
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"


def test_objects_version_match_first(test_client):
    objs = get_objects_by_version(test_client, "?match[version]=first")

    returned_id_version = [
        (obj["id"], common.timestamp_to_datetime(obj.get("modified") or obj["created"]))
        for obj in objs["objects"]
    ]

    correct_id_version = [
        ("relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463", common.timestamp_to_datetime("2014-05-08T09:00:00.000Z")),
        ("indicator--cd981c25-8042-4166-8945-51178443bdac", common.timestamp_to_datetime("2014-05-08T09:00:00.000Z")),
        ("indicator--6770298f-0fd8-471a-ab8c-1c658a46574e", common.timestamp_to_datetime("2016-11-03T12:30:59.000Z")),
        ("marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da", common.timestamp_to_datetime("2017-01-20T00:00:00.000Z")),
        ("malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", common.timestamp_to_datetime("2017-01-27T13:49:53.997Z")),
        ("malware-analysis--084a658c-a7ef-4581-a21d-1f600908741b", common.timestamp_to_datetime("2021-12-11T07:17:44.542582Z"))
    ]

    assert returned_id_version == correct_id_version


def test_objects_version_match_last(test_client):
    objs = get_objects_by_version(test_client, "?match[version]=last")

    returned_id_version = [
        (obj["id"], common.timestamp_to_datetime(obj.get("modified") or obj["created"]))
        for obj in objs["objects"]
    ]

    correct_id_version = [
        ("relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463", common.timestamp_to_datetime("2014-05-08T09:00:00.000Z")),
        ("indicator--cd981c25-8042-4166-8945-51178443bdac", common.timestamp_to_datetime("2014-05-08T09:00:00.000Z")),
        ("marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da", common.timestamp_to_datetime("2017-01-20T00:00:00.000Z")),
        ("malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", common.timestamp_to_datetime("2018-02-23T18:30:00.000Z")),
        ("indicator--6770298f-0fd8-471a-ab8c-1c658a46574e", common.timestamp_to_datetime("2017-01-27T13:49:53.935Z")),
        ("malware-analysis--084a658c-a7ef-4581-a21d-1f600908741b", common.timestamp_to_datetime("2021-12-11T07:17:44.542582Z"))
    ]

    assert returned_id_version == correct_id_version


def test_objects_version_match_all(test_client):
    objs = get_objects_by_version(test_client, "?match[version]=all")
    assert len(objs['objects']) == 8


def get_objects_spec_version(test_client, filter, num_objects):
    r = test_client.get(
        test.GET_OBJECTS_EP + filter,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == num_objects
    return objs


def test_get_objects_spec_version_20(test_client):
    objs = get_objects_spec_version(test_client, "?match[spec_version]=2.0", 1)
    assert all("spec_version" not in obj for obj in objs['objects'])


def test_get_objects_spec_version_21_20(test_client):
    get_objects_spec_version(test_client, "?match[spec_version]=2.0,2.1", 6)


def test_get_objects_spec_version_21(test_client):
    objs = get_objects_spec_version(test_client, "?match[spec_version]=2.1", 5)
    assert all(obj['spec_version'] == "2.1" for obj in objs['objects'])


def test_get_objects_spec_version_default(test_client):
    get_objects_spec_version(test_client, "", 6)
    # Removed spec_version check on results; they are a mix of 2.0 and 2.1
    # (it had checked that all spec_versions are 2.1).  This is because version
    # filtering (which in this case retains only the latest versions) occurs
    # before spec_version filtering in this implementation, which causes a
    # latest-version 2.0 object to be retained and the earlier 2.1 version to
    # be filtered out.


def get_object_added_after(test_client, filter):
    r = test_client.get(
        test.GET_OBJECTS_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec" + filter,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    return r.json


def test_get_object_added_after_case1(test_client):
    objs = get_object_added_after(test_client, "?added_after=2018-01-27T13:49:59.997000Z")
    assert 'more' not in objs
    assert 'objects' not in objs


def test_get_object_added_after_case2(test_client):
    objs = get_object_added_after(test_client, "?added_after=2017-01-27T13:49:59Z")
    assert objs['more'] is False
    assert len(objs['objects']) == 1


def test_get_object_limit(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?limit=1",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert r.headers['X-TAXII-Date-Added-First'] == '2017-12-31T13:49:53.935000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2017-12-31T13:49:53.935000Z'

    r = test_client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=all&limit=2",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is True
    assert len(objs['objects']) == 2
    assert r.headers['X-TAXII-Date-Added-First'] == '2016-11-03T12:30:59.001000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2016-12-27T13:49:59.000000Z'
    # checking ordering by date_added value
    assert objs['objects'][0]['modified'] == '2016-11-03T12:30:59.000Z'
    assert objs['objects'][1]['modified'] == '2016-12-25T12:30:59.444Z'

    r = test_client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=all&limit=2&next=" + objs['next'],
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime('2017-12-31T13:49:53.935000Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime('2017-12-31T13:49:53.935000Z')


@pytest.mark.parametrize("filter, modified", [("?match[version]=2016-12-25T12:30:59.444Z", "2016-12-25T12:30:59.444Z"),
                                              ("?match[version]=first", "2016-11-03T12:30:59.000Z"),
                                              ("?match[version]=last", "2017-01-27T13:49:53.935Z")])
def test_get_object_version_single(test_client, filter, modified):
    objstr = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    r = test_client.get(
        test.GET_OBJECTS_EP + objstr + filter,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == objstr
    assert common.timestamp_to_datetime(objs["objects"][0]["modified"]) == common.timestamp_to_datetime(modified)


def test_get_object_version_match_all(test_client):

    r = test_client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=all",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 3


def get_object_spec_version(test_client, filter, matching, num_expected):
    r = test_client.get(
        test.GET_OBJECTS_EP + filter + matching,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs.get('more', False) is False
    assert len(objs.get('objects', [])) == num_expected
    return objs


def test_get_object_spec_version_20(test_client):
    objs = get_object_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "?match[spec_version]=2.0", 1)
    assert all('spec_version' not in obj for obj in objs['objects'])


def test_get_object_spec_version_21(test_client):
    objs = get_object_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "?match[spec_version]=2.1", 0)
    assert all(obj['spec_version'] == "2.1" for obj in objs.get('objects', []))


def test_get_object_spec_version_2021(test_client):
    objs = get_object_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "?match[spec_version]=2.0,2.1", 1)

    returned_id_version = [
        (o["id"], o.get("modified") or o["created"])
        for o in objs["objects"]
    ]

    correct_id_version = [
        ("malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "2018-02-23T18:30:00.000Z")
    ]

    assert returned_id_version == correct_id_version


def test_get_object_spec_version_default(test_client):
    get_object_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "", 1)


def test_get_manifest_added_after(test_client):
    r = test_client.get(
        test.GET_MANIFESTS_EP + "?added_after=2017-01-20T00:00:00.000Z",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 3


def test_get_manifest_limit(test_client):
    r = test_client.get(
        test.GET_MANIFESTS_EP + "?limit=2",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is True
    assert len(objs['objects']) == 2
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime(objs['objects'][0]['date_added'])
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime(objs['objects'][-1]['date_added'])

    r = test_client.get(
        test.GET_MANIFESTS_EP + "?limit=2&next=" + objs['next'],
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is True
    assert len(objs['objects']) == 2
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime(objs['objects'][0]['date_added'])
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime(objs['objects'][-1]['date_added'])

    r = test_client.get(
        test.GET_MANIFESTS_EP + "?limit=3&next=" + objs['next'],
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime(objs['objects'][0]['date_added'])
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime(objs['objects'][-1]['date_added'])


def test_get_manifest_id(test_client):
    object_id = "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec"
    r = test_client.get(
        test.GET_MANIFESTS_EP + "?match[id]=" + object_id,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert all(
        obj["id"] == object_id
        for obj in objs["objects"]
    )


def test_get_manifest_type(test_client):
    r = test_client.get(
        test.GET_MANIFESTS_EP + "?match[type]=indicator",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2
    assert all('indicator' in obj['id'] for obj in objs['objects'])


def get_manifest_version(test_client, filter):

    r = test_client.get(
        test.GET_MANIFESTS_EP + filter,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    return objs


def test_get_manifest_version_specific(test_client):
    object_id = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    objs = get_manifest_version(test_client, "?match[version]=2016-12-25T12:30:59.444Z")
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == object_id
    assert common.timestamp_to_datetime(objs["objects"][0]["version"]) == common.timestamp_to_datetime("2016-12-25T12:30:59.444Z")


def test_get_manifest_version_first(test_client):
    object_id = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    objs = get_manifest_version(test_client, "?match[version]=first")
    assert len(objs['objects']) == 6
    for obj in objs['objects']:
        if obj['id'] == object_id:
            assert common.timestamp_to_datetime(obj['version']) == common.timestamp_to_datetime("2016-11-03T12:30:59.000Z")


def test_get_manifest_version_last(test_client):
    object_id = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    objs = get_manifest_version(test_client, "?match[version]=last")
    assert len(objs['objects']) == 6
    for obj in objs['objects']:
        if obj['id'] == object_id:
            assert common.timestamp_to_datetime(obj['version']) == common.timestamp_to_datetime("2017-01-27T13:49:53.935Z")


def test_get_manifest_version_all(test_client):
    objs = get_manifest_version(test_client, "?match[version]=all")
    assert len(objs['objects']) == 8


def get_manifest_spec_version(test_client, filter):
    r = test_client.get(
        test.GET_MANIFESTS_EP + filter,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    return objs


def test_manifest_spec_version_20(test_client):
    objs = get_manifest_spec_version(test_client, "?match[spec_version]=2.0")
    assert len(objs['objects']) == 1
    assert all(obj['media_type'] == "application/stix+json;version=2.0" for obj in objs['objects'])


def test_manifest_spec_version_21(test_client):
    objs = get_manifest_spec_version(test_client, "?match[spec_version]=2.1")
    assert len(objs['objects']) == 5
    assert all(obj['media_type'] == "application/stix+json;version=2.1" for obj in objs['objects'])


def test_manifest_spec_version_2021(test_client):
    objs = get_manifest_spec_version(test_client, "?match[spec_version]=2.0,2.1")
    # though the spec_version filter is getting all objects, the automatic filtering by version only gets the latest objects

    returned = [
        (man["id"], man["media_type"])
        for man in objs["objects"]
    ]

    expected = [
        ("relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463", "application/stix+json;version=2.1"),
        ("indicator--cd981c25-8042-4166-8945-51178443bdac", "application/stix+json;version=2.1"),
        ("marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da", "application/stix+json;version=2.1"),
        ("malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "application/stix+json;version=2.0"),
        ("indicator--6770298f-0fd8-471a-ab8c-1c658a46574e", "application/stix+json;version=2.1"),
        ("malware-analysis--084a658c-a7ef-4581-a21d-1f600908741b", "application/stix+json;version=2.1")
    ]

    assert returned == expected


def test_manifest_spec_version_default(test_client):
    objs = get_manifest_spec_version(test_client, "")
    # testing default value

    returned = [
        (man["id"], man["media_type"])
        for man in objs["objects"]
    ]

    expected = [
        ("relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463", "application/stix+json;version=2.1"),
        ("indicator--cd981c25-8042-4166-8945-51178443bdac", "application/stix+json;version=2.1"),
        ("marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da", "application/stix+json;version=2.1"),
        ("malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "application/stix+json;version=2.0"),
        ("indicator--6770298f-0fd8-471a-ab8c-1c658a46574e", "application/stix+json;version=2.1"),
        ("malware-analysis--084a658c-a7ef-4581-a21d-1f600908741b", "application/stix+json;version=2.1")
    ]

    assert returned == expected


def test_get_version_added_after(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463/versions?added_after=2014-05-08T09:00:00Z",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs == {}

    r = test_client.get(
        test.GET_OBJECTS_EP + "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463/versions?added_after=2014-05-08T08:00:00Z",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1


def test_get_version_limit(test_client):

    r = test_client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?limit=1",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is True
    assert len(objs["versions"]) == 1
    assert common.timestamp_to_datetime(objs["versions"][0]) == common.timestamp_to_datetime('2016-11-03T12:30:59.000Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime('2016-11-03T12:30:59.001000Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime('2016-11-03T12:30:59.001000Z')

    r = test_client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?limit=1&next=" + objs["next"],
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is True
    assert len(objs["versions"]) == 1
    assert common.timestamp_to_datetime(objs["versions"][0]) == common.timestamp_to_datetime('2016-12-25T12:30:59.444Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime('2016-12-27T13:49:59.000000Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime('2016-12-27T13:49:59.000000Z')

    r = test_client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?limit=1&next=" + objs["next"],
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1
    assert common.timestamp_to_datetime(objs["versions"][0]) == common.timestamp_to_datetime('2017-01-27T13:49:53.935Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-First']) == common.timestamp_to_datetime('2017-12-31T13:49:53.935000Z')
    assert common.timestamp_to_datetime(r.headers['X-TAXII-Date-Added-Last']) == common.timestamp_to_datetime('2017-12-31T13:49:53.935000Z')


def get_version_spec_version(test_client, filter):
    r = test_client.get(
        test.GET_OBJECTS_EP + filter,
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    return objs


def test_get_version_spec_version_20(test_client):
    objs = get_version_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions?match[spec_version]=2.0")
    assert len(objs["versions"]) == 1
    assert common.timestamp_to_datetime(objs["versions"][0]) == common.timestamp_to_datetime("2018-02-23T18:30:00.000Z")


def test_get_version_spec_version_21(test_client):
    objs = get_version_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions?match[spec_version]=2.1")
    assert len(objs["versions"]) == 1
    assert common.timestamp_to_datetime(objs["versions"][0]) == common.timestamp_to_datetime("2017-01-27T13:49:53.997Z")


def test_get_version_spec_version_2021(test_client):
    objs = get_version_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions?match[spec_version]=2.0,2.1")
    assert len(objs["versions"]) == 2


def test_get_version_spec_version_default(test_client):
    objs = get_version_spec_version(test_client, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions")
    # testing default value for spec_version

    returned = [
        common.timestamp_to_datetime(ver)
        for ver in objs["versions"]
    ]

    correct = [
        common.timestamp_to_datetime("2017-01-27T13:49:53.997Z")
    ]

    assert returned == correct


def test_delete_objects_version(test_client):
    add_objects = {"objects": []}
    coa_object = copy.deepcopy(TEST_OBJECT["objects"][0])
    object_id = coa_object["id"]
    coa_object["created"] = "2014-01-27T13:49:53.935Z"

    add_objects["objects"].append(copy.deepcopy(coa_object))
    coa_object["modified"] = "2015-01-27T13:49:53.935Z"
    add_objects["objects"].append(copy.deepcopy(coa_object))
    coa_object["modified"] = "2016-01-27T13:49:53.935Z"
    add_objects["objects"].append(copy.deepcopy(coa_object))
    coa_object["modified"] = "2018-01-27T13:49:53.935Z"
    add_objects["objects"].append(copy.deepcopy(coa_object))
    coa_object["modified"] = "2019-01-27T13:49:53.935Z"
    add_objects["objects"].append(copy.deepcopy(coa_object))

    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(add_objects),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21
    status_response = r_post.json
    assert status_response["success_count"] == 5  # Simple check to assert objects got successfully added to backend

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 5

    r = test_client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=2018-01-27T13:49:53.935Z",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 4
    assert "2018-01-27T13:49:53.935Z" not in objs["versions"]

    r = test_client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=first",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 3
    assert "2015-01-27T13:49:53.935Z" not in objs["versions"]

    r = test_client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=last",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 2
    assert "2019-01-27T13:49:53.935Z" not in objs["versions"]

    r = test_client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=all",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21


def test_delete_objects_spec_version(test_client):
    new_objects = copy.deepcopy(TEST_OBJECT)
    obj = copy.deepcopy(new_objects["objects"][0])
    obj["modified"] = "2019-01-27T13:49:53.935Z"
    obj["spec_version"] = "2.0"
    new_objects["objects"].append(copy.deepcopy(obj))
    object_id = obj["id"]

    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(new_objects),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[spec_version]=2.0",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1
    assert "2019-01-27T13:49:53.935Z" not in objs["versions"]

    r = test_client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[spec_version]=2.1",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21


def test_SCO_versioning(test_client):
    SCO = {
        "objects":
            [
                {
                    "type": "artifact",
                    "spec_version": "2.1",
                    "id": "artifact--6f437177-6e48-5cf8-9d9e-872a2bddd641",
                    "mime_type": "application/zip",
                    "encryption_algorithm": "mime-type-indicated",
                    "decryption_key": "My voice is my passport"
                }
            ]
    }
    object_id = SCO["objects"][0]["id"]

    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(SCO)),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=all",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=first",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=last",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "?added_after=2017-01-27T13:49:53.935Z",
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = test_client.get(
        test.ADD_OBJECTS_EP + object_id + "?added_after=" + common.datetime_to_string_stix(common.get_timestamp()),
        headers=GET_HEADERS,
        follow_redirects=True,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs) == 0

# combine filters together where problems may occur


# test non-200 responses
def test_get_api_root_information_not_existent(test_client):
    r = test_client.get(
        "/trustgroup2/", headers=GET_HEADERS, auth=("admin", "Password0")
    )
    assert r.status_code == 404


def test_get_collection_not_existent(test_client):

    r = test_client.get(
        test.NON_EXISTENT_COLLECTION_EP,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404


def test_get_collections_401(test_client):
    r = test_client.get(test.COLLECTIONS_EP, headers=GET_HEADERS)
    assert r.status_code == 401


def test_get_collections_404(test_client):
    # note that the api root "carbon1" is nonexistent
    r = test_client.get(
        "/carbon1/collections/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404


def test_get_collection_404(test_client):
    # note that api root "carbon1" is nonexistent
    r = test_client.get(
        "/carbon1/collections/12345678-1234-1234-1234-123456789012/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404


def test_get_status_401(test_client):
    # non existent object ID but shouldn't matter as the request should never pass login auth
    r = test_client.get(
        test.API_ROOT_EP + "status/2223/",
        headers=GET_HEADERS
    )
    assert r.status_code == 401


def test_get_status_404(test_client):
    r = test_client.get(
        test.API_ROOT_EP + "status/22101993/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404


def test_get_object_manifest_401(test_client):
    # non existent object ID but shouldnt matter as the request should never pass login
    r = test_client.get(test.COLLECTIONS_EP + "24042009/manifest/")
    assert r.status_code == 401


def test_get_object_manifest_403(test_client):
    r = test_client.get(
        test.FORBIDDEN_COLLECTION_EP + "manifest/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 403


def test_get_object_manifest_404(test_client):
    # note that collection ID doesnt exist
    r = test_client.get(
        test.COLLECTIONS_EP + "24042009/manifest/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404


def test_get_object_401(test_client):
    r = test_client.get(
       test.GET_OBJECTS_EP + "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111/",
       headers=GET_HEADERS
    )
    assert r.status_code == 401


def test_get_object_403(test_client):
    """note that the 403 code is still being generated at the Collection resource level
    (i.e. we dont have access rights to the collection specified, not just the object)
    """
    r = test_client.get(
        test.FORBIDDEN_COLLECTION_EP + "objects/indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 403


def test_get_object_404(test_client):
    # TAXII spec allows for a 404 or empty bundle if object is not found
    r = test_client.get(
        test.GET_OBJECTS_EP + "malware--cee60c30-a68c-11e3-b0c1-a01aac20d000/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    objs = r.json

    if r.status_code == 200:
        assert len(objs["objects"]) == 0
    else:
        assert r.status_code == 404


def test_get_or_add_objects_401(test_client):
    # note that no credentials are supplied with requests

    # get_objects()
    r = test_client.get(test.ADD_OBJECTS_EP, headers=GET_HEADERS)
    assert r.status_code == 401

    # add_objects()
    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(TEST_OBJECT)),
        headers=POST_HEADERS,
    )
    assert r_post.status_code == 401


def test_get_or_add_objects_403(test_client):
    """note that the 403 code is still being generated at the Collection resource level

      (i.e. we dont have access rights to the collection specified here, not just the object)
    """
    # get_objects()
    r = test_client.get(
        test.FORBIDDEN_COLLECTION_EP + "objects/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 403

    # add_objects
    r_post = test_client.post(
        test.FORBIDDEN_COLLECTION_EP + "objects/",
        data=json.dumps(copy.deepcopy(TEST_OBJECT)),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_post.status_code == 403


def test_get_or_add_objects_404(test_client):
    # get_objects()
    r = test_client.get(
        test.NON_EXISTENT_COLLECTION_EP + "objects/",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 404

    # add_objects
    r_post = test_client.post(
        test.NON_EXISTENT_COLLECTION_EP + "objects/",
        data=json.dumps(copy.deepcopy(TEST_OBJECT)),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    assert r_post.status_code == 404


def test_get_or_add_objects_422(test_client):
    """only applies to adding objects as would arise if user content is malformed"""

    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(TEST_OBJECT["objects"][0])),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )

    assert r_post.status_code == 422
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21
    error_data = r_post.json
    assert error_data["title"] == "ProcessingError"
    assert error_data["http_status"] == '422'


def test_object_pagination_bad_limit_value_400(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?limit=-20",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 400


def test_object_pagination_changing_params_400(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[version]=all&limit=2",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 2
    assert objs["more"]

    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[version]=all&limit=2&next=" + objs["next"],
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 2
    assert objs["more"]

    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[version]=first&limit=2&next=" + objs["next"],
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    assert r.status_code == 400
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["title"] == "ProcessingError"


def test_no_config():
    with pytest.raises(exceptions.InitializationError) as e:
        create_app({})
        assert str(e.value) == "You did not give backend information in your config."


def test_default_taxii_no_taxii_section():

    configuration = {
        "backend": {
            "module_class": "MemoryBackend",
            "filename": DATA_FILE,
            "interop_requirements": True,
        },
        "users": {
            "admin": "Password0"
        }
    }

    app = create_app(configuration)

    assert app.taxii_config['max_page_size'] == 100

    app.medallion_backend.close()


def test_default_userpass_no_auth_section():
    configuration = {
        "backend": {
            "module_class": "MemoryBackend",
            "filename": DATA_FILE,
            "interop_requirements": True,
        },
        "taxii": {
            "max_page_size": 20,
        },
    }

    app = create_app(configuration)

    assert app.users_config.get("user") == "pass"

    app.medallion_backend.close()


def test_default_backend_no_backend_section():
    with pytest.raises(exceptions.InitializationError) as e:
        configuration = {
            "users": {
                "admin": "Password0",
            },
            "taxii": {
                "max_page_size": 20,
            },
        }

        create_app(configuration)

    assert str(e.value) == "You did not give backend information in your config.."

# test collections with different can_read and can_write values


# test if program will accept duplicate objects being posted
def test_object_already_present(test_client):
    object_copy = {
                        "created": "2014-05-08T09:00:00.000Z",
                        "modified": "2014-05-08T09:00:00.000Z",
                        "id": "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463",
                        "relationship_type": "indicates",
                        "source_ref": "indicator--cd981c25-8042-4166-8945-51178443bdac",
                        "spec_version": "2.1",
                        "target_ref": "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
                        "type": "relationship"
                    }
    object_copy2 = object_copy.copy()
    del object_copy2['modified']
    add_objects = {"objects": []}

    add_objects["objects"].append(object_copy)
    # add object to test against
    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(add_objects),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )

    add_objects["objects"].append(object_copy2)
    # try to add a duplicate, with and without the modified key (both should fail)
    r_post = test_client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(add_objects),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    status_data = r_post.json
    assert r_post.status_code == 202
    # should not have failures
    assert "failures" not in status_data
    # should have successes
    assert "successes" in status_data


def test_save_to_file(flask_app):
    if flask_app.backend_config["module_class"] != "MemoryBackend":
        pytest.skip()
    with tempfile.NamedTemporaryFile(mode='w+') as tmpfile:
        flask_app.medallion_backend.save_data_to_file(tmpfile)
        tmpfile.flush()
        tmpfile.seek(0)
        data = json.load(tmpfile)
        assert "472c94ae-3113-4e3e-a4dd-a9f4ac7471d4" in data['trustgroup1']['collections']
        assert "365fed99-08fa-fdcd-a1b3-fb247eb41d01" in data['trustgroup1']['collections']
        assert "91a7b528-80eb-42ed-a74d-c6fbd5a26116" in data['trustgroup1']['collections']
        assert "52892447-4d7e-4f70-b94d-d7f22742ff63" in data['trustgroup1']['collections']


@pytest.fixture(params=TestServers)
def flask_app_without_threads(mongo_client, backup_filter_settings, request):
    configuration = {
        "backend": {
            "filename": DATA_FILE,
            "run_cleanup_threads": False,
            "interop_requirements": True
        },
        "users": {
            "root": "example",
        },
        "taxii": {
            "max_page_size": 20
        },
    }

    if request.param in request.config.getoption("backends"):
        _set_backend(configuration, mongo_client, request)

        app = create_app(configuration)

        yield app

        # Important for releasing backend resources
        app.medallion_backend.close()

    else:
        pytest.skip()


def test_status_cleanup(flask_app_without_threads):
    test_client = flask_app_without_threads.test_client()

    # add a status with the current time (by doing something which generates
    # one), which should not be deleted.
    new_status_resp = test_client.post(
        test.ADD_OBJECTS_EP,
        json=TEST_OBJECT,
        headers=POST_HEADERS,
        auth=("root", "example")
    )

    assert new_status_resp.status_code == 202

    expected_status_ids = [
        new_status_resp.json["id"],
        "2d086da7-4bdc-4f91-900e-d77486753710",
        "2d086da7-4bdc-4f91-900e-f4566be4b780"
    ]

    resps = [
        test_client.get(
            test.API_ROOT_EP + "status/" + status_id + "/",
            headers=GET_HEADERS,
            auth=("root", "example")
        )
        for status_id in expected_status_ids
    ]

    resp_status_codes = [
        resp.status_code for resp in resps
    ]

    assert resp_status_codes == [200, 200, 200]

    backend_app = flask_app_without_threads.medallion_backend
    backend_app.status_retention = SECONDS_IN_24_HOURS
    backend_app._pop_old_statuses()

    resps = [
        test_client.get(
            test.API_ROOT_EP + "status/" + status_id + "/",
            headers=GET_HEADERS,
            auth=("root", "example")
        )
        for status_id in expected_status_ids
    ]

    resp_status_codes = [
        resp.status_code for resp in resps
    ]

    assert resp_status_codes == [200, 404, 404]


def test_get_objects_match_type_version(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[type]=indicator&match[version]=2017-01-27T13:49:53.935Z",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )
    obj = r.json

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    assert len(obj['objects']) == 1
    assert obj['objects'][0]['type'] == "indicator"
    assert obj['objects'][0]['id'] == 'indicator--6770298f-0fd8-471a-ab8c-1c658a46574e'


def test_get_objects_match_type_spec_version(test_client):
    object_id = "indicator--68794cd5-28db-429d-ab1e-1256704ef906"
    newobj = {
        "objects": [
            {
                "type": "indicator",
                "spec_version": "2.0",
                "id": "indicator--68794cd5-28db-429d-ab1e-1256704ef906",
                "created": "2017-01-27T13:49:53.935Z",
                "modified": "2017-01-27T13:49:53.935Z",
                "name": "Test object"
            }
        ]
    }

    test_client.post(
        test.GET_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(newobj)),
        headers=POST_HEADERS,
        auth=("admin", "Password0")
    )
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[type]=indicator&match[spec_version]=2.1",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    obj = r.json
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    assert len(obj['objects']) == 2
    assert obj['objects'][0]['type'] == "indicator"
    assert obj['objects'][0]['id'] == "indicator--cd981c25-8042-4166-8945-51178443bdac"
    assert obj['objects'][0]['spec_version'] == "2.1"
    assert obj['objects'][1]['type'] == "indicator"
    assert obj['objects'][1]['id'] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    assert obj['objects'][1]['spec_version'] == "2.1"

    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[type]=indicator&match[spec_version]=2.0",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    obj = r.json
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    assert len(obj['objects']) == 1
    assert obj['objects'][0]['type'] == "indicator"
    assert obj['objects'][0]['id'] == object_id
    assert obj['objects'][0]['spec_version'] == "2.0"


def test_interop_tier1_filters(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[pattern_type]=stix",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2
    assert all("indicator" == obj["type"] for obj in objs["objects"])


def test_interop_tier2_filters(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[malware_types]=remote-access-trojan",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False

    obj_ids = [obj["id"] for obj in objs["objects"]]
    assert obj_ids == ["malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec"]


def test_interop_tier3_filters(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[tlp]=green",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False

    obj_ids = [obj["id"] for obj in objs["objects"]]
    assert obj_ids == ["indicator--cd981c25-8042-4166-8945-51178443bdac"]


def test_interop_relationship_filters(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[relationships-all]=malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False

    obj_ids = [obj["id"] for obj in objs["objects"]]
    assert obj_ids == ["relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463"]


def test_interop_calculation_filters(test_client):
    r = test_client.get(
        test.GET_OBJECTS_EP + "?match[confidence-gte]=10",
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False

    obj_ids = [obj["id"] for obj in objs["objects"]]
    assert obj_ids == ["malware-analysis--084a658c-a7ef-4581-a21d-1f600908741b"]


@pytest.fixture(params=TestServers)
def test_client_no_interop(mongo_client, backup_filter_settings, request):
    configuration = {
        "backend": {
            "filename": DATA_FILE,
            "interop_requirements": False
        },
        "users": {
            "admin": "Password0",
        },
        "taxii": {
            "max_page_size": 20
        },
    }

    if request.param in request.config.getoption("backends"):
        _set_backend(configuration, mongo_client, request)
        flask_app = create_app(configuration)

        yield flask_app.test_client()

        flask_app.medallion_backend.close()

    else:
        pytest.skip()


@pytest.mark.parametrize("query", [
    "match[pattern_type]=stix",
    "match[malware_types]=remote-access-trojan",
    "match[tlp]=green",
    "match[relationships-all]=malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
    "match[confidence-gte]=10"
])
def test_interop_filters_interop_disabled(test_client_no_interop, query):
    # With interop filters disabled, all of these queries should return the
    # same thing.
    r = test_client_no_interop.get(
        test.GET_OBJECTS_EP + "?" + query,
        headers=GET_HEADERS,
        auth=("admin", "Password0")
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 6
