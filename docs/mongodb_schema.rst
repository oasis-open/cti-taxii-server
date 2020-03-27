
Design of the TAXII Server Mongo DB Schema for *medallion*
==========================================================

As *medallion* is a prototype TAXII server implementation, the schema design for a Mongo DB is relatively straightforward.

Each Mongo database contains one or more collections.  The term "collection" in Mongo DBs is similar to the concept of a table in a relational database.  Collections contain "documents", similar to records.

It is unfortunate that the term "collection" is also used to signify something unrelated in the TAXII specification.  We will use the phrase "taxii collection" to distinguish them.

An instance of this schema can be populated via the file test/data/initialize_mongodb.py.  This instance will be used for examples below.

Utilities to initialize your own Mongo DB can be found in test/generic_initialize_mongodb.py.

The discovery database
----------------------

Basic metadata contained in the mongo database named **discovery_database**.

The discovery_database contains two collections:

**discovery_information**.  It should only contain only one "document", which is the discovery information that would be returned from the Discovery endpoint.  Here is the document from the example database.

.. code-block:: json

    {
        "title": "Some TAXII Server",
        "description": "This TAXII Server contains a listing of",
        "contact": "string containing contact information",
        "default": "http://localhost:5000/api2/",
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
            "taxii-2.0"
        ],
        "max_content_length": 9765625,
        "_url": "http://localhost:5000/trustgroup1/",
        "_name": "trustgroup1"
    }

The api root databases
----------------------

Each api root is contained in a separate Mongo DB database.  It has four collections:  **status**, **objects**, **manifests**, and **collections**.  To support multiple taxii collections, any document in the **objects** and **manifests** contains an extra property, "collection_id", to link it to the taxii collection that it is contained in.  Because "_collection_id" property is not part of the TAXII specification, it will be stripped by *medallion* before any document is returned to the client.

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

A document from the **objects** collection:

.. code-block:: json

    {
        "created": "2014-05-08T09:00:00.000Z",
        "id": "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
        "labels": [
            "file-hash-watchlist"
        ],
        "modified": "2014-05-08T09:00:00.000Z",
        "name": "File hash for Poison Ivy variant",
        "pattern": "[file:hashes.'SHA-256' = 'ef537f25c895bfa782526529a9b63d97aa631564d5d789c2b765448c8635fb6c']",
        "type": "indicator",
        "valid_from": "2014-05-08T09:00:00.000000Z",
        "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116"
    }

A document from the **status** collection:

.. code-block:: json

    {
        "id": "2d086da7-4bdc-4f91-900e-d77486753710",
        "status": "pending",
        "request_timestamp": "2016-11-02T12:34:34.12345Z",
        "total_count": 4,
        "success_count": 1,
        "successes": [
            "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade"
        ],
        "failure_count": 1,
        "failures": [
            {
                "id": "malware--664fa29d-bf65-4f28-a667-bdb76f29ec98",
                "message": "Unable to process object"
            }
        ],
        "pending_count": 2,
        "pendings": [
            "indicator--252c7c11-daf2-42bd-843b-be65edca9f61",
            "relationship--045585ad-a22f-4333-af33-bfd503a683b5"
        ]
    }

A document from the **manifest** collection:

.. code-block:: json

    {
        "id": "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
        "date_added": "2016-11-01T10:29:05Z",
        "versions": [
            "2014-05-08T09:00:00.000Z"
        ],
        "media_types": [
            "application/vnd.oasis.stix+json; version=2.0"
        ],
        "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116"
    }
