import base64
import os

from medallion import connect_to_backend, register_blueprints, set_config
from medallion.common import (
    APPLICATION_INSTANCE, get_application_instance_config_values
)
from medallion.test.data.initialize_mongodb import reset_db


class TaxiiTest():
    type = None
    DATA_FILE = os.path.join(
        os.path.dirname(__file__), "data", "default_data.json",
    )
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

    no_config = {}

    config_no_taxii = {
        "backend": {
            "module_class": "MemoryBackend",
            "filename": DATA_FILE,
        },
        "users": {
            "admin": "Password0",
        },
    }

    config_no_auth = {
        "backend": {
            "module_class": "MemoryBackend",
            "filename": DATA_FILE,
        },
        "taxii": {
            "max_page_size": 20,
        },
    }

    config_no_backend = {
        "users": {
            "admin": "Password0",
        },
        "taxii": {
            "max_page_size": 20,
        },
    }

    memory_config = {
        "backend": {
            "module_class": "MemoryBackend",
            "filename": DATA_FILE,
        },
        "users": {
            "admin": "Password0",
        },
        "taxii": {
            "max_page_size": 20,
        },
    }

    mongodb_config = {
        "backend": {
            "module_class": "MongoBackend",
            "uri": "mongodb://127.0.0.1:27017/",
        },
        "users": {
            "root": "example",
        },
        "taxii": {
            "max_page_size": 20,
        },
    }

    def setUp(self, start_threads=True):
        self.__name__ = self.type
        self.app = APPLICATION_INSTANCE
        self.app_context = APPLICATION_INSTANCE.app_context()
        self.app_context.push()
        self.app.testing = True
        if(not self.app.blueprints):
            register_blueprints(self.app)
        if self.type == "mongo":
            reset_db(self.mongodb_config["backend"]["uri"])
            self.configuration = self.mongodb_config
        elif self.type == "memory":
            self.configuration = self.memory_config
        elif self.type == "memory_no_config":
            self.configuration = self.no_config
        elif self.type == "no_taxii":
            self.configuration = self.config_no_taxii
        elif self.type == "no_auth":
            self.configuration = self.config_no_auth
        elif self.type == "no_backend":
            self.configuration = self.config_no_backend
        else:
            raise RuntimeError("Unknown backend!")
        set_config(self.app, "backend", self.configuration)
        set_config(self.app, "users", self.configuration)
        set_config(self.app, "taxii", self.configuration)
        if not start_threads:
            self.app.backend_config["run_cleanup_threads"] = False
        APPLICATION_INSTANCE.medallion_backend = connect_to_backend(get_application_instance_config_values(APPLICATION_INSTANCE, "backend"))
        self.client = APPLICATION_INSTANCE.test_client()
        if self.type == "memory_no_config" or self.type == "no_auth":
            encoded_auth = "Basic " + \
                base64.b64encode(b"user:pass").decode("ascii")
        elif self.type == "mongo":
            encoded_auth = "Basic " + \
                base64.b64encode(b"root:example").decode("ascii")
        else:
            encoded_auth = "Basic " + \
                base64.b64encode(b"admin:Password0").decode("ascii")
        self.headers = {"Accept": "application/taxii+json;version=2.1", "Authorization": encoded_auth}
        self.post_headers = {
            "Content-Type": "application/taxii+json;version=2.1",
            "Accept": "application/taxii+json;version=2.1",
            "Authorization": encoded_auth
        }

    def tearDown(self):
        self.app_context.pop()
