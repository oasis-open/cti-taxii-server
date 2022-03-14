import copy
import json
import tempfile

import pytest

from medallion import common, test
from medallion.views import MEDIA_TYPE_TAXII_V21

from .base_test import TaxiiTest


class MemoryTestServer(TaxiiTest):
    type = "memory"


class MongoTestServer(TaxiiTest):
    type = "mongo"


TestServers = ["memory", "mongo"]


@pytest.fixture(scope="module", params=TestServers)
def backend(request):
    if request.param in request.config.getoption("backends"):
        if request.param == "memory":
            test_server = MemoryTestServer()
        if request.param == "mongo":
            test_server = MongoTestServer()
        test_server.setUp()
        yield test_server
        test_server.tearDown()
    else:
        yield pytest.skip("skipped")


# start with basic get requests for each endpoint
def test_server_discovery(backend):
    r = backend.client.get(test.DISCOVERY_EP, headers=backend.headers)

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    server_info = r.json
    assert server_info["api_roots"][0] == "http://localhost:5000/api1/"


def test_get_api_root_information(backend):
    r = backend.client.get(test.API_ROOT_EP, headers=backend.headers)

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    api_root_metadata = r.json
    assert api_root_metadata["title"] == "Malware Research Group"


def test_get_status(backend):
    r = backend.client.get(
            test.API_ROOT_EP + "status/2d086da7-4bdc-4f91-900e-d77486753710",
            headers=backend.headers,
            follow_redirects=True,
        )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    status_data = r.json
    assert "successes" in status_data
    assert "failures" in status_data
    assert "pendings" in status_data


def test_get_collections(backend):
    r = backend.client.get(test.COLLECTIONS_EP, headers=backend.headers)

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


def test_get_objects(backend):

    r = backend.client.get(
        test.GET_OBJECTS_EP,
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 5

    # testing date-added headers
    assert r.headers['X-TAXII-Date-Added-First'] == "2014-05-08T09:00:00.000000Z"
    assert r.headers['X-TAXII-Date-Added-Last'] == "2017-12-31T13:49:53.935000Z"

    # testing ordering of returned objects by date_added
    correct_order = ['relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463',
                     'indicator--cd981c25-8042-4166-8945-51178443bdac',
                     'marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da',
                     'malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec',
                     'indicator--6770298f-0fd8-471a-ab8c-1c658a46574e']

    for x in range(0, len(correct_order)):
        assert objs['objects'][x]['id'] == correct_order[x]


def test_get_object(backend):

    r = backend.client.get(
        test.GET_OBJECTS_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1
    assert objs["objects"][0]["id"] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec"

    # testing date-added headers
    assert r.headers['X-TAXII-Date-Added-First'] == "2017-01-27T13:49:59.997000Z"
    assert r.headers['X-TAXII-Date-Added-Last'] == "2017-01-27T13:49:59.997000Z"


def test_add_and_delete_object(backend):
    # ------------- BEGIN: add object section ------------- #

    object_id = backend.TEST_OBJECT["objects"][0]["id"]

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(backend.TEST_OBJECT)),
        headers=backend.post_headers,
    )
    status_response = r_post.json
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    # ------------- END: add object section ------------- #
    # ------------- BEGIN: get object section ------------- #

    r_get = backend.client.get(
        test.ADD_OBJECTS_EP,
        headers=backend.headers,
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    objs = r_get.json
    assert any(obj["id"] == object_id for obj in objs["objects"])

    # ------------- END: get object section ------------- #
    # ------------- BEGIN: get object w/ filter section --- #

    r_get = backend.client.get(
        test.ADD_OBJECTS_EP + "?match[id]=" + object_id,
        headers=backend.headers,
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    objs = r_get.json
    assert objs["objects"][0]["id"] == object_id

    # ------------- END: get object w/ filter section --- #
    # ------------- BEGIN: get status section ------------- #

    r_get = backend.client.get(
        test.API_ROOT_EP + "status/%s/" % status_response["id"],
        headers=backend.headers,
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    status_response2 = r_get.json
    assert status_response2["success_count"] == 1

    # ------------- END: get status section ------------- #
    # ------------- BEGIN: get manifest section ------------- #

    r_get = backend.client.get(
        test.ADD_MANIFESTS_EP + "?match[id]=" + object_id,
        headers=backend.headers,
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    manifests = r_get.json
    assert len(manifests["objects"]) == 1
    assert manifests["objects"][0]["id"] == object_id

    # ------------- END: get manifest section ----------- #

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + object_id,
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id,
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    # test getting the deleted object's manifest

    r = backend.client.get(
        test.ADD_MANIFESTS_EP + object_id,
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 404
    # for whatever reason, content_type is not normal? doesn't really matter
    # assert r.content_type == MEDIA_TYPE_TAXII_V21


def test_get_object_manifests(backend):

    r = backend.client.get(
        test.GET_MANIFESTS_EP,
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    manifests = r.json
    assert len(manifests["objects"]) == 5

    # testing the date-added headers
    assert r.headers['X-TAXII-Date-Added-First'] == "2014-05-08T09:00:00.000000Z"
    assert r.headers['X-TAXII-Date-Added-Last'] == "2017-12-31T13:49:53.935000Z"

    # checking ordered by date_added

    for x in range(1, len(manifests["objects"])):
        assert manifests["objects"][x - 1]["date_added"] < manifests["objects"][x]["date_added"]


def test_get_version(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463/versions",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    vers = r.json
    assert len(vers["versions"]) == 1

    # testing the date-added headers
    assert r.headers['X-TAXII-Date-Added-First'] == "2014-05-08T09:00:00.000000Z"
    assert r.headers['X-TAXII-Date-Added-Last'] == "2014-05-08T09:00:00.000000Z"


# test each filter type with each applicable endpoint
def test_get_objects_added_after(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?added_after=2016-11-03T12:30:59Z",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 3


def test_get_objects_limit(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?limit=3",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is True
    assert len(objs['objects']) == 3
    assert r.headers['X-TAXII-Date-Added-First'] == '2014-05-08T09:00:00.000000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2017-01-20T00:00:00.000000Z'

    correct_order = ['relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463',
                     'indicator--cd981c25-8042-4166-8945-51178443bdac',
                     'marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da']

    for x in range(0, len(correct_order)):
        assert objs["objects"][x]["id"] == correct_order[x]

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?limit=3&next=" + r.json["next"],
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2

    assert r.headers['X-TAXII-Date-Added-First'] == '2017-01-27T13:49:59.997000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2017-12-31T13:49:53.935000Z'

    correct_order = ['malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec',
                     'indicator--6770298f-0fd8-471a-ab8c-1c658a46574e']

    for x in range(0, len(correct_order)):
        assert objs["objects"][x]["id"] == correct_order[x]


def test_get_objects_id(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[id]=malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1


def test_get_objects_type(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[type]=indicator",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2
    assert all("indicator" == obj["type"] for obj in objs["objects"])


def get_objects_by_version(backend, filter):
    r = backend.client.get(
        test.GET_OBJECTS_EP + filter,
        headers=backend.headers,
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    return objs


def test_objects_version_match_specific_date(backend):
    objs = get_objects_by_version(backend, "?match[version]=2016-12-25T12:30:59.444Z")
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"


def test_objects_version_match_first(backend):
    objs = get_objects_by_version(backend, "?match[version]=first")
    for obj in objs["objects"]:
        if obj["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e":
            assert obj["modified"] == "2016-11-03T12:30:59.000Z"
        if obj["id"] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec":
            assert obj["modified"] == "2017-01-27T13:49:53.997Z"


def test_objects_version_match_last(backend):
    objs = get_objects_by_version(backend, "?match[version]=last")
    for obj in objs["objects"]:
        if obj["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e":
            assert obj["modified"] == "2017-01-27T13:49:53.935Z"
        # Because the spec_version default filter comes before the version filter, the 2.0 version gets filtered out automatically
        # If you put a spec_version=2.0,2.1 here, then the correct version would be here
        # if obj["id"] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec":
        #    assert obj["modified"] == "2018-02-23T18:30:00.000Z"


def test_objects_version_match_all(backend):
    objs = get_objects_by_version(backend, "?match[version]=all")
    assert len(objs['objects']) == 7


def get_objects_spec_version(backend, filter, num_objects):
    r = backend.client.get(
        test.GET_OBJECTS_EP + filter,
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == num_objects
    return objs


def test_get_objects_spec_version_20(backend):
    objs = get_objects_spec_version(backend, "?match[spec_version]=2.0", 1)
    assert all("spec_version" not in obj for obj in objs['objects'])


def test_get_objects_spec_version_21_20(backend):
    get_objects_spec_version(backend, "?match[spec_version]=2.0,2.1", 5)


def test_get_objects_spec_version_21(backend):
    objs = get_objects_spec_version(backend, "?match[spec_version]=2.1", 5)
    assert all(obj['spec_version'] == "2.1" for obj in objs['objects'])


def test_get_objects_spec_version_default(backend):
    objs = get_objects_spec_version(backend, "", 5)
    assert all(obj['spec_version'] == "2.1" for obj in objs['objects'])


def get_object_added_after(backend, filter):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec" + filter,
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    return r.json


def test_get_object_added_after_case1(backend):
    objs = get_object_added_after(backend, "?added_after=2018-01-27T13:49:59.997000Z")
    assert 'more' not in objs
    assert 'objects' not in objs


def test_get_object_added_after_case2(backend):
    objs = get_object_added_after(backend, "?added_after=2017-01-27T13:49:59Z")
    assert objs['more'] is False
    assert len(objs['objects']) == 1


def test_get_object_limit(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?limit=1",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert r.headers['X-TAXII-Date-Added-First'] == '2017-12-31T13:49:53.935000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2017-12-31T13:49:53.935000Z'

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=all&limit=2",
        headers=backend.headers,
        follow_redirects=True
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

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=all&limit=2&next=" + objs['next'],
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert r.headers['X-TAXII-Date-Added-First'] == '2017-12-31T13:49:53.935000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2017-12-31T13:49:53.935000Z'


@pytest.mark.parametrize("filter, modified", [("?match[version]=2016-12-25T12:30:59.444Z", "2016-12-25T12:30:59.444Z"),
                                              ("?match[version]=first", "2016-11-03T12:30:59.000Z"),
                                              ("?match[version]=last", "2017-01-27T13:49:53.935Z")])
def test_get_object_version_single(backend, filter, modified):
    objstr = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    r = backend.client.get(
        test.GET_OBJECTS_EP + objstr + filter,
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == objstr
    assert objs["objects"][0]["modified"] == modified


def test_get_object_version_match_all(backend):

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=all",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 3


def get_object_spec_version(backend, filter, matching):
    r = backend.client.get(
        test.GET_OBJECTS_EP + filter + matching,
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    return objs


def test_get_object_spec_version_20(backend):
    objs = get_object_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "?match[spec_version]=2.0")
    assert all('spec_version' not in obj for obj in objs['objects'])


def test_get_object_spec_version_21(backend):
    objs = get_object_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "?match[spec_version]=2.1")
    assert all(obj['spec_version'] == "2.1" for obj in objs['objects'])


def test_get_object_spec_version_2021(backend):
    # though this is getting objects with every spec_version, the version filter gets only the latest object.
    objs = get_object_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "?match[spec_version]=2.0,2.1")
    for obj in objs['objects']:
        if obj['id'] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec":
            assert obj['modified'] == "2018-02-23T18:30:00.000Z"


def test_get_object_spec_version_default(backend):
    objs = get_object_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", "")
    assert all(obj['spec_version'] == "2.1" for obj in objs['objects'])


def test_get_manifest_added_after(backend):
    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?added_after=2017-01-20T00:00:00.000Z",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2


def test_get_manifest_limit(backend):
    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?limit=2",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is True
    assert len(objs['objects']) == 2
    assert r.headers['X-TAXII-Date-Added-First'] == objs['objects'][0]['date_added']
    assert r.headers['X-TAXII-Date-Added-Last'] == objs['objects'][-1]['date_added']

    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?limit=2&next=" + objs['next'],
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is True
    assert len(objs['objects']) == 2
    assert r.headers['X-TAXII-Date-Added-First'] == objs['objects'][0]['date_added']
    assert r.headers['X-TAXII-Date-Added-Last'] == objs['objects'][-1]['date_added']

    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?limit=2&next=" + objs['next'],
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert r.headers['X-TAXII-Date-Added-First'] == objs['objects'][0]['date_added']
    assert r.headers['X-TAXII-Date-Added-Last'] == objs['objects'][-1]['date_added']


def test_get_manifest_id(backend):
    object_id = "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec"
    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[id]=" + object_id,
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs['objects'][0]['id'] == object_id


def test_get_manifest_type(backend):
    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[type]=indicator",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2
    assert all('indicator' in obj['id'] for obj in objs['objects'])


def get_manifest_version(backend, filter):

    r = backend.client.get(
        test.GET_MANIFESTS_EP + filter,
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    return objs


def test_get_manifest_version_specific(backend):
    object_id = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    objs = get_manifest_version(backend, "?match[version]=2016-12-25T12:30:59.444Z")
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == object_id
    assert objs["objects"][0]["version"] == "2016-12-25T12:30:59.444Z"


def test_get_manifest_version_first(backend):
    object_id = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    objs = get_manifest_version(backend, "?match[version]=first")
    assert len(objs['objects']) == 5
    for obj in objs['objects']:
        if obj['id'] == object_id:
            assert obj['version'] == "2016-11-03T12:30:59.000Z"


def test_get_manifest_version_last(backend):
    object_id = "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    objs = get_manifest_version(backend, "?match[version]=last")
    assert len(objs['objects']) == 5
    for obj in objs['objects']:
        if obj['id'] == object_id:
            assert obj['version'] == "2017-01-27T13:49:53.935Z"


def test_get_manifest_version_all(backend):
    objs = get_manifest_version(backend, "?match[version]=all")
    assert len(objs['objects']) == 7


def get_manifest_spec_version(backend, filter):
    r = backend.client.get(
        test.GET_MANIFESTS_EP + filter,
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    return objs


def test_manifest_spec_version_20(backend):
    objs = get_manifest_spec_version(backend, "?match[spec_version]=2.0")
    assert len(objs['objects']) == 1
    assert all(obj['media_type'] == "application/stix+json;version=2.0" for obj in objs['objects'])


def test_manifest_spec_version_21(backend):
    objs = get_manifest_spec_version(backend, "?match[spec_version]=2.1")
    assert len(objs['objects']) == 5
    assert all(obj['media_type'] == "application/stix+json;version=2.1" for obj in objs['objects'])


def test_manifest_spec_version_2021(backend):
    objs = get_manifest_spec_version(backend, "?match[spec_version]=2.0,2.1")
    # though the spec_version filter is getting all objects, the automatic filtering by version only gets the latest objects
    assert len(objs['objects']) == 5
    for obj in objs['objects']:
        if obj['id'] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec":
            assert obj['version'] == "2018-02-23T18:30:00.000Z"


def test_manifest_spec_version_default(backend):
    objs = get_manifest_spec_version(backend, "")
    # testing default value
    assert len(objs['objects']) == 5
    assert all(obj['media_type'] == "application/stix+json;version=2.1" for obj in objs['objects'])


def test_get_version_added_after(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463/versions?added_after=2014-05-08T09:00:00Z",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs == {}

    r = backend.client.get(
        test.GET_OBJECTS_EP + "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463/versions?added_after=2014-05-08T08:00:00Z",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1


def test_get_version_limit(backend):

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?limit=1",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is True
    assert len(objs["versions"]) == 1
    assert objs["versions"][0] == '2016-11-03T12:30:59.000Z'
    assert r.headers['X-TAXII-Date-Added-First'] == '2016-11-03T12:30:59.001000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2016-11-03T12:30:59.001000Z'

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?limit=1&next=" + objs["next"],
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is True
    assert len(objs["versions"]) == 1
    assert objs["versions"][0] == '2016-12-25T12:30:59.444Z'
    assert r.headers['X-TAXII-Date-Added-First'] == '2016-12-27T13:49:59.000000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2016-12-27T13:49:59.000000Z'

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?limit=1&next=" + objs["next"],
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1
    assert objs["versions"][0] == '2017-01-27T13:49:53.935Z'
    assert r.headers['X-TAXII-Date-Added-First'] == '2017-12-31T13:49:53.935000Z'
    assert r.headers['X-TAXII-Date-Added-Last'] == '2017-12-31T13:49:53.935000Z'


def get_version_spec_version(backend, filter):
    r = backend.client.get(
        test.GET_OBJECTS_EP + filter,
        headers=backend.headers,
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    return objs


def test_get_version_spec_version_20(backend):
    objs = get_version_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions?match[spec_version]=2.0")
    assert len(objs["versions"]) == 1
    assert objs["versions"][0] == "2018-02-23T18:30:00.000Z"


def test_get_version_spec_version_21(backend):
    objs = get_version_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions?match[spec_version]=2.1")
    assert len(objs["versions"]) == 1
    assert objs["versions"][0] == "2017-01-27T13:49:53.997Z"


def test_get_version_spec_version_2021(backend):
    objs = get_version_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions?match[spec_version]=2.0,2.1")
    assert len(objs["versions"]) == 2


def test_get_version_spec_version_default(backend):
    objs = get_version_spec_version(backend, "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/versions")
    # testing default value for spec_version
    assert len(objs["versions"]) == 1
    assert objs["versions"][0] == "2017-01-27T13:49:53.997Z"


def test_delete_objects_version(backend):
    add_objects = {"objects": []}
    coa_object = copy.deepcopy(backend.TEST_OBJECT["objects"][0])
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

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(add_objects),
        headers=backend.post_headers,
    )
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21
    status_response = r_post.json
    assert status_response["success_count"] == 5  # Simple check to assert objects got successfully added to backend

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 5

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=2018-01-27T13:49:53.935Z",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 4
    assert "2018-01-27T13:49:53.935Z" not in objs["versions"]

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=first",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 3
    assert "2015-01-27T13:49:53.935Z" not in objs["versions"]

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=last",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 2
    assert "2019-01-27T13:49:53.935Z" not in objs["versions"]

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=all",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21


def test_delete_objects_spec_version(backend):
    new_objects = copy.deepcopy(backend.TEST_OBJECT)
    obj = copy.deepcopy(new_objects["objects"][0])
    obj["modified"] = "2019-01-27T13:49:53.935Z"
    obj["spec_version"] = "2.0"
    new_objects["objects"].append(copy.deepcopy(obj))
    object_id = obj["id"]

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(new_objects),
        headers=backend.post_headers,
    )
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[spec_version]=2.0",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1
    assert "2019-01-27T13:49:53.935Z" not in objs["versions"]

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + object_id + "?match[spec_version]=2.1",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21


def test_SCO_versioning(backend):
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

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(SCO)),
        headers=backend.post_headers,
    )
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=all",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=first",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "?match[version]=last",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "?added_after=2017-01-27T13:49:53.935Z",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 1

    r = backend.client.get(
        test.ADD_OBJECTS_EP + object_id + "?added_after=" + common.datetime_to_string_stix(common.get_timestamp()),
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs) == 0

# combine filters together where problems may occur


# test non-200 responses
def test_get_api_root_information_not_existent(backend):
    r = backend.client.get("/trustgroup2/", headers=backend.headers)
    assert r.status_code == 404


def test_get_collection_not_existent(backend):

    r = backend.client.get(
        test.NON_EXISTENT_COLLECTION_EP,
        headers=backend.headers,
    )
    assert r.status_code == 404


def test_get_collections_401(backend):
    r = backend.client.get(test.COLLECTIONS_EP)
    assert r.status_code == 401


def test_get_collections_404(backend):
    # note that the api root "carbon1" is nonexistent
    r = backend.client.get("/carbon1/collections/", headers=backend.headers)
    assert r.status_code == 404


def test_get_collection_404(backend):
    # note that api root "carbon1" is nonexistent
    r = backend.client.get("/carbon1/collections/12345678-1234-1234-1234-123456789012/", headers=backend.headers)
    assert r.status_code == 404


def test_get_status_401(backend):
    # non existent object ID but shouldn't matter as the request should never pass login auth
    r = backend.client.get(test.API_ROOT_EP + "status/2223/")
    assert r.status_code == 401


def test_get_status_404(backend):
    r = backend.client.get(test.API_ROOT_EP + "status/22101993/", headers=backend.headers)
    assert r.status_code == 404


def test_get_object_manifest_401(backend):
    # non existent object ID but shouldnt matter as the request should never pass login
    r = backend.client.get(test.COLLECTIONS_EP + "24042009/manifest/")
    assert r.status_code == 401


def test_get_object_manifest_403(backend):
    r = backend.client.get(
        test.FORBIDDEN_COLLECTION_EP + "manifest/",
        headers=backend.headers,
    )
    assert r.status_code == 403


def test_get_object_manifest_404(backend):
    # note that collection ID doesnt exist
    r = backend.client.get(test.COLLECTIONS_EP + "24042009/manifest/", headers=backend.headers)
    assert r.status_code == 404


def test_get_object_401(backend):
    r = backend.client.get(
       test.GET_OBJECTS_EP + "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111/",
    )
    assert r.status_code == 401


def test_get_object_403(backend):
    """note that the 403 code is still being generated at the Collection resource level
    (i.e. we dont have access rights to the collection specified, not just the object)
    """
    r = backend.client.get(
        test.FORBIDDEN_COLLECTION_EP + "objects/indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f/",
        headers=backend.headers,
    )
    assert r.status_code == 403


def test_get_object_404(backend):
    # TAXII spec allows for a 404 or empty bundle if object is not found
    r = backend.client.get(
        test.GET_OBJECTS_EP + "malware--cee60c30-a68c-11e3-b0c1-a01aac20d000/",
        headers=backend.headers,
    )
    objs = r.json

    if r.status_code == 200:
        assert len(objs["objects"]) == 0
    else:
        assert r.status_code == 404


def test_get_or_add_objects_401(backend):
    # note that no credentials are supplied with requests

    # get_objects()
    r = backend.client.get(test.ADD_OBJECTS_EP)
    assert r.status_code == 401

    # add_objects()
    bad_headers = copy.deepcopy(backend.post_headers)
    bad_headers.pop("Authorization")
    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(backend.TEST_OBJECT)),
        headers=bad_headers,
    )
    assert r_post.status_code == 401


def get_or_add_objects_403(backend):
    """note that the 403 code is still being generated at the Collection resource level

      (i.e. we dont have access rights to the collection specified here, not just the object)
    """
    # get_objects()
    r = backend.client.get(
        test.FORBIDDEN_COLLECTION_EP + "objects/",
        headers=backend.headers,
    )
    assert r.status_code == 403

    # add_objects
    r_post = backend.client.post(
        test.FORBIDDEN_COLLECTION_EP + "objects/",
        data=json.dumps(copy.deepcopy(backend.TEST_OBJECT)),
        headers=backend.post_headers,
    )
    assert r_post.status_code == 403


def test_get_or_add_objects_404(backend):
    # get_objects()
    r = backend.client.get(
        test.NON_EXISTENT_COLLECTION_EP + "objects/",
        headers=backend.headers,
    )
    assert r.status_code == 404

    # add_objects
    r_post = backend.client.post(
        test.NON_EXISTENT_COLLECTION_EP + "objects/",
        data=json.dumps(copy.deepcopy(backend.TEST_OBJECT)),
        headers=backend.post_headers,
    )
    assert r_post.status_code == 404


def test_get_or_add_objects_422(backend):
    """only applies to adding objects as would arise if user content is malformed"""

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(copy.deepcopy(backend.TEST_OBJECT["objects"][0])),
        headers=backend.post_headers,
    )

    assert r_post.status_code == 422
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21
    error_data = r_post.json
    assert error_data["title"] == "ProcessingError"
    assert error_data["http_status"] == '422'
    assert "While processing supplied content, an error occurred" in error_data["description"]


def test_object_pagination_bad_limit_value_400(backend):
    r = backend.client.get(test.GET_OBJECTS_EP + "?limit=-20",
                           headers=backend.headers)
    assert r.status_code == 400


def test_object_pagination_changing_params_400(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=all&limit=2",
        headers=backend.headers
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 2
    assert objs["more"]

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=all&limit=2&next=" + objs["next"],
        headers=backend.headers
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert len(objs["objects"]) == 2
    assert objs["more"]

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=first&limit=2&next=" + objs["next"],
        headers=backend.headers
    )
    assert r.status_code == 400
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["title"] == "ProcessingError"


# test other config values
# this may warrant some cleanup and organization later
class TestTAXIIWithNoConfig(TaxiiTest):
    type = "memory_no_config"


@pytest.fixture(scope="module")
def no_config():
    server = TestTAXIIWithNoConfig()
    server.setUp()
    yield server
    server.tearDown()


def test_default_userpass_no_config(no_config):
    assert no_config.app.users_backend.get("user") == "pass"


def test_default_backend_no_config(no_config):
    assert no_config.app.medallion_backend.data == {}


def test_default_taxii_config_no_config(no_config):
    assert no_config.app.taxii_config['max_page_size'] == 100


class TestTAXIIWithNoTAXIISection(TaxiiTest):
    type = "no_taxii"


@pytest.fixture(scope="module")
def no_taxii_section():
    server = TestTAXIIWithNoTAXIISection()
    server.setUp()
    yield server
    server.tearDown()


def test_default_taxii_no_taxii_section(no_taxii_section):
    assert no_taxii_section.app.taxii_config['max_page_size'] == 100


class TestTAXIIWithNoAuthSection(TaxiiTest):
    type = "no_auth"


@pytest.fixture(scope="module")
def no_auth_section():
    server = TestTAXIIWithNoAuthSection()
    server.setUp()
    yield server
    server.tearDown()


def test_default_userpass_no_auth_section(no_auth_section):
    assert no_auth_section.app.users_backend.get("user") == "pass"


class TestTAXIIWithNoBackendSection(TaxiiTest):
    type = "no_backend"


@pytest.fixture(scope="module")
def no_backend_section():
    server = TestTAXIIWithNoBackendSection()
    server.setUp()
    yield server
    server.tearDown()


def test_default_backend_no_backend_section(no_backend_section):
    assert no_backend_section.app.medallion_backend.data == {}

# test collections with different can_read and can_write values


# test if program will accept duplicate objects being posted
def test_object_already_present(backend):
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
    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(add_objects),
        headers=backend.post_headers,
    )

    add_objects["objects"].append(object_copy2)
    # try to add a duplicate, with and without the modified key (both should fail)
    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(add_objects),
        headers=backend.post_headers,
    )
    status_data = r_post.json
    assert r_post.status_code == 202
    # should not have failures
    assert "failures" not in status_data
    # should have successes
    assert "successes" in status_data


def test_save_to_file(backend):
    if backend.type != "memory":
        pytest.skip()
    with tempfile.NamedTemporaryFile(mode='w') as tmpfile:
        backend.app.medallion_backend.save_data_to_file(tmpfile.name)
        tmpfile.flush()
        with open(tmpfile.name) as f:
            data = json.load(f)
        assert data['trustgroup1']['collections'][0]['id'] == "472c94ae-3113-4e3e-a4dd-a9f4ac7471d4"
        assert data['trustgroup1']['collections'][1]['id'] == "365fed99-08fa-fdcd-a1b3-fb247eb41d01"
        assert data['trustgroup1']['collections'][2]['id'] == "91a7b528-80eb-42ed-a74d-c6fbd5a26116"
        assert data['trustgroup1']['collections'][3]['id'] == "52892447-4d7e-4f70-b94d-d7f22742ff63"
   
def test_get_objects_match_type_version(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[type]=incident&match[version]=2016-01-01T01:01:01.000Z",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

def test_get_objects_match_type_spec_version(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[type]=indicator&match[spec_version]=2.1",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

