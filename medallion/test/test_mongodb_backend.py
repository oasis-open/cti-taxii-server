import copy
import time
import uuid

import pytest

from medallion import get_backend, init
from medallion.test.data.initialize_mongodb import reset_db
from medallion.utils import common

API_OBJECTS_2 = {
    "id": "bundle--8fab937e-b694-11e3-b71c-0800271e87d2",
    "objects": [
        {
            "created": "2017-01-27T13:49:53.935Z",
            "id": "indicator--%s",
            "labels": [
                "url-watchlist"
            ],
            "modified": "2017-01-27T13:49:53.935Z",
            "name": "Malicious site hosting downloader",
            "pattern": "[url:value = 'http://x4z9arb.cn/5000']",
            "type": "indicator",
            "valid_from": "2017-01-27T13:49:53.935382Z"
        }
    ],
    "spec_version": "2.0",
    "type": "bundle"
}


@pytest.fixture(scope="module")
def backend():
    reset_db()
    init_backend({"type": "mongodb", "url": "mongodb://localhost:27017/"})
    return get_backend()


def test_server_discovery(backend):
    server_info = backend.server_discovery()
    assert server_info["title"] == "Some TAXII Server"


def test_get_api_root_information(backend):
    api_root_metadata = backend.get_api_root_information("trustgroup1")
    assert api_root_metadata["title"] == "Malware Research Group"


def test_get_collections(backend):
    collections_metdata = backend.get_collections("trustgroup1")
    collections_metdata = sorted(collections_metdata["collections"], key=lambda x: x["id"])
    assert collections_metdata[0]["id"] == "52892447-4d7e-4f70-b94d-d7f22742ff63"
    assert collections_metdata[1]["id"] == "91a7b528-80eb-42ed-a74d-c6fbd5a26116"


def test_get_collection(backend):
    collection_metdata = backend.get_collection("trustgroup1", "52892447-4d7e-4f70-b94d-d7f22742ff63")
    assert collection_metdata["media_types"][0] == "application/vnd.oasis.stix+json; version=2.0"


def test_get_object(backend):
    obj = backend.get_object("trustgroup1",
                             "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                             "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111",
                             None,
                             ("id", "type", "version"))
    assert obj["objects"][0]["id"] == "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111"


def test_get_objects(backend):
    objs = backend.get_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               {"match[type]": "relationship"},
                               ("id", "type", "version"))
    assert filter(lambda obj: obj["id"] == "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463", objs["objects"]) is not None


def test_add_objects(backend):
    new_bundle = copy.deepcopy(API_OBJECTS_2)
    new_id = "indicator--%s" % uuid.uuid4()
    new_bundle["objects"][0]["id"] = new_id
    resp = backend.add_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               new_bundle,
                               common.format_datetime(common.get_timestamp()))
    objs = backend.get_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               {"match[id]": new_id},
                               ("id", "type", "version"))
    assert objs["objects"][0]["id"] == new_id
    resp2 = backend.get_status("trustgroup1", resp["id"])
    assert resp2["success_count"] == 1
    mani = backend.get_object_manifest("trustgroup1",
                                       "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                                       {"match[id]": new_id},
                                       ("id", "type", "version"))
    assert mani[0]["id"] == new_id


def test_client_object_versioning(backend):
    new_id = "indicator--%s" % uuid.uuid4()
    new_bundle = copy.deepcopy(API_OBJECTS_2)
    new_bundle["objects"][0]["id"] = new_id
    resp = backend.add_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               new_bundle,
                               common.format_datetime(common.get_timestamp()))
    for i in range(0, 5):
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id
        new_bundle["objects"][0]["modified"] = common.format_datetime(common.get_timestamp())
        resp = backend.add_objects("trustgroup1",
                                   "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                                   new_bundle,
                                   common.format_datetime(common.get_timestamp()))
        time.sleep(1)
    objs = backend.get_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               {"match[id]": new_id, "match[version]": "all"},
                               ("id", "type", "version"))
    assert objs["objects"][0]["id"] == new_id
    assert objs["objects"][-1]["modified"] == new_bundle["objects"][0]["modified"]
    objs = backend.get_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               {"match[id]": new_id, "match[version]": "first"},
                               ("id", "type", "version"))
    assert objs["objects"][0]["id"] == new_id
    assert objs["objects"][0]["modified"] == "2017-01-27T13:49:53.935Z"
    objs = backend.get_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               {"match[id]": new_id, "match[version]": "last"},
                               ("id", "type", "version"))
    assert objs["objects"][0]["id"] == new_id
    assert objs["objects"][0]["modified"] == new_bundle["objects"][0]["modified"]
    objs = backend.get_objects("trustgroup1",
                               "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                               {"match[id]": new_id, "match[version]": "2017-01-27T13:49:53.935Z"},
                               ("id", "type", "version"))
    assert objs["objects"][0]["id"] == new_id
    assert objs["objects"][0]["modified"] == "2017-01-27T13:49:53.935Z"
    resp2 = backend.get_status("trustgroup1", resp["id"])
    assert resp2["success_count"] == 1
    mani = backend.get_object_manifest("trustgroup1",
                                       "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                                       {"match[id]": new_id},
                                       ("id", "type", "version"))
    assert mani[0]["id"] == new_id
    assert filter(lambda obj: obj["id"] == new_bundle["objects"][0]["modified"], mani[0]["versions"]) is not None


def test_added_after_filtering(backend):
    bundle = backend.get_objects("trustgroup1",
                                 "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                                 {"added_after": "2016-11-01T03:04:05Z"},
                                 ("id", "type", "version"))
    assert filter(lambda obj: obj["id"] == "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111", bundle["objects"]) is not None
