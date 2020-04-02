import base64
import copy
import json
import sys
import time
import unittest
import uuid

import pytest
import six

from medallion import (application_instance, register_blueprints, set_config,
                       test)
from medallion.views import MEDIA_TYPE_TAXII_V21

from .base_test import TaxiiTest

BUNDLE = {
    "id": "bundle--8fab937e-b694-11e3-b71c-0800271e87d2",
    "objects": [
    ],
    "spec_version": "2.0",
    "type": "bundle",
}

API_OBJECT = {
    "created": "2017-01-27T13:49:53.935Z",
    "id": "indicator--%s",
    "labels": [
        "url-watchlist",
    ],
    "modified": "2017-01-27T13:49:53.935Z",
    "name": "Malicious site hosting downloader",
    "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
    "type": "indicator",
    "valid_from": "2017-01-27T13:49:53.935382Z",
}

def load_json_response(response):
    if isinstance(response, bytes):
        response = response.decode()
    io = six.StringIO(response)
    x = json.load(io)
    return x


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

"""
@pytest.fixture(scope="session", autouse=True)
def compare_results(request):
    request.session.save = {}

    yield

    comp = {}

    for func, res in request.session.save.items():
        function_name = func.split('[')[0]
        backend = func.split('[')[1]
        if function_name not in comp:
            comp[function_name] = {}
        comp[function_name][backend] = res

    for test in comp:
        r = []
        for backend in comp[test]:
            r.append(comp[test][backend])
        assert len(set(r)) == 1
"""

#start with basic get requests for each endpoint
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

def test_get_object(backend):

    r = backend.client.get(
        test.GET_OBJECTS_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    obj = r.json
    assert obj["objects"][0]["id"] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec"

def test_add_object(backend):
    new_bundle = copy.deepcopy(backend.API_OBJECTS_2)

    # ------------- BEGIN: add object section ------------- #

    post_header = copy.deepcopy(backend.headers)
    post_header["Content-Type"] = MEDIA_TYPE_TAXII_V21
    post_header["Accept"] = MEDIA_TYPE_TAXII_V21

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(new_bundle),
        headers=post_header,
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
    assert any(obj["id"] == "indicator--68794cd5-28db-429d-ab1e-1256704ef906" for obj in objs["objects"])
    
    # ------------- END: get object section ------------- #
    # ------------- BEGIN: get object w/ filter section --- #

    r_get = backend.client.get(
        test.ADD_OBJECTS_EP + "?match[id]=indicator--68794cd5-28db-429d-ab1e-1256704ef906",
        headers=backend.headers,
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    objs = r_get.json
    assert objs["objects"][0]["id"] == "indicator--68794cd5-28db-429d-ab1e-1256704ef906"

    # ------------- END: get object w/ filter section --- #
    # ------------- BEGIN: get status section ------------- #

    r_get = backend.client.get(
        test.API_ROOT_EP + "status/%s/" % status_response["id"],
        headers=backend.headers,
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    status_response2 = r_get.json
    assert status_response2["success_count"] == 2

    # ------------- END: get status section ------------- #
    # ------------- BEGIN: get manifest section ------------- #

    r_get = backend.client.get(
        test.ADD_MANIFESTS_EP + "?match[id]=indicator--68794cd5-28db-429d-ab1e-1256704ef906",
        headers=backend.headers,
    )
    assert r_get.status_code == 200
    assert r_get.content_type == MEDIA_TYPE_TAXII_V21
    manifests = r_get.json
    assert manifests["objects"][0]["id"] == "indicator--68794cd5-28db-429d-ab1e-1256704ef906"

    # ------------- END: get manifest section ----------- #

def test_delete_object(backend):
    DELETE_OBJECT = {
        "objects": [
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--ad33acc3-89b0-4604-8bf2-3433efa86bfc",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2015-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.0",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            }
        ]
    }

    new_bundle = copy.deepcopy(DELETE_OBJECT)
    post_header = copy.deepcopy(backend.headers)
    post_header["Content-Type"] = MEDIA_TYPE_TAXII_V21
    post_header["Accept"] = MEDIA_TYPE_TAXII_V21

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(new_bundle),
        headers=post_header,
    )
    status_response = r_post.json
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + "indicator--ad33acc3-89b0-4604-8bf2-3433efa86bfc",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    
    r = backend.client.get(
        test.ADD_OBJECTS_EP + "indicator--ad33acc3-89b0-4604-8bf2-3433efa86bfc",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21

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

#test each filter type with each applicable endpoint
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

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?limit=3&next=" + r.json["next"],
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 2

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
    assert all("indicator" in obj["id"] for obj in objs["objects"])

def test_get_objects_version(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=2016-12-25T12:30:59.444Z",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=first&match[id]=indicator--6770298f-0fd8-471a-ab8c-1c658a46574e",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["modified"] == "2016-11-03T12:30:59.000Z"

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=last&match[id]=indicator--6770298f-0fd8-471a-ab8c-1c658a46574e",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["modified"] == "2017-01-27T13:49:53.935Z"

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=all",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 7

def test_get_objects_spec_version(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[spec_version]=2.0",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert all(obj['spec_version'] == "2.0" for obj in objs['objects'])

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[spec_version]=2.1",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 5
    assert all(obj['spec_version'] == "2.1" for obj in objs['objects'])

    # look into and talk about testing the spec_version with no parameter

def test_get_object_added_after(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec?added_after=2018-01-27T13:49:59.997000Z",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert 'more' not in objs
    assert 'objects' not in objs

    r = backend.client.get(
        test.GET_OBJECTS_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec?added_after=2017-01-27T13:49:59Z",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
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

def test_get_object_version(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=2016-12-25T12:30:59.444Z",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    assert objs["objects"][0]["modified"] == "2016-12-25T12:30:59.444Z"

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=first",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["modified"] == "2016-11-03T12:30:59.000Z"
    assert objs["objects"][0]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[version]=last",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["modified"] == "2017-01-27T13:49:53.935Z"
    assert objs["objects"][0]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"

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

def test_get_object_spec_version(backend):
    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[spec_version]=2.0",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert all(obj['spec_version'] == "2.0" for obj in objs['objects'])

    r = backend.client.get(
        test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e?match[spec_version]=2.1",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert all(obj['spec_version'] == "2.1" for obj in objs['objects'])

    #look into and test spec_version default argument

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

def test_get_manifest_id(backend):
    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[id]=malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs['objects'][0]['id'] == "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec"

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
    assert "indicator" in objs['objects'][0]['id']
    assert "indicator" in objs['objects'][1]['id']

def test_get_manifest_version(backend):
    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[version]=2016-11-03T12:30:59.000Z",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert objs["objects"][0]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    assert objs["objects"][0]["version"] == "2016-11-03T12:30:59.000Z"

    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[version]=first",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 5
    assert objs["objects"][2]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    assert objs["objects"][2]["version"] == "2016-11-03T12:30:59.000Z"

    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[version]=last",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 5
    assert objs["objects"][4]["id"] == "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e"
    assert objs["objects"][4]["version"] == "2017-01-27T13:49:53.935Z"

    r = backend.client.get(
        test.GET_OBJECTS_EP + "?match[version]=all",
        headers=backend.headers,
        follow_redirects=True
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 7

def test_get_manifest_spec_version(backend):
    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[spec_version]=2.0",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 1
    assert all(obj['media_type'] == "application/stix+json;version=2.0" for obj in objs['objects'])

    r = backend.client.get(
        test.GET_MANIFESTS_EP + "?match[spec_version]=2.1",
        headers=backend.headers,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs['more'] is False
    assert len(objs['objects']) == 5
    assert all(obj['media_type'] == "application/stix+json;version=2.1" for obj in objs['objects'])

    # look into and test spec_version default argument

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

def test_get_version_spec_version(backend):
    r = backend.client.get(
            test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?match[spec_version]=2.0",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1
    assert objs["versions"][0] == "2016-11-03T12:30:59.000Z"

    r = backend.client.get(
            test.GET_OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions?match[spec_version]=2.1",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 2
    assert "2016-11-03T12:30:59.000Z" not in objs["versions"]

def test_delete_objects_version(backend):
    DELETE_VERSIONS = {
        "objects": [
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2015-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.1",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            },
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2019-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.1",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            },
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2016-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.1",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            },
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2017-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.1",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            },
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2018-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.1",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            },
        ],
    }

    new_bundle = copy.deepcopy(DELETE_VERSIONS)
    post_header = copy.deepcopy(backend.headers)
    post_header["Content-Type"] = MEDIA_TYPE_TAXII_V21
    post_header["Accept"] = MEDIA_TYPE_TAXII_V21

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(new_bundle),
        headers=post_header,
    )
    status_response = r_post.json
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21
    assert status_response["success_count"] == 5  # Simple check to assert objects got successfully added to backend

    r = backend.client.get(
            test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 5

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736?match[version]=2018-01-27T13:49:53.935Z",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
            test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736/versions",
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
        test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736?match[version]=first",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
            test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736/versions",
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
        test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736?match[version]=last",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
            test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736/versions",
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
        test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736?match[version]=all",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
            test.ADD_OBJECTS_EP + "indicator--3aa5ad42-ff70-4442-a44c-055bea7b7736/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21

def test_delete_objects_spec_version(backend):
    DELETE_SPEC_VERSION = {
        "objects": [
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--801e2c62-361f-4e87-9e46-1d6df4abe048",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2015-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.0",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            },
            {
                "created": "2014-01-27T13:49:53.935Z",
                "id": "indicator--801e2c62-361f-4e87-9e46-1d6df4abe048",
                "labels": [
                    "url-watchlist",
                ],
                "modified": "2016-01-27T13:49:53.935Z",
                "name": "Malicious site hosting downloader",
                "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
                "pattern_type": "stix",
                "spec_version": "2.1",
                "type": "indicator",
                "valid_from": "2017-01-27T13:49:53.935382Z",
            }
        ]
    }

    new_bundle = copy.deepcopy(DELETE_SPEC_VERSION)
    post_header = copy.deepcopy(backend.headers)
    post_header["Content-Type"] = MEDIA_TYPE_TAXII_V21
    post_header["Accept"] = MEDIA_TYPE_TAXII_V21

    r_post = backend.client.post(
        test.ADD_OBJECTS_EP,
        data=json.dumps(new_bundle),
        headers=post_header,
    )
    status_response = r_post.json
    assert r_post.status_code == 202
    assert r_post.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + "indicator--801e2c62-361f-4e87-9e46-1d6df4abe048?match[spec_version]=2.0",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
            test.ADD_OBJECTS_EP + "indicator--801e2c62-361f-4e87-9e46-1d6df4abe048/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    objs = r.json
    assert objs["more"] is False
    assert len(objs["versions"]) == 1
    assert "2015-01-27T13:49:53.935Z" not in objs["versions"]

    r = backend.client.delete(
        test.ADD_OBJECTS_EP + "indicator--801e2c62-361f-4e87-9e46-1d6df4abe048?match[spec_version]=2.1",
        headers=backend.headers,
        follow_redirects=True
    )
    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21

    r = backend.client.get(
            test.ADD_OBJECTS_EP + "indicator--801e2c62-361f-4e87-9e46-1d6df4abe048/versions",
        headers=backend.headers,
        follow_redirects=True,
    )

    assert r.status_code == 404
    assert r.content_type == MEDIA_TYPE_TAXII_V21

#test save and next capabilities

#combine filters together where problems may occur

#test bad filters

#test non-200 responses
def test_get_api_root_information_not_existent(backend):
    r = backend.client.get("/trustgroup2/", headers=backend.headers)
    assert r.status_code == 404

def test_get_collection_not_existent(backend):
    
    r = backend.client.get(
        test.NON_EXISTENT_COLLECTION_EP,
        headers=backend.headers,
    )
    assert r.status_code == 404

#test collections with different can_read and can_write values
