import copy
import json
import uuid

import six

from medallion import test
from medallion.test.base_test import TaxiiTest
from medallion.test.generic_initialize_mongodb import connect_to_client
from medallion.utils import common
from medallion.views import MEDIA_TYPE_STIX_V20, MEDIA_TYPE_TAXII_V20


class TestTAXIIServerWithMongoDBBackend(TaxiiTest):
    type = "mongo"

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
        assert len(server_info["api_roots"]) == 3
        assert server_info["api_roots"][2] == "http://localhost:5000/trustgroup1/"

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

        assert len(collection_ids) == 4
        assert "52892447-4d7e-4f70-b94d-d7f22742ff63" in collection_ids
        assert "91a7b528-80eb-42ed-a74d-c6fbd5a26116" in collection_ids
        assert "64993447-4d7e-4f70-b94d-d7f33742ee63" in collection_ids
        assert "472c94ae-3113-4e3e-a4dd-a9f4ac7471d4" in collection_ids

    def test_get_collection(self):
        r = self.client.get(
            test.GET_COLLECTION_EP,
            headers=self.auth,
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_TAXII_V20)
        collections_metadata = self.load_json_response(r.data)
        assert collections_metadata["media_types"][0] == "application/vnd.oasis.stix+json; version=2.0"

    def test_get_collection_not_existent(self):
        r = self.client.get(
            test.NON_EXISTENT_COLLECTION_EP,
            headers=self.auth,
        )
        self.assertEqual(r.status_code, 404)

    def test_get_object(self):
        r = self.client.get(
           test.GET_OBJECT_EP + "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111/",
           headers=self.auth,
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        obj = self.load_json_response(r.data)
        assert obj["objects"][0]["id"] == "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111"

    def test_get_objects(self):
        r = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=relationship",
            headers=self.auth,
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        objs = self.load_json_response(r.data)
        assert any(obj["id"] == "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463" for obj in objs["objects"])

        # ------------- BEGIN: test that all returned objects belong to the correct collection ------------- #
        r = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=indicator",
            headers=self.auth,
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        objs = self.load_json_response(r.data)

        # there should be only two indicators in this collection
        self.assertEqual(len(objs["objects"]), 2)
        # check that the returned objects are the ones we expected
        expected_ids = set(['indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f', 'indicator--a932fcc6-e032-176c-126f-cb970a5a1ade'])
        received_ids = set(obj["id"] for obj in objs["objects"])
        self.assertEqual(expected_ids, received_ids)

    def test_add_objects(self):
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle["objects"][0]["id"] = new_id

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
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
            headers=get_header,
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)

        objs = self.load_json_response(r_get.data)
        assert objs["objects"][0]["id"] == new_id

        # ------------- END: get object section ------------- #
        # ------------- BEGIN: get status section ------------- #

        r_get = self.client.get(
            test.API_ROOT_EP + "status/%s/" % status_response["id"],
            headers=self.auth,
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        status_response2 = self.load_json_response(r_get.data)
        assert status_response2["success_count"] == 1

        # ------------- END: get status section ------------- #
        # ------------- BEGIN: get manifest section ------------- #

        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=%s" % new_id,
            headers=self.auth,
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        manifests = self.load_json_response(r_get.data)
        assert manifests["objects"][0]["id"] == new_id
        # ------------- END: end manifest section ------------- #

    def test_client_object_versioning(self):
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        status_response = self.load_json_response(r_post.data)
        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        for i in range(0, 5):
            new_bundle = copy.deepcopy(self.API_OBJECTS_2)
            new_bundle["objects"][0]["id"] = new_id
            new_bundle["objects"][0]["modified"] = common.datetime_to_string_stix(common.get_timestamp())
            r_post = self.client.post(
                test.ADD_OBJECTS_EP,
                data=json.dumps(new_bundle),
                headers=post_header,
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
            headers=get_header,
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
            headers=get_header,
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
            headers=get_header,
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
            headers=get_header,
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
            headers=self.auth,
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        status_response2 = self.load_json_response(r_get.data)
        assert status_response2["success_count"] == 1

        # ------------- END: get status section ------------- #
        # ------------- BEGIN: get manifest section ------------- #

        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=%s" % new_id,
            headers=self.auth,
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
            headers=get_header,
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_STIX_V20)
        bundle = self.load_json_response(r_get.data)

        # none of the objects in the test data set has an added_after date post 1 Jan 2018
        self.assertEqual(0, len(bundle['objects']))

        # ------------- END: test with static data section ------------- #
        # ------------- BEGIN: test with object added via API ------------- #
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.load_json_response(r_post.data)
        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # refetch objects post 1 Jan 2018 - should now have 1 result
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?added_after=2018-01-01T00:00:00Z",
            headers=get_header,
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
            headers=get_header,
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
            headers=get_header,
        )
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.content_type, MEDIA_TYPE_TAXII_V20)

        manifests = self.load_json_response(r_get.data)

        assert all(obj["id"].startswith("marking-definition") for obj in manifests["objects"])
        self.assertEqual(len(manifests["objects"]), 1, "Expected exactly one result")
        # ------------- END: get manifest section 2 ------------- #
        # ------------- BEGIN: get objects section 1 ------------- #
        r_get = self.client.get(
            test.GET_OBJECT_EP + "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da/",
            headers=get_header,
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
            headers=get_header,
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
            headers=get_header,
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
            headers=get_header,
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
            headers=self.auth,
        )
        self.assertEqual(r.status_code, 403)

    def test_get_object_manifest_404(self):
        # note that collection ID does not exist
        r = self.client.get(test.COLLECTIONS_EP + "24042009/manifest/", headers=self.auth)
        self.assertEqual(r.status_code, 404)

    def test_get_object_401(self):
        r = self.client.get(
            test.GET_OBJECT_EP + "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111/",
        )
        self.assertEqual(r.status_code, 401)

    def test_get_object_403(self):
        """note that the 403 code is still being generated at the Collection resource level

           (i.e. we dont have access rights to the collection specified, not just the object)
        """
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "objects/indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f/",
            headers=self.auth,
        )
        self.assertEqual(r.status_code, 403)

    def test_get_object_404(self):
        # TAXII spec allows for a 404 or empty bundle if object is not found
        r = self.client.get(
            test.GET_OBJECT_EP + "malware--cee60c30-a68c-11e3-b0c1-a01aac20d000/",
            headers=self.auth,
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
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = {}
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_STIX_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.assertEqual(r_post.status_code, 401)

    def get_or_add_objects_403(self):
        """note that the 403 code is still being generated at the Collection resource level

          (i.e. we dont have access rights to the collection specified here, not just the object)
        """
        # get_objects()
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "objects/",
            headers=self.auth,
        )
        self.assertEqual(r.status_code, 403)

        # add_objects
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.FORBIDDEN_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.assertEqual(r_post.status_code, 403)

    def test_get_or_add_objects_404(self):
        # get_objects()
        r = self.client.get(
            test.NON_EXISTENT_COLLECTION_EP + "objects/",
            headers=self.auth,
        )
        self.assertEqual(r.status_code, 404)

        # add_objects
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.NON_EXISTENT_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header,
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
                "url-watchlist",
            ],
            "modified": "2016-11-03T12:30:59.000Z",
            "name": "Malicious site hosting downloader",
            "pattern": "[url:value = 'http://yarg.cn/4712']",
            "type": "indicator",
            "valid_from": "2017-01-27T13:51:53.935382Z",
        }

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(malformed_bundle),
            headers=post_header,
        )

        self.assertEqual(r_post.status_code, 422)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)
        error_data = self.load_json_response(r_post.data)
        assert error_data["title"] == "ProcessingError"
        assert error_data["http_status"] == "422"
        assert "While processing supplied content, an error occurred" in error_data["description"]

    def test_get_object_containing_additional_properties(self):
        """tests fix for issue where additional indicator SDO properties such as external_references
        are not being returned correctly"""

        # setup data by adding indicator with valid_until date and external_references
        new_id = "indicator--%s" % uuid.uuid4()
        valid_until = "2018-01-27T13:49:53.935382Z"
        external_references = [{
            "source_name": "capec",
            "external_id": "CAPEC-163",
        }]
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id
        new_bundle["objects"][0]["valid_until"] = valid_until
        new_bundle["objects"][0]["external_references"] = external_references

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )

        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # get the indicator and check the valid_until date and external_references are returned
        r = self.client.get(test.GET_OBJECT_EP + new_id + '/', headers=self.auth)
        self.assertEqual(r.status_code, 200)
        event = self.load_json_response(r.data)
        self.assertEqual(event['objects'][0]['valid_until'], valid_until)
        self.assertEqual(event['objects'][0]['external_references'], external_references)

    def test_get_object_exists_in_multiple_collections(self):
        # setup data by adding indicator with valid_until date and external_references
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )

        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # now also add that identical object to another collection
        r_post = self.client.post(
            test.EMPTY_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header,
        )

        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # ------------- BEGIN: test that all returned objects belong to the correct collection ------------- #
        # now query for that object in one collection and confirm we don't recieve both
        # instances back
        r = self.client.get(
            test.ADD_OBJECTS_EP + new_id + "/",
            headers=self.auth,
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        objs = self.load_json_response(r.data)

        # there should be only one indicator in this collection
        self.assertEqual(len(objs["objects"]), 1)
        # check that the returned object is the one we expected
        self.assertEqual(new_id, objs["objects"][0]["id"])

    def test_object_pagination(self):
        # setup data by adding 100 indicators
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 5 objects in the collection already so add another 95 to make it up to 100
        for i in range(0, 94):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # ------------- BEGIN: test request for subset of objects endpoint ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-10',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-10/100')
        self.assertEqual(len(objs['objects']), 11)

        # ------------- END: test request for subset of objects endpoint ------------- #
        # ------------- BEGIN: test request for more than servers supported page size on objects endpoint ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-100',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)
        objs = self.load_json_response(r.data)

        # should return a maximum of 20 objects as that is what we have set in the server configuration
        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-19/100')
        self.assertEqual(len(objs['objects']), 20)

        # ------------- END: test request for more than servers supported page size on objects endpoint ------------- #
        # ------------- BEGIN: test request for range beyond result set of objects endpoint ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 90-119',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 90-99/100')
        self.assertEqual(len(objs['objects']), 10)

        # ------------- END: test request for range beyond result set of objects endpoint ------------- #
        # ------------- BEGIN: test request for just the first item ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-0',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-0/100')
        self.assertEqual(len(objs['objects']), 1)

        # ------------- END: test request for just the first item ------------- #
        # ------------- BEGIN: test request for one item past the end of the range ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 100-100',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)
        self.assertEqual(r.status_code, 416)

        # ------------- END: test request for one item past the end of the range ------------- #

    def test_manifest_pagination(self):
        # setup data by adding 100 indicators
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 6 items in the manifests collection already so add another 94 to make it up to 100
        for i in range(0, 94):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(r_post.content_type, MEDIA_TYPE_TAXII_V20)

        # ------------- BEGIN: test request for subset of manifests endpoint------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-10',
        }
        r = self.client.get(test.MANIFESTS_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-10/100')
        self.assertEqual(len(objs['objects']), 11)

        # ------------- END: test request for subset of manifests endpoint ------------- #
        # ------------- BEGIN: test request for more than servers supported page size of manifests endpoint------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-100',
        }
        r = self.client.get(test.MANIFESTS_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-19/100')
        self.assertEqual(len(objs['objects']), 20)

        # ------------- END: test request for more than servers supported page size of manifests endpoint ------------- #
        # ------------- BEGIN: test request for range beyond result set of manifests endpoint  ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 90-119',
        }
        r = self.client.get(test.MANIFESTS_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 90-99/100')
        self.assertEqual(len(objs['objects']), 10)

        # ------------- END: test request for range beyond result set of manifests endpoint ------------- #

    def test_collection_pagination(self):
        # setup data by adding additional collections to static data to make the number up to 100
        collections = []
        for i in range(0, 96):
            new_id = "indicator--%s" % uuid.uuid4()
            col = {
                "id": new_id,
                "title": "Test collection",
                "description": "Description for test collection",
                "can_read": True,
                "can_write": True,
                "media_types": [
                    "application/vnd.oasis.stix+json; version=2.0",
                ],
            }
            collections.append(col)

        client = connect_to_client(self.configuration["backend"]["uri"])
        api_root_db = client['trustgroup1']
        api_root_db["collections"].insert_many(collections)

        # ------------- BEGIN: test request for subset of collections endpoint------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-10',
        }
        r = self.client.get(test.COLLECTIONS_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-10/100')
        self.assertEqual(len(objs['collections']), 11)

        # ------------- END: test request for subset of collections endpoint ------------- #
        # ------------- BEGIN: test request for more than servers supported page size of collections endpoint------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-100',
        }
        r = self.client.get(test.COLLECTIONS_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-19/100')
        self.assertEqual(len(objs['collections']), 20)

        # ------------- END: test request for more than servers supported page size of collections endpoint ------------- #
        # ------------- BEGIN: test request for range beyond result set of collections endpoint  ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 90-119',
        }
        r = self.client.get(test.COLLECTIONS_EP, headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers.get('Content-Range'), 'items 90-99/100')
        self.assertEqual(len(objs['collections']), 10)

        # ------------- END: test request for range beyond result set of collections endpoint ------------- #

    def test_version_filtering(self):
        # collection contains 1 indicator with 2 versions.

        # ------------- BEGIN: test request for latest version, should return one result ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
        }
        r = self.client.get(test.GET_COLLECTION_EP + 'objects/', headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(objs['objects']), 1)

        # ------------- END: test request for latest version, should return one result ------------- #
        # ------------- BEGIN: test request for all versions, should return two results ------------- #

        headers = {
            'Authorization': self.auth['Authorization'],
        }
        r = self.client.get(test.GET_COLLECTION_EP + 'objects/?match[version]=all', headers=headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(objs['objects']), 2)

        # ------------- END: test request for all versions, should return two results ------------- #

    def test_add_existing_single_version_object(self):
        new_id = "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9"
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0] = {
            "type": "marking-definition",
            "spec_version": "2.1",
            "created": "2017-01-20T00:00:00.000Z",
            "id": "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",
            "definition": {"tlp": "white"},
            "name": "TLP:WHITE",
            "definition_type": "tlp"
        }

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.auth)
        post_header["Content-Type"] = MEDIA_TYPE_STIX_V20
        post_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V20, r_post.content_type)

        # ------------- END: add object section ------------- #
        # ------------- BEGIN: add object again section ------------- #

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        status_response2 = self.load_json_response(r_post.data)
        self.assertEqual(202, r_post.status_code)
        self.assertEqual(0, status_response2["success_count"])
        self.assertEqual(
            "Unable to process object because identical version exist.",
            status_response2["failures"][0]["message"]
        )

        # ------------- END: add object again section ------------- #
        # ------------- BEGIN: get object section ------------- #

        get_header = copy.deepcopy(self.auth)
        get_header["Accept"] = MEDIA_TYPE_TAXII_V20

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s" % new_id,
            headers=get_header,
        )
        self.assertEqual(200, r_get.status_code)
        objs = self.load_json_response(r_get.data)
        self.assertEqual(1, len(objs["objects"]))
        self.assertEqual(new_id, objs["objects"][0]["id"])
