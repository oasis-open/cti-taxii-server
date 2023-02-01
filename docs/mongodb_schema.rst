
Design of the TAXII Server Mongo DB Schema for *medallion*
==========================================================

As *medallion* is a prototype TAXII server implementation, the schema design for a Mongo DB is relatively straightforward.

Each Mongo database contains one or more collections.  The term "collection" in Mongo DBs is similar to the concept of a table in a relational database.  Collections contain "documents", somewhat analogous to table rows.

It is unfortunate that the term "collection" is also used to signify something unrelated in the TAXII specification.  We will use the phrase "taxii collection" to distinguish them.

You can initialize the database with content by specifying a JSON file in the backend section of the medallion configuration.  The JSON file containing TAXII server content must have a particular structure.  Refer to medallion/test/data/default_data.json for an example of the required structure.

An example configuration:

.. code-block:: json

    {
         "backend": {
            "module_class": "MongoBackend",
            "uri": "<Mongo DB server url, e.g. mongodb://localhost:27017/>",
            "filename": "<path to json file with initial data>"
         }
    }

.. important::
    To avoid accidentally deleting data, the Mongo backend will check whether the database appears to have already been initialized.  If so, it will not change anything.  To override the safety check and always reinitialize the database, add another backend setting: ``"clear_db": true``.

The discovery database
----------------------

Basic metadata is contained in the mongo database named **discovery_database**.  The discovery_database contains two collections:

**discovery_information** should only contain only one "document", which is the discovery information that would be returned from the Discovery endpoint.  Here is the document from the example database.

.. code-block:: json

    {
        "title": "Some TAXII Server",
        "description": "This TAXII Server contains a listing of",
        "contact": "string containing contact information",
        "default": "http://localhost:5000/trustgroup1/",
        "api_roots": [
            "http://localhost:5000/api1/",
            "http://localhost:5000/api2/",
            "http://localhost:5000/trustgroup1/"
        ]
    }

**api_root_info** contains documents that describe each api_root.  Because the "_url" and "_name" properties are not part of the TAXII specification, they will be stripped by *medallion* before any document is returned to the client.

Here is a document from the example database:

.. code-block:: json

    {
        "title": "Malware Research Group",
        "description": "A trust group setup for malware researchers",
        "versions": [
            "application/taxii+json;version=2.1"
        ],
        "max_content_length": 9765625,
        "_url": "http://localhost:5000/trustgroup1/",
        "_name": "trustgroup1"
    }

The api root databases
----------------------

Each api root is contained in a separate Mongo DB database.  It has three collections:  **status**, **objects**,
and **collections**.

A document from the **collections** collection:

.. code-block:: json

    {
        "id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
        "title": "High Value Indicator Collection",
        "description": "This data collection is for collecting high value IOCs",
        "can_read": true,
        "can_write": true,
        "media_types": [
            "application/vnd.oasis.stix+json; version=2.0"
        ]
    }

Because the STIX objects and the manifest entries correspond one-to-one, the manifest is stored with the object.  It keeps all information about an object in one place and avoids the complexity and overhead of needing to join documents.  Also, timestamps are stored as numbers due to the millisecond precision limitation of the Mongo built-in ``Date`` type.  These documents are converted to proper STIX or TAXII JSON format as needed.

A document from the **objects** collection:

.. code-block:: json

    {
        "created": 1485524993.997,
        "description": "Poison Ivy",
        "id": "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
        "is_family": true,
        "malware_types": [
            "remote-access-trojan"
        ],
        "modified": 1485524993.997,
        "name": "Poison Ivy",
        "spec_version": "2.1",
        "type": "malware",
        "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
        "_manifest": {
            "date_added": 1485524999.997,
            "id": "malware--c0931cc6-c75e-47e5-9036-78fabc95d4ec",
            "media_type": "application/stix+json;version=2.1",
            "version": 1485524993.997
        }
    }

A document from the **status** collection:

.. code-block:: json

    {
        "id": "2d086da7-4bdc-4f91-900e-d77486753710",
        "status": "pending",
        "request_timestamp": "2016-11-02T12:34:34.123456Z",
        "total_count": 4,
        "success_count": 1,
        "successes": [
            {
                "id": "indicator--cd981c25-8042-4166-8945-51178443bdac",
                "version": "2014-05-08T09:00:00.000Z",
                "message": "Successfully added object to collection '91a7b528-80eb-42ed-a74d-c6fbd5a26116'."
            }
        ],
        "failure_count": 1,
        "failures": [
            {
                "id": "malware--664fa29d-bf65-4f28-a667-bdb76f29ec98",
                "version": "2015-05-08T09:00:00.000Z",
                "message": "Unable to process object"
            }
        ],
        "pending_count": 2,
        "pendings": [
            {
                "id": "indicator--252c7c11-daf2-42bd-843b-be65edca9f61",
                "version": "2016-08-08T09:00:00.000Z"
            },
            {
                "id": "relationship--045585ad-a22f-4333-af33-bfd503a683b5",
                "version": "2016-06-08T09:00:00.000Z"
            }
        ]
    }
