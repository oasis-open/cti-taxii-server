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
import requests

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

    def __init__(self):
        self.type = "memory"
        self.setUp()


class MongoTestServer(TaxiiTest):

    def __init__(self):
        self.type = "mongo"
        self.setUp()

TestServers = ["memory", "mongo"]

@pytest.fixture(scope="module", params=TestServers)
def backend(request):
    if request.param in request.config.getoption("backends"):
        if request.param == "memory":
            yield MemoryTestServer()
        if request.param == "mongo":
            yield MongoTestServer()
    else:
        yield pytest.skip("skipped")

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

def test_double_taxii(backend, request):
    r = backend.client.get(test.DISCOVERY_EP, headers=backend.headers)

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    server_info = load_json_response(r.data)
    assert server_info["api_roots"][0] == "http://localhost:5000/api1/"

    request.session.save[request.node.name] = r

def test_get_api_root_information(backend, request):
    r = backend.client.get(test.API_ROOT_EP, headers=backend.headers)

    assert r.status_code == 200
    assert r.content_type == MEDIA_TYPE_TAXII_V21
    api_root_metadata = load_json_response(r.data)
    assert api_root_metadata["title"] == "Malware Research Group"

    request.session.save[request.node.name] = r
