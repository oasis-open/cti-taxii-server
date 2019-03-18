import base64
import copy
import json
import unittest
import uuid

import six

from medallion import (application_instance, init_backend, register_blueprints,
                       set_config, test)
from medallion.test.data.initialize_mongodb import reset_db
from medallion.utils import common
from medallion.views import MEDIA_TYPE_STIX_V20, MEDIA_TYPE_TAXII_V20

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


class TestTAXIIServerWithMongoDBBackend(unittest.TestCase):

    def setUp(self):
        self.app = application_instance
        self.application_context = self.app.app_context()
        self.application_context.push()
        self.app.testing = True
        register_blueprints(self.app)
        reset_db()
        self.configuration = {
            "backend": {
                "module": "medallion.backends.mongodb_backend",
                "module_class": "MongoBackend",
                "uri": "mongodb://localhost:27017/"
            },
            "users": {
                "admin": "Password0"
            }
        }
        init_backend(self.app, self.configuration["backend"])
        set_config(self.app, self.configuration["users"])
        self.client = application_instance.test_client()
        encoded_auth = 'Basic ' + base64.b64encode(b"admin:Password0").decode("ascii")
        self.auth = {'Authorization': encoded_auth}

    def tearDown(self):
        self.application_context.pop()

    @staticmethod
    def load_json_response(response):
        if isinstance(response, bytes):
            response = response.decode()
        io = six.StringIO(response)
        return json.load(io)

    def test_server_discovery(self):
        r = self.client.get(test.DISCOVERY_EP, headers=self.auth)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_TAXII_V20)
        server_info = self.load_json_response(r.data)
        assert server_info["title"] == "Some TAXII Server"
        assert len(server_info["api_roots"]) == 2
        assert server_info["api_roots"][0] == "http://localhost:5000/trustgroup1/"

    def test_get_api_root_information(self):
        r = self.client.get(test.API_ROOT_EP, headers=self.auth)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_TAXII_V20)
        api_root_metadata = self.load_json_response(r.data)
        assert api_root_metadata["title"] == "Malware Research Group"

    def test_get_api_root_information_not_existent(self):
        r = self.client.get("/trustgroup2/", headers=self.auth)
        self.assertEqual(r.status_code, 404)

    def test_get_collections(self):
        r = self.client.get(test.COLLECTIONS_EP, headers=self.auth)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_TAXII_V20)
        collections_metadata = self.load_json_response(r.data)
        collections_metadata = sorted(collections_metadata["collections"], key=lambda x: x["id"])
        collection_ids = [cm["id"] for cm in collections_metadata]

        assert len(collection_ids) == 3
        assert "52892447-4d7e-4f70-b94d-d7f22742ff63" in collection_ids
        assert "91a7b528-80eb-42ed-a74d-c6fbd5a26116" in collection_ids
        assert "64993447-4d7e-4f70-b94d-d7f33742ee63" in collection_ids

    def test_get_collection(self):
        r = self.client.get(
            test.GET_COLLECTION_EP,
            headers=self.auth
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_TAXII_V20)
        collections_metadata = self.load_json_response(r.data)
        assert collections_metadata["media_types"][0] == "application/vnd.oasis.stix+json; version=2.0"

    def test_get_collection_not_existent(self):
        r = self.client.get(
            test.NON_EXISTENT_COLLECTION_EP,
            headers=self.auth
        )
        self.assertEqual(r.status_code, 404)

    def test_get_object(self):
        r = self.client.get(
           test.GET_OBJECT_EP + "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111/",
           headers=self.auth
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        obj = self.load_json_response(r.data)
        assert obj["objects"][0]["id"] == "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111"

    def test_get_objects(self):
        r = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=relationship",
            headers=self.auth
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        objs = self.load_json_response(r.data)
        assert any(obj["id"] == "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463" for obj in objs["objects"])

    def test_add_objects(self):
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle["objects"][0]["id"] = new_id

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header
        )
        status_response = self.load_json_response(r_post.data)
        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # ------------- END: add object section ------------- #
        # ------------- BEGIN: get object section ------------- #

        get_header = copy.deepcopy(self.auth)
        get_header["Accept"] = MEDIA_TYPE_STIX_V20

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s" % new_id,
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        objs = self.load_json_response(r_get.data)
        assert objs["objects"][0]["id"] == new_id

        # ------------- END: get object section ------------- #
        # ------------- BEGIN: get status section ------------- #

        r_get = self.client.get(
            test.API_ROOT_EP + "status/%s/" % status_response["id"],
            headers=self.auth
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        status_response2 = self.load_json_response(r_get.data)
        assert status_response2["success_count"] == 1

        # ------------- END: get status section ------------- #
        # ------------- BEGIN: get manifest section ------------- #

        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=%s" % new_id,
            headers=self.auth
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        manifests = self.load_json_response(r_get.data)
        assert manifests["objects"][0]["id"] == new_id
        # ------------- END: end manifest section ------------- #

    def test_client_object_versioning(self):
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header
        )
        status_response = self.load_json_response(r_post.data)
        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        for i in range(0, 5):
            new_bundle = copy.deepcopy(API_OBJECTS_2)
            new_bundle["objects"][0]["id"] = new_id
            new_bundle["objects"][0]["modified"] = common.format_datetime(common.get_timestamp())
            r_post = self.client.post(
                test.ADD_OBJECTS_EP,
                data=json.dumps(new_bundle),
                headers=post_header
            )
            status_response = self.load_json_response(r_post.data)
            self.assertEqual(r_post.status_code, 202)
            self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # ------------- END: add object section ------------- #
        # ------------- BEGIN: get object section 1 ------------- #

        get_header = copy.deepcopy(self.auth)
        get_header["Accept"] = MEDIA_TYPE_STIX_V20

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "all"),
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        objs = self.load_json_response(r_get.data)
        assert objs["objects"][0]["id"] == new_id
        assert objs["objects"][-1]["modified"] == new_bundle["objects"][0]["modified"]

        # ------------- END: get object section 1 ------------- #
        # ------------- BEGIN: get object section 2 ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "first"),
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        objs = self.load_json_response(r_get.data)
        assert objs["objects"][0]["id"] == new_id
        assert objs["objects"][0]["modified"] == "2017-01-27T13:49:53.935Z"

        # ------------- END: get object section 2 ------------- #
        # ------------- BEGIN: get object section 3 ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "last"),
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        objs = self.load_json_response(r_get.data)
        assert objs["objects"][0]["id"] == new_id
        assert objs["objects"][0]["modified"] == new_bundle["objects"][0]["modified"]

        # ------------- END: get object section 3 ------------- #
        # ------------- BEGIN: get object section 4 ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "2017-01-27T13:49:53.935Z"),
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        objs = self.load_json_response(r_get.data)
        assert objs["objects"][0]["id"] == new_id
        assert objs["objects"][0]["modified"] == "2017-01-27T13:49:53.935Z"

        # ------------- END: get object section 4 ------------- #
        # ------------- BEGIN: get status section ------------- #

        r_get = self.client.get(
            test.API_ROOT_EP + "status/%s/" % status_response["id"],
            headers=self.auth
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        status_response2 = self.load_json_response(r_get.data)
        assert status_response2["success_count"] == 1

        # ------------- END: get status section ------------- #
        # ------------- BEGIN: get manifest section ------------- #

        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=%s" % new_id,
            headers=self.auth
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        manifests = self.load_json_response(r_get.data)

        assert manifests["objects"][0]["id"] == new_id
        assert any(version == new_bundle["objects"][0]["modified"] for version in manifests["objects"][0]["versions"])
        # ------------- END: get manifest section ------------- #

    def test_added_after_filtering(self):
        get_header = copy.deepcopy(self.auth)
        get_header["Accept"] = MEDIA_TYPE_STIX_V20

        # ------------- BEGIN: test with static data section ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?added_after=2018-01-01T00:00:00Z",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)
        bundle = self.load_json_response(r_get.data)

        # none of the objects in the test data set has an added_after date post 1 Jan 2018
        self.assertEqual(0, len(bundle['objects']))

        # ------------- END: test with static data section ------------- #
        # ------------- BEGIN: test with object added via API ------------- #
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header
        )
        self.load_json_response(r_post.data)
        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # refetch objects post 1 Jan 2018 - should now have 1 result
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?added_after=2018-01-01T00:00:00Z",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)
        bundle = self.load_json_response(r_get.data)

        self.assertEqual(1, len(bundle['objects']))
        self.assertEqual(new_id, bundle['objects'][0]['id'])

    def test_marking_defintions(self):
        get_header = copy.deepcopy(self.auth)
        get_header["Accept"] = MEDIA_TYPE_STIX_V20

        # ------------- BEGIN: get manifest section 1 ------------- #
        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        manifests = self.load_json_response(r_get.data)

        assert manifests["objects"][0]["id"] == "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da"
        self.assertEqual(len(manifests["objects"]), 1, "Expected exactly one result")
        # ------------- END: get manifest section 1 ------------- #
        # ------------- BEGIN: get manifest section 2 ------------- #
        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[type]=marking-definition",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        manifests = self.load_json_response(r_get.data)

        assert all(obj["id"].startswith("marking-definition") for obj in manifests["objects"])
        self.assertEqual(len(manifests["objects"]), 1, "Expected exactly one results")
        # ------------- END: get manifest section 2 ------------- #
        # ------------- BEGIN: get objects section 1 ------------- #
        r_get = self.client.get(
            test.GET_OBJECT_EP + "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da/",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        manifests = self.load_json_response(r_get.data)

        assert manifests["objects"][0]["id"] == "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da"
        self.assertEqual(len(manifests["objects"]), 1, "Expected exactly one result")
        # ------------- END: get objects section 1 ------------- #
        # ------------- BEGIN: get objects section 2 ------------- #
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=marking-definition",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        manifests = self.load_json_response(r_get.data)

        assert all(obj["id"].startswith("marking-definition") for obj in manifests["objects"])
        self.assertEqual(len(manifests["objects"]), 1, "Expected exactly one result")
        # ------------- END: get objects section 2 ------------- #
        # ------------- BEGIN: get objects section 3 ------------- #
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=marking-definition,malware",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        manifests = self.load_json_response(r_get.data)

        assert all((obj["id"].startswith("marking-definition") or obj["id"].startswith("malware")) for obj in manifests["objects"])
        self.assertEqual(len(manifests["objects"]), 2, "Expected exactly two results")
        # ------------- END: get objects section 3 ------------- #
        # ------------- BEGIN: get objects section 4 ------------- #
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
            headers=get_header
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        manifests = self.load_json_response(r_get.data)

        assert manifests["objects"][0]["id"] == "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da"
        self.assertEqual(len(manifests["objects"]), 1, "Expected exactly one result")
        # ------------- END: get objects section 4 ------------- #

    def test_get_collections_401(self):
        r = self.client.get(test.COLLECTIONS_EP)
        self.assertEqual(r.status_code, 401)

    """get_collections 403 - not implemented. Medallion TAXII implementation does not have
    access control for Collection resource metadata"""

    def test_get_collections_404(self):
        # note that api root "carbon1" is nonexistent
        r = self.client.get("/carbon1/collections/", headers=self.auth)
        self.assertEqual(r.status_code, 404)

    def test_get_status_401(self):
        # non existent ID but shouldnt matter as the request should never pass login
        r = self.client.get(test.API_ROOT_EP + "status/2223/")
        self.assertEqual(r.status_code, 401)

    """get_status 403 - not implemented. Medallion TAXII implementation does not have
     access control for Status resources"""

    def test_get_status_404(self):
        r = self.client.get(test.API_ROOT_EP + "status/22101993/", headers=self.auth)
        self.assertEqual(r.status_code, 404)

    def test_get_object_manifest_401(self):
        # non existent collection ID but shouldnt matter as the request should never pass login
        r = self.client.get(test.COLLECTIONS_EP + "24042009/manifest/")
        self.assertEqual(r.status_code, 401)

    def test_get_object_manifest_403(self):
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "manifest/",
            headers=self.auth)
        self.assertEqual(r.status_code, 403)

    def test_get_object_manifest_404(self):
        # note that collection ID does not exist
        r = self.client.get(test.COLLECTIONS_EP + "24042009/manifest/", headers=self.auth)
        self.assertEqual(r.status_code, 404)

    def test_get_object_401(self):
        r = self.client.get(
            test.GET_OBJECT_EP + "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111/"
        )
        self.assertEqual(r.status_code, 401)

    def test_get_object_403(self):
        """note that the 403 code is still being generated at the Collection resource level

           (i.e. we dont have access rights to the collection specified, not just the object)
        """
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "objects/indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f/",
            headers=self.auth
        )
        self.assertEqual(r.status_code, 403)

    def test_get_object_404(self):
        # TAXII spec allows for a 404 or empty bundle if object is not found
        r = self.client.get(
            test.GET_OBJECT_EP + "malware--cee60c30-a68c-11e3-b0c1-a01aac20d000/",
            headers=self.auth
        )
        objs = self.load_json_response(r.data)

        if r.status_code == 200:
            assert len(objs["objects"]) == 0
        else:
            self.assertEqual(r.status_code, 404)

    def test_get_or_add_objects_401(self):
        # note that no credentials are supplied with requests

        # get_objects()
        r = self.client.get(test.GET_OBJECT_EP)
        self.assertEqual(r.status_code, 401)

        # add_objects()
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = {}
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_STIX_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header
        )
        self.assertEqual(r_post.status_code, 401)

    def get_or_add_objects_403(self):
        """note that the 403 code is still being generated at the Collection resource level

          (i.e. we dont have access rights to the collection specified here, not just the object)
        """
        # get_objects()
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "objects/",
            headers=self.auth
        )
        self.assertEqual(r.status_code, 403)

        # add_objects
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.FORBIDDEN_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header
        )
        self.assertEqual(r_post.status_code, 403)

    def test_get_or_add_objects_404(self):
        # get_objects()
        r = self.client.get(
            test.NON_EXISTENT_COLLECTION_EP + "objects/",
            headers=self.auth
        )
        self.assertEqual(r.status_code, 404)

        # add_objects
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.NON_EXISTENT_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header
        )
        self.assertEqual(r_post.status_code, 404)

    def test_get_or_add_objects_422(self):
        """only applies to adding objects as would arise if user content is malformed"""

        # add_objects()
        new_id = "indicator--%s" % uuid.uuid4()
        malformed_bundle = {
            "created": "2016-11-03T12:30:59.000Z",
            "description": "Accessing this url will infect your machine with malware.",
            "id": new_id,
            "labels": [
                "url-watchlist"
            ],
            "modified": "2016-11-03T12:30:59.000Z",
            "name": "Malicious site hosting downloader",
            "pattern": "[url:value = 'http://yarg.cn/4712']",
            "type": "indicator",
            "valid_from": "2017-01-27T13:51:53.935382Z"
        }

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(malformed_bundle),
            headers=post_header
        )

        self.assertEqual(r_post.status_code, 422)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)
        error_data = self.load_json_response(r_post.data)
        assert error_data["title"] == "ProcessingError"
        assert error_data["http_status"] == "422"
        assert "While processing supplied content, an error occured" in error_data["description"]

    def test_get_object_containing_additional_properties(self):
        """tests fix for issue where additional indicator SDO properties such as external_references
        are not being returned correctly"""

        # setup data by adding indicator with valid_until date and external_references
        new_id = "indicator--%s" % uuid.uuid4()
        valid_until = "2018-01-27T13:49:53.935382Z"
        external_references = [{
            "source_name": "capec",
            "external_id": "CAPEC-163"
            }]
        new_bundle = copy.deepcopy(API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id
        new_bundle["objects"][0]["valid_until"] = valid_until
        new_bundle["objects"][0]["external_references"] = external_references

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header
        )

        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # get the indicator and check the valid_until date and external_references are returned
        r = self.client.get(test.GET_OBJECT_EP + new_id + '/', headers=self.auth)
        self.assertEqual(r.status_code, 200)
        event = json.loads(r.data)
        self.assertEqual(event['objects'][0]['valid_until'], valid_until)
        self.assertEqual(event['objects'][0]['external_references'], external_references)
