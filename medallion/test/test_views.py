import copy
import json
import sys
import unittest
import uuid
from base64 import b64encode

import six

from medallion import (create_app, test)
from medallion.test import config
from medallion.test.base_test import TaxiiTest
from medallion.test.data.initialize_mongodb import reset_db
from medallion.views import MEDIA_TYPE_STIX_V20, MEDIA_TYPE_TAXII_V20

if sys.version_info < (3, 3, 0):
    import mock
else:
    from unittest import mock

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


class TestTAXIIServerWithMockBackend(unittest.TestCase):

    def setUp(self):
        reset_db()
        self.configuration = config.mongodb_config()
        self.configuration['backend']['default_page_size'] = 20

        self.app = create_app(self.configuration)

        self.app_context = self.app.app_context()
        self.app_context.push()

        self.client = self.app.test_client()
        self.auth = {'Authorization': 'Token abc123'}

    def tearDown(self):
        self.app_context.pop()

    @staticmethod
    def load_json_response(response):
        if isinstance(response, bytes):
            response = response.decode()
        io = six.StringIO(response)
        return json.load(io)

    @mock.patch('medallion.backends.base.Backend')
    def test_responses_include_range_headers(self, mock_backend):
        """ This test confirms that the expected endpoints are returning the Accept-Ranges
        HTTP header as per section 3.4 of the specification """

        self.app.medallion_backend = mock_backend()

        # ------------- BEGIN: test collection endpoint ------------- #
        mock_backend.return_value.get_collections.return_value = (10, {'collections': []})
        r = self.client.get(test.COLLECTIONS_EP, headers=self.auth)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_TAXII_V20)
        self.assertIsNotNone(r.headers.get('Accept-Ranges', None))

        # ------------- END: test collection endpoint ------------- #
        # ------------- BEGIN: test manifests endpoint ------------- #
        mock_backend.return_value.get_object_manifest.return_value = (10, {'objects': []})
        r = self.client.get(
            test.MANIFESTS_EP,
            headers=self.auth,
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_TAXII_V20)
        self.assertIsNotNone(r.headers.get('Accept-Ranges', None))

        # ------------- END: test manifests endpoint ------------- #
        # ------------- BEGIN: test objects endpoint ------------- #
        mock_backend.return_value.get_objects.return_value = (10, {'objects': []})
        r = self.client.get(
            test.GET_OBJECTS_EP,
            headers=self.auth,
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        self.assertIsNotNone(r.headers.get('Accept-Ranges', None))

        # ------------- END: test objects endpoint ------------- #

    @mock.patch('medallion.backends.base.Backend')
    def test_response_status_headers_for_large_responses(self, mock_backend):
        """ This test confirms that the expected endpoints are returning the Accept-Ranges and
        Content-Range headers as well as a HTTP 206 for large responses. Refer section 3.4.3
        of the specification """

        self.app.medallion_backend = mock_backend()
        page_size = self.configuration['backend']['default_page_size']

        # ------------- BEGIN: test small result set - no range required ------------- #
        # set up mock backend to return test objects
        response = copy.deepcopy(BUNDLE)
        for i in range(0, 10):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(API_OBJECT)
            obj['id'] = new_id
            response['objects'].append(obj)
        mock_backend.return_value.get_objects.return_value = (10, response)

        r = self.client.get(test.GET_OBJECT_EP, headers=self.auth)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        self.assertIsNotNone(r.headers.get('Accept-Ranges', None))

        # ------------- END: test small result set ------------- #
        # ------------- BEGIN: test large result set ------------- #
        # set up mock backend to return larger set of test objects
        response = copy.deepcopy(BUNDLE)
        for i in range(0, 20):
            new_id = "indicator--%s" % uuid.uuid4()
            obj = copy.deepcopy(API_OBJECT)
            obj['id'] = new_id
            response['objects'].append(obj)
        mock_backend.return_value.get_objects.return_value = (100, response)

        r = self.client.get(test.GET_OBJECT_EP, headers=self.auth)
        objs = self.load_json_response(r.data)

        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.content_type, MEDIA_TYPE_STIX_V20)
        self.assertIsNotNone(r.headers.get('Accept-Ranges', None))
        self.assertIsNotNone(r.headers.get('Content-Range', None))
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-{}/100'.format(page_size - 1))
        self.assertEqual(len(objs['objects']), page_size)

        # ------------- END: test large result set ------------- #

    @mock.patch('medallion.backends.base.Backend')
    def test_bad_range_request(self, mock_backend):
        """ This test should return a HTTP 416 for a range request that cannot be satisfied. Refer 3.4.2 in
        the TAXII specification. """

        self.app.medallion_backend = mock_backend()

        # Set up the backend to return the total number of results = 10. Actual results not important
        # for this test so an empty set is returned.
        mock_backend.return_value.get_objects.return_value = (10, {'objects': []})

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 100-199',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)

        self.assertEqual(416, r.status_code)
        self.assertEqual(r.headers.get('Content-Range'), 'items */10')

    @mock.patch('medallion.backends.base.Backend')
    def test_invalid_range_request(self, mock_backend):
        """ This test should return a HTTP 400 with a message that the request contains a malformed
        range request header. """

        self.app.medallion_backend = mock_backend()

        # Set up the backend to return the total number of results = 10. Actual results not important
        # for this test so an empty set is returned.
        mock_backend.return_value.get_objects.return_value = (10, {'objects': []})

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items x-199',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)

        self.assertEqual(400, r.status_code)

    @mock.patch('medallion.backends.base.Backend')
    def test_content_range_header_empty_response(self, mock_backend):
        """ This test checks that the Content-Range header is correctly formed for queries that return
        an empty (zero record) response. """
        self.app.medallion_backend = mock_backend()

        # Set up the backend to return the total number of results = 0.
        mock_backend.return_value.get_objects.return_value = (0, {'objects': []})

        headers = {
            'Authorization': self.auth['Authorization'],
            'Range': 'items 0-10',
        }
        r = self.client.get(test.GET_OBJECT_EP, headers=headers)

        self.assertEqual(206, r.status_code)
        self.assertEqual(r.headers.get('Content-Range'), 'items 0-0/0')


class TestAuth(TaxiiTest):
    type = "memory"

    @classmethod
    def setUpClass(cls):
        cls.username, cls.password = "admin", "Password0"

    def test_auth_failure(self):
        with self.app.test_client() as client:
            response = client.get('/routes')
            self.assertEqual(response.status_code, 401)

    def test_login(self):
        with self.app.test_client() as client:
            response = client.post(test.LOGIN, method='POST',
                                   json={'username': self.username,
                                         'password': self.password})
            self.assertEqual(response.status_code, 200)
            self.assertIn('access_token', response.json)

            response = client.get('/routes',
                                  headers={'Authorization': 'JWT ' + response.json['access_token']})
            self.assertEqual(response.status_code, 200)

    def test_login_failure(self):
        with self.app.test_client() as client:
            response = client.post(test.LOGIN,
                                   json={'username': self.username + 'x',
                                         'password': self.password + 'y'})
            self.assertEqual(response.status_code, 401)

    def test_api_key_auth_failure(self):
        with self.app.test_client() as client:
            response = client.get("/routes",
                                  headers={'Authorization': 'Basic ' + b64encode("user:invalid")})
            self.assertEqual(response.headers.get('WWW-Authenticate'),
                             'Basic realm="Authentication Required"')

    def test_basic_auth_failure(self):
        with self.app.test_client() as client:
            response = client.get("/routes",
                                  headers={'Authorization': 'Token xxxxxxx'})
            self.assertEqual(response.headers.get('WWW-Authenticate'),
                             'Token realm="Authentication Required"')


if __name__ == "__main__":
    unittest.main()
