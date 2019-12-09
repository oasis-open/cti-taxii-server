import copy
import json
import uuid

import six

from medallion import common, test
from medallion.views import MEDIA_TYPE_TAXII_V21

from .base_test import TaxiiTest


class TestTAXIIServerWithMongoDBBackend(TaxiiTest):
    type = "mongo"

    @staticmethod
    def load_json_response(response):
        if isinstance(response, bytes):
            response = response.decode()
        io = six.StringIO(response)
        return json.load(io)

    def test_server_discovery(self):
        r = self.client.get(test.DISCOVERY_EP, headers=self.headers)

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        server_info = self.load_json_response(r.data)
        self.assertEqual("Some TAXII Server", server_info["title"])
        self.assertEqual(3, len(server_info["api_roots"]))
        self.assertEqual("http://localhost:5000/trustgroup1/", server_info["api_roots"][2])

    def test_get_api_root_information(self):
        r = self.client.get(test.API_ROOT_EP, headers=self.headers)

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        api_root_metadata = self.load_json_response(r.data)
        self.assertEqual("Malware Research Group", api_root_metadata["title"])

    def test_get_api_root_information_not_existent(self):
        r = self.client.get("/trustgroup2/", headers=self.headers)
        self.assertEqual(404, r.status_code)

    def test_get_collections(self):
        r = self.client.get(test.COLLECTIONS_EP, headers=self.headers)

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        collections_metadata = self.load_json_response(r.data)
        collections_metadata = sorted(collections_metadata["collections"], key=lambda x: x["id"])
        collection_ids = [cm["id"] for cm in collections_metadata]

        self.assertEqual(4, len(collection_ids))
        self.assertIn("52892447-4d7e-4f70-b94d-d7f22742ff63", collection_ids)
        self.assertIn("91a7b528-80eb-42ed-a74d-c6fbd5a26116", collection_ids)
        self.assertIn("64993447-4d7e-4f70-b94d-d7f33742ee63", collection_ids)
        self.assertIn("472c94ae-3113-4e3e-a4dd-a9f4ac7471d4", collection_ids)

    def test_get_collection_404(self):
        # note that api root "carbon1" is nonexistent
        r = self.client.get("/carbon1/collections/12345678-1234-1234-1234-123456789012/", headers=self.headers)
        self.assertEqual(404, r.status_code)

    def test_get_collection(self):
        r = self.client.get(
            test.GET_COLLECTION_EP,
            headers=self.headers,
        )

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        collections_metadata = self.load_json_response(r.data)
        self.assertIn("application/stix+json;version=2.1", collections_metadata["media_types"])

    def test_get_collection_not_existent(self):
        r = self.client.get(
            test.NON_EXISTENT_COLLECTION_EP,
            headers=self.headers,
        )
        self.assertEqual(404, r.status_code)

    def test_get_object(self):
        r = self.client.get(
           test.GET_OBJECT_EP + "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec/",
           headers=self.headers,
        )

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        obj = self.load_json_response(r.data)
        self.assertEqual(1, len(obj["objects"]))
        self.assertEqual("malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec", obj["objects"][0]["id"])

    def test_get_objects(self):
        r = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=relationship",
            headers=self.headers,
        )

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        objs = self.load_json_response(r.data)
        self.assertTrue(any(obj["id"] == "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463" for obj in objs["objects"]))

        # ------------- BEGIN: test that all returned objects belong to the correct collection ------------- #
        r = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=indicator",
            headers=self.headers,
        )

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        objs = self.load_json_response(r.data)

        # there should be only two indicators in this collection
        self.assertEqual(2, len(objs["objects"]))
        # check that the returned objects are the ones we expected
        expected_ids = set(['indicator--6770298f-0fd8-471a-ab8c-1c658a46574e', 'indicator--cd981c25-8042-4166-8945-51178443bdac'])
        received_ids = set(obj["id"] for obj in objs["objects"])
        self.assertEqual(expected_ids, received_ids)

    def test_add_objects(self):
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle["objects"][0]["id"] = new_id

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        status_response = self.load_json_response(r_post.data)
        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- END: add object section ------------- #
        # ------------- BEGIN: get object section ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s" % new_id,
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        objs = self.load_json_response(r_get.data)
        self.assertEqual(new_id, objs["objects"][0]["id"])

        # ------------- END: get object section ------------- #
        # ------------- BEGIN: get status section ------------- #

        r_get = self.client.get(
            test.API_ROOT_EP + "status/%s/" % status_response["id"],
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        status_response2 = self.load_json_response(r_get.data)
        self.assertEqual(2, status_response2["success_count"])

        # ------------- END: get status section ------------- #
        # ------------- BEGIN: get manifest section ------------- #

        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=%s" % new_id,
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)
        self.assertEqual(new_id, manifests["objects"][0]["id"])
        # ------------- END: end manifest section ------------- #

    def test_add_existing_single_version_object(self):
        new_id = "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9"
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        del new_bundle["objects"][0]

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- END: add object section ------------- #
        # ------------- BEGIN: add object again section ------------- #

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        status_response2 = self.load_json_response(r_post.data)
        self.assertEqual(r_post.status_code, 202)
        self.assertEqual(status_response2["success_count"], 0)
        self.assertEqual(
            "Unable to process object because an identical entry already exists in collection '91a7b528-80eb-42ed-a74d-c6fbd5a26116'.",
            status_response2["failures"][0]["message"]
        )

        # ------------- END: add object again section ------------- #
        # ------------- BEGIN: get object section ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s" % new_id,
            headers=self.headers,
        )
        self.assertEqual(r_get.status_code, 200)
        objs = self.load_json_response(r_get.data)
        self.assertEqual(1, len(objs["objects"]))
        self.assertEqual(new_id, objs["objects"][0]["id"])

    def test_client_object_versioning(self):
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        # ------------- BEGIN: add object section ------------- #

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        status_response = self.load_json_response(r_post.data)
        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

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
        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- END: add object section ------------- #
        # ------------- BEGIN: get object section 1 ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "all"),
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        objs = self.load_json_response(r_get.data)
        self.assertEqual(new_id, objs["objects"][0]["id"])
        self.assertEqual(new_bundle["objects"][0]["modified"], objs["objects"][-1]["modified"])

        # ------------- END: get object section 1 ------------- #
        # ------------- BEGIN: get object section 2 ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "first"),
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        objs = self.load_json_response(r_get.data)
        self.assertEqual(new_id, objs["objects"][0]["id"])
        self.assertEqual(objs["objects"][0]["modified"], "2017-01-27T13:49:53.935Z")

        # ------------- END: get object section 2 ------------- #
        # ------------- BEGIN: get object section 3 ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "last"),
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        objs = self.load_json_response(r_get.data)
        self.assertEqual(new_id, objs["objects"][0]["id"])
        self.assertEqual(new_bundle["objects"][0]["modified"], objs["objects"][0]["modified"])

        # ------------- END: get object section 3 ------------- #
        # ------------- BEGIN: get object section 4 ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=%s&match[version]=%s"
            % (new_id, "2017-01-27T13:49:53.935Z"),
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        objs = self.load_json_response(r_get.data)
        self.assertEqual(new_id, objs["objects"][0]["id"])
        self.assertEqual("2017-01-27T13:49:53.935Z", objs["objects"][0]["modified"])

        # ------------- END: get object section 4 ------------- #
        # ------------- BEGIN: get status section ------------- #

        r_get = self.client.get(
            test.API_ROOT_EP + "status/%s/" % status_response["id"],
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        status_response2 = self.load_json_response(r_get.data)
        self.assertEqual(1, status_response2["success_count"])

        # ------------- END: get status section ------------- #
        # ------------- BEGIN: get manifest section ------------- #

        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=%s" % new_id,
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)

        self.assertEqual(new_id, manifests["objects"][0]["id"])
        self.assertTrue(any(version["version"] == new_bundle["objects"][0]["modified"] for version in manifests["objects"]))
        # ------------- END: get manifest section ------------- #

    def test_added_after_filtering(self):
        # ------------- BEGIN: test with static data section ------------- #

        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?added_after=2018-01-01T00:00:00Z",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)
        bundle = self.load_json_response(r_get.data)

        # none of the objects in the test data set has an added_after date post 1 Jan 2018
        self.assertEqual({}, bundle)

        # ------------- END: test with static data section ------------- #
        # ------------- BEGIN: test with object added via API ------------- #
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.load_json_response(r_post.data)
        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # refetch objects post 1 Jan 2018 - should now have 2 results
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?added_after=2018-01-01T00:00:00Z",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)
        bundle = self.load_json_response(r_get.data)

        self.assertEqual(2, len(bundle['objects']))
        self.assertTrue(any(obj["id"] == new_id for obj in bundle['objects']))

    def test_marking_defintions(self):

        # ------------- BEGIN: get manifest section 1 ------------- #
        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[id]=marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)
        self.assertEqual("marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da", manifests["objects"][0]["id"])
        self.assertEqual(1, len(manifests["objects"]), "Expected exactly one result")
        # ------------- END: get manifest section 1 ------------- #
        # ------------- BEGIN: get manifest section 2 ------------- #
        r_get = self.client.get(
            test.GET_ADD_COLLECTION_EP + "manifest/?match[type]=marking-definition",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)

        self.assertTrue(all(obj["id"].startswith("marking-definition") for obj in manifests["objects"]))
        self.assertEqual(1, len(manifests["objects"]), "Expected exactly one result")
        # ------------- END: get manifest section 2 ------------- #
        # ------------- BEGIN: get objects section 1 ------------- #
        r_get = self.client.get(
            test.GET_OBJECT_EP + "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da/",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)

        self.assertEqual("marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da", manifests["objects"][0]["id"])
        self.assertEqual(1, len(manifests["objects"]), "Expected exactly one result")
        # ------------- END: get objects section 1 ------------- #
        # ------------- BEGIN: get objects section 2 ------------- #
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=marking-definition",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)

        self.assertTrue(all(obj["id"].startswith("marking-definition") for obj in manifests["objects"]))
        self.assertEqual(1, len(manifests["objects"]), "Expected exactly one result")
        # ------------- END: get objects section 2 ------------- #
        # ------------- BEGIN: get objects section 3 ------------- #
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[type]=marking-definition,malware",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)

        self.assertTrue(all((obj["id"].startswith("marking-definition") or obj["id"].startswith("malware")) for obj in manifests["objects"]))
        self.assertEqual(2, len(manifests["objects"]), "Expected exactly two results")
        # ------------- END: get objects section 3 ------------- #
        # ------------- BEGIN: get objects section 4 ------------- #
        r_get = self.client.get(
            test.GET_OBJECTS_EP + "?match[id]=marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
            headers=self.headers,
        )
        self.assertEqual(200, r_get.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_get.content_type)

        manifests = self.load_json_response(r_get.data)

        self.assertEqual("marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da", manifests["objects"][0]["id"])
        self.assertEqual(1, len(manifests["objects"]), "Expected exactly one result")
        # ------------- END: get objects section 4 ------------- #

    def test_get_collections_401(self):
        r = self.client.get(test.COLLECTIONS_EP)
        self.assertEqual(401, r.status_code)

    """get_collections 403 - not implemented. Medallion TAXII implementation does not have
    access control for Collection resource metadata"""

    def test_get_collections_404(self):
        # note that api root "carbon1" is nonexistent
        r = self.client.get("/carbon1/collections/", headers=self.headers)
        self.assertEqual(404, r.status_code)

    def test_get_status_401(self):
        # non existent ID but shouldnt matter as the request should never pass login
        r = self.client.get(test.API_ROOT_EP + "status/2223/")
        self.assertEqual(401, r.status_code)

    """get_status 403 - not implemented. Medallion TAXII implementation does not have
     access control for Status resources"""

    def test_get_status_404(self):
        r = self.client.get(test.API_ROOT_EP + "status/22101993/", headers=self.headers)
        self.assertEqual(404, r.status_code)

    def test_get_object_manifest_401(self):
        # non existent collection ID but shouldnt matter as the request should never pass login
        r = self.client.get(test.COLLECTIONS_EP + "24042009/manifest/")
        self.assertEqual(401, r.status_code)

    def test_get_object_manifest_403(self):
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "manifest/",
            headers=self.headers,
        )
        self.assertEqual(403, r.status_code)

    def test_get_object_manifest_404(self):
        # note that collection ID does not exist
        r = self.client.get(test.COLLECTIONS_EP + "24042009/manifest/", headers=self.headers)
        self.assertEqual(404, r.status_code)

    def test_get_object_401(self):
        r = self.client.get(
            test.GET_OBJECT_EP + "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111/",
        )
        self.assertEqual(401, r.status_code)

    def test_get_object_403(self):
        """note that the 403 code is still being generated at the Collection resource level

           (i.e. we dont have access rights to the collection specified, not just the object)
        """
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "objects/indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f/",
            headers=self.headers,
        )
        self.assertEqual(403, r.status_code)

    def test_get_object_404(self):
        # TAXII spec allows for a 404 or empty bundle if object is not found
        r = self.client.get(
            test.GET_OBJECT_EP + "malware--cee60c30-a68c-11e3-b0c1-a01aac20d000/",
            headers=self.headers,
        )
        objs = self.load_json_response(r.data)

        if r.status_code == 200:
            self.assertEqual(0, len(objs["objects"]))
        else:
            self.assertEqual(404, r.status_code)

    def test_get_or_add_objects_401(self):
        # note that no credentials are supplied with requests

        # get_objects()
        r = self.client.get(test.GET_OBJECT_EP)
        self.assertEqual(401, r.status_code)

        # add_objects()
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.headers)
        post_header.pop("Authorization")
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.assertEqual(401, r_post.status_code)

    def get_or_add_objects_403(self):
        """note that the 403 code is still being generated at the Collection resource level

          (i.e. we dont have access rights to the collection specified here, not just the object)
        """
        # get_objects()
        r = self.client.get(
            test.FORBIDDEN_COLLECTION_EP + "objects/",
            headers=self.headers,
        )
        self.assertEqual(403, r.status_code)

        # add_objects
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.FORBIDDEN_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.assertEqual(403, r_post.status_code)

    def test_get_or_add_objects_404(self):
        # get_objects()
        r = self.client.get(
            test.NON_EXISTENT_COLLECTION_EP + "objects/",
            headers=self.headers,
        )
        self.assertEqual(404, r.status_code)

        # add_objects
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.NON_EXISTENT_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header,
        )
        self.assertEqual(404, r_post.status_code)

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

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(malformed_bundle),
            headers=post_header,
        )

        self.assertEqual(422, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)
        error_data = self.load_json_response(r_post.data)
        self.assertEqual("ProcessingError", error_data["title"])
        self.assertEqual("422", error_data["http_status"])
        self.assertIn("While processing supplied content, an error occurred", error_data["description"])

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

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # get the indicator and check the valid_until date and external_references are returned
        r = self.client.get(test.GET_OBJECT_EP + new_id + '/', headers=self.headers)
        self.assertEqual(200, r.status_code)
        event = self.load_json_response(r.data)
        self.assertEqual(valid_until, event['objects'][0]['valid_until'])
        self.assertEqual(external_references, event['objects'][0]['external_references'])

    def test_get_object_exists_in_multiple_collections(self):
        # setup data by adding indicator with valid_until date and external_references
        new_id = "indicator--%s" % uuid.uuid4()
        new_bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_bundle["objects"][0]["id"] = new_id

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(new_bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # now also add that identical object to another collection
        r_post = self.client.post(
            test.EMPTY_COLLECTION_EP + "objects/",
            data=json.dumps(new_bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- BEGIN: test that all returned objects belong to the correct collection ------------- #
        # now query for that object in one collection and confirm we don't recieve both
        # instances back
        r = self.client.get(
            test.ADD_OBJECTS_EP + new_id + "/",
            headers=self.headers,
        )

        self.assertEqual(200, r.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r.content_type)
        objs = self.load_json_response(r.data)

        # there should be only one indicator in this collection
        self.assertEqual(1, len(objs["objects"]))
        # check that the returned object is the one we expected
        self.assertEqual(new_id, objs["objects"][0]["id"])

    def test_object_pagination_regular_request(self):
        # setup data by adding 100 indicators
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 5 objects in the collection already so add another 95 to make it up to 100
        for i in range(0, 94):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- BEGIN: test request for subset of objects endpoint ------------- #
        r = self.client.get(test.GET_OBJECT_EP + "?limit=11", headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(11, len(objs['objects']))
        self.assertIn("next", objs)
        self.assertEqual(True, objs["more"])
        # ------------- END: test request for subset of objects endpoint ------------- #

    def test_object_pagination_past_server_limit(self):
        # setup data by adding 100 indicators
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 5 objects in the collection already so add another 95 to make it up to 100
        for i in range(0, 94):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------ BEGIN: test request for more than servers supported page size on objects endpoint ------------ #
        r = self.client.get(test.GET_OBJECT_EP + "?limit=101", headers=self.headers)
        objs = self.load_json_response(r.data)

        # should return a maximum of 20 objects as that is what we have set in the server configuration
        self.assertEqual(200, r.status_code)
        self.assertEqual(20, len(objs['objects']))
        self.assertIn("next", objs)
        self.assertEqual(True, objs["more"])
        # ------------ END: test request for more than servers supported page size on objects endpoint ------------ #

    def test_object_pagination_bad_limit_value_400(self):
        r = self.client.get(test.GET_OBJECT_EP + "?limit=-20", headers=self.headers)
        self.assertEqual(400, r.status_code)

    def test_object_pagination_just_one(self):
        # setup data by adding 100 indicators
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 5 objects in the collection already so add another 95 to make it up to 100
        for i in range(0, 94):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- BEGIN: test request for just the first item ------------- #
        r = self.client.get(test.GET_OBJECT_EP + "?limit=1", headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(1, len(objs['objects']))
        self.assertIn("next", objs)
        self.assertEqual(True, objs["more"])
        # ------------- END: test request for just the first item ------------- #

    def test_object_pagination_changing_params_400(self):
        # setup data by adding 100 indicators
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 5 objects in the collection already so add another 95 to make it up to 100
        for i in range(0, 46):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        for i in range(0, 46):
            new_id = "foo-bar--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            obj['type'] = 'foo-bar'
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- BEGIN: test request for the first page ------------- #
        r = self.client.get(test.GET_OBJECT_EP + "?limit=15&match[type]=indicator", headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(15, len(objs['objects']))
        self.assertTrue(all(obj["type"] == "indicator" for obj in objs["objects"]))
        self.assertIn("next", objs)
        self.assertEqual(True, objs["more"])
        # ------------- END: test request for the first page ------------- #

        # ------------- BEGIN: test request with subsequent page, params changed ------------- #
        r = self.client.get(test.GET_OBJECT_EP + "?limit=15&next=%s&match[type]=indicator,foo-bar" % objs["next"], headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(400, r.status_code)
        self.assertNotIn("objects", objs)
        self.assertNotIn("next", objs)
        self.assertNotIn("more", objs)
        # ------------- END: test request with subsequent page, params changed ------------- #

    def test_object_pagination_whole_task(self):
        # setup data by adding 100 indicators + the marking-definition in self.API_OBJECTS_2
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 5 objects in the collection already so add another 95 to make it up to 101
        for i in range(0, 94):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )
        r_status = self.load_json_response(r_post.data)
        self.assertEqual(96, r_status["success_count"])

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- BEGIN: test request for the whole list of objects ------------- #
        r = self.client.get(test.GET_OBJECT_EP + "?limit=10", headers=self.headers)
        objs = self.load_json_response(r.data)
        object_count = 10

        self.assertEqual(200, r.status_code)
        self.assertEqual(object_count, len(objs['objects']))
        self.assertIn("next", objs)
        self.assertEqual(True, objs["more"])
        next_id = objs["next"]

        while objs["more"] is True:
            r = self.client.get(test.GET_OBJECT_EP + "?limit=10&next=%s" % next_id, headers=self.headers)
            objs = self.load_json_response(r.data)

            self.assertEqual(200, r.status_code)
            if objs["more"] is True:
                self.assertEqual(10, len(objs['objects']))
                self.assertIn("next", objs)
                object_count += 10
            else:
                self.assertEqual(1, len(objs['objects']))
                self.assertNotIn("next", objs)
                object_count += 1
        # ------------- END: test request for the whole list of objects ------------- #

        r = self.client.get(test.GET_OBJECT_EP + "?limit=10&next=%s" % next_id, headers=self.headers)
        self.assertEqual(400, r.status_code)
        self.assertEqual(101, object_count)

    def test_manifest_pagination(self):
        # setup data by adding 100 indicators
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        # 6 items in the manifests collection already so add another 94 to make it up to 100
        for i in range(0, 94):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- BEGIN: test request for subset of manifests endpoint------------- #

        r = self.client.get(test.MANIFESTS_EP + "?limit=11", headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(11, len(objs['objects']))
        self.assertEqual(True, objs['more'])

        # ------------- END: test request for subset of manifests endpoint ------------- #
        # ------------- BEGIN: test request for more than servers supported page size of manifests endpoint------------- #

        r = self.client.get(test.MANIFESTS_EP + "?limit=20", headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(20, len(objs['objects']))

        # ------------- END: test request for more than servers supported page size of manifests endpoint ------------- #

    def test_version_filtering(self):
        # collection contains 7 objects, one indicator contains 2 additional versions

        # ------------- BEGIN: test request for latest version, should return five results ------------- #

        r = self.client.get(test.OBJECTS_EP, headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(5, len(objs['objects']))

        # ------------- END: test request for latest version, should return five results ------------- #
        # ------------- BEGIN: test request for all versions, should return seven results ------------- #

        r = self.client.get(test.OBJECTS_EP + '?match[version]=all', headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(7, len(objs['objects']))

        # ------------- END: test request for all versions, should return seven results ------------- #

    def test_object_versions(self):
        # ------------- BEGIN: test request for object versions, should return three results ------------- #
        r = self.client.get(test.OBJECTS_EP + "indicator--6770298f-0fd8-471a-ab8c-1c658a46574e/versions/", headers=self.headers)
        objs = self.load_json_response(r.data)

        self.assertEqual(200, r.status_code)
        self.assertEqual(3, len(objs['versions']))

        # ------------- END: test request for object versions, should return three results ------------- #

    def test_delete_object(self):

        # setup data by adding 3 versions of an indicator to collection
        bundle = copy.deepcopy(self.API_OBJECTS_2)
        new_id = "indicator--%s" % uuid.uuid4()
        new_mod_times = ["2017-01-27T13:49:53.935Z", "2018-06-27T13:49:53.000Z", "2019-01-27T13:49:53.444Z"]
        for i in range(0, 3):
            obj = copy.deepcopy(bundle['objects'][0])
            obj['id'] = new_id
            obj['modified'] = new_mod_times[i]
            bundle['objects'].append(obj)

        post_header = copy.deepcopy(self.headers)
        post_header.update(self.content_type_header)

        r_post = self.client.post(
            test.ADD_OBJECTS_EP,
            data=json.dumps(bundle),
            headers=post_header,
        )

        self.assertEqual(202, r_post.status_code)
        self.assertEqual(MEDIA_TYPE_TAXII_V21, r_post.content_type)

        # ------------- BEGIN: test request for object deletion, should return 200 ------------- #
        r = self.client.delete(test.OBJECTS_EP + "%s/?match[version]=all" % new_id, headers=self.headers)
        self.assertEqual(200, r.status_code)
        # ------------- END: test request for object deletion, should return 200 ------------- #

        # ------------- BEGIN: test request getting deleted object returns 404 ------------- #
        r = self.client.get(test.OBJECTS_EP + "%s/" % new_id, headers=self.headers)
        objs = self.load_json_response(r.data)
        if r.status_code == 200:
            self.assertEqual(0, len(objs["objects"]))
        else:
            self.assertEqual(404, r.status_code)
        # ------------- END: test request getting deleted object returns 404 ------------- #

        # ------------- BEGIN: test request getting deleted object manifest returns 404 ------------- #
        r = self.client.get(
            test.MANIFESTS_EP + "?match[id]=%s&match[version]=all" % new_id,
            headers=self.headers,
        )
        objs = self.load_json_response(r.data)
        if r.status_code == 200:
            self.assertEqual(0, len(objs["objects"]))
        else:
            self.assertEqual(404, r.status_code)
        # ------------- END: test request getting deleted object manifest returns 404 ------------- #

        # ------------- BEGIN: test request getting deleted object manifest returns 404 ------------- #
        r = self.client.get(
            test.OBJECTS_EP + "%s/versions/" % new_id,
            headers=self.headers,
        )
        objs = self.load_json_response(r.data)
        if r.status_code == 200:
            self.assertEqual(0, len(objs["versions"]))
        else:
            self.assertEqual(404, r.status_code)
        # ------------- END: test request getting deleted object manifest returns 404 ------------- #
