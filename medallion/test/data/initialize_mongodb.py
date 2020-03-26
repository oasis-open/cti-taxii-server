from pymongo import ASCENDING, IndexModel

from medallion.common import datetime_to_float, string_to_datetime
from medallion.test.generic_initialize_mongodb import (
    add_api_root, build_new_mongo_databases_and_collection, connect_to_client
)


def reset_db(url="mongodb://root:example@localhost:27017/"):
    client = connect_to_client(url)
    client.drop_database("discovery_database")
    db = build_new_mongo_databases_and_collection(client)

    db["discovery_information"].insert_one({
        "title": "Some TAXII Server",
        "description": "This TAXII Server contains a listing of",
        "contact": "string containing contact information",
        "api_roots": [],
    })

    client.drop_database("api1")
    add_api_root(
        client,
        url="http://localhost:5000/api1/",
        title="General STIX 2.1 Collections",
        description="A repo for general STIX data.",
        max_content_length=9765625,
    )

    client.drop_database("api2")
    add_api_root(
        client,
        url="http://localhost:5000/api2/",
        title="STIX 2.1 Indicator Collections",
        description="A repo for general STIX data.",
        max_content_length=9765625,
    )

    client.drop_database("trustgroup1")
    api_root_db = add_api_root(
        client,
        url="http://localhost:5000/trustgroup1/",
        title="Malware Research Group",
        description="A trust group setup for malware researchers",
        max_content_length=9765625,
        default=True,
    )
    api_root_db["status"].insert_many([
        {
            "id": "2d086da7-4bdc-4f91-900e-d77486753710",
            "status": "pending",
            "request_timestamp": "2016-11-02T12:34:34.123456Z",
            "total_count": 4,
            "success_count": 1,
            "successes": [
                "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
            ],
            "failure_count": 1,
            "failures": [
                {
                    "id": "malware--664fa29d-bf65-4f28-a667-bdb76f29ec98",
                    "message": "Unable to process object",
                },
            ],
            "pending_count": 2,
            "pendings": [
                "indicator--252c7c11-daf2-42bd-843b-be65edca9f61",
                "relationship--045585ad-a22f-4333-af33-bfd503a683b5",
            ],
        },
        {
            "id": "2d086da7-4bdc-4f91-900e-f4566be4b780",
            "status": "pending",
            "request_timestamp": "2016-11-02T12:34:34.123456Z",
            "total_objects": 0,
            "success_count": 0,
            "successes": [],
            "failure_count": 0,
            "failures": [],
            "pending_count": 0,
            "pendings": [],
        },
    ])

    api_root_db["manifests"].insert_many([
        {
            "id": "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
            "date_added": datetime_to_float(string_to_datetime("2016-11-01T03:04:05Z")),
            "versions": [
                datetime_to_float(string_to_datetime("2014-05-08T09:00:00.000Z")),
            ],
            "media_types": [
                "application/vnd.oasis.stix+json; version=2.0",
            ],
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
            "_type": "indicator",
        },
        {
            "id": "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111",
            "date_added": datetime_to_float(string_to_datetime("2017-01-27T13:49:53.997Z")),
            "versions": [
                datetime_to_float(string_to_datetime("2017-01-27T13:49:53.997Z")),
            ],
            "media_types": [
                "application/vnd.oasis.stix+json; version=2.0",
            ],
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
            "_type": "malware",
        },
        {
            "id": "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463",
            "date_added": datetime_to_float(string_to_datetime("2014-05-08T09:00:00.000Z")),
            "versions": [
                datetime_to_float(string_to_datetime("2014-05-08T09:00:00.000Z")),
            ],
            "media_types": [
                "application/vnd.oasis.stix+json; version=2.0",
            ],
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
            "_type": "relationship",
        },
        {
            "date_added": datetime_to_float(string_to_datetime("2017-01-20T00:00:00.000Z")),
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
            "id": "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
            "media_types": [
                "application/vnd.oasis.stix+json; version=2.0",
            ],
            "versions": [
                datetime_to_float(string_to_datetime("2017-01-20T00:00:00.000Z")),
            ],
            "_type": "marking-definition",
        },
        {
            "id": "indicator--d81f86b9-975b-bc0b-775e-810c5ad45a4f",
            "date_added": datetime_to_float(string_to_datetime("2016-12-27T13:49:53Z")),
            "versions": [
                datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
                datetime_to_float(string_to_datetime("2017-01-27T13:49:53.935Z")),
            ],
            "media_types": [
                "application/vnd.oasis.stix+json; version=2.0",
            ],
            "_collection_id": "52892447-4d7e-4f70-b94d-d7f22742ff63",
            "_type": "indicator",
        },
        {
            "id": "indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f",
            "date_added": datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
            "versions": [
                datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
            ],
            "media_types": [
                "application/vnd.oasis.stix+json; version=2.0",
            ],
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
            "_type": "indicator",
        },
    ])

    api_root_db["collections"].insert_one({
        "id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
        "title": "High Value Indicator Collection",
        "can_read": True,
        "can_write": True,
        "media_types": [
            "application/vnd.oasis.stix+json; version=2.0",
        ],
    })

    api_root_db["collections"].insert_one({
        "id": "472c94ae-3113-4e3e-a4dd-a9f4ac7471d4",
        "title": "Empty test Collection",
        "description": "This data collection is for testing querying across collections",
        "can_read": True,
        "can_write": True,
        "media_types": [
            "application/vnd.oasis.stix+json; version=2.0",
        ],
    })

    api_root_db["collections"].insert_one({
        "id": "52892447-4d7e-4f70-b94d-d7f22742ff63",
        "title": "Indicators from the past 24-hours",
        "description": "This data collection is for collecting current IOCs",
        "can_read": True,
        "can_write": False,
        "media_types": [
            "application/vnd.oasis.stix+json; version=2.0",
        ],
    })

    api_root_db["collections"].insert_one({
        "id": "64993447-4d7e-4f70-b94d-d7f33742ee63",
        "title": "Secret Indicators",
        "description": "Non accessible",
        "can_read": False,
        "can_write": False,
        "media_types": [
            "application/vnd.oasis.stix+json; version=2.0",
        ],
    })

    api_root_db["objects"].insert_many([
        {
            "created": datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
            "id": "indicator--d81f86b9-975b-bc0b-775e-810c5ad45a4f",
            "labels": [
                "url-watchlist",
            ],
            "modified": datetime_to_float(string_to_datetime("2017-01-27T13:49:53.935Z")),
            "name": "Malicious site hosting downloader",
            "pattern": "[url:value = 'http://x4z9arb.cn/4712']",
            "type": "indicator",
            "valid_from": "2016-11-03T12:30:59.000Z",
            "_collection_id": "52892447-4d7e-4f70-b94d-d7f22742ff63",
        },
        {
            "created": datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
            "description": "Accessing this url will infect your machine with malware.",
            "id": "indicator--d81f86b9-975b-bc0b-775e-810c5ad45a4f",
            "labels": [
                "url-watchlist",
            ],
            "modified": datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
            "name": "Malicious site hosting downloader",
            "pattern": "[url:value = 'http://x4z9arb.cn/4712']",
            "type": "indicator",
            "valid_from": "2017-01-27T13:49:53.935382Z",
            "_collection_id": "52892447-4d7e-4f70-b94d-d7f22742ff63",
        },
        {
            "created": datetime_to_float(string_to_datetime("2017-01-27T13:49:53.997Z")),
            "description": "Poison Ivy",
            "id": "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111",
            "labels": [
                "remote-access-trojan",
            ],
            "modified": datetime_to_float(string_to_datetime("2017-01-27T13:49:53.997Z")),
            "name": "Poison Ivy",
            "type": "malware",
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
        },
        {
            "created": datetime_to_float(string_to_datetime("2014-05-08T09:00:00.000Z")),
            "id": "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
            "labels": [
                "file-hash-watchlist",
            ],
            "modified": datetime_to_float(string_to_datetime("2014-05-08T09:00:00.000Z")),
            "name": "File hash for Poison Ivy variant",
            "pattern": "[file:hashes.'SHA-256' = 'ef537f25c895bfa782526529a9b63d97aa631564d5d789c2b765448c8635fb6c']",
            "type": "indicator",
            "valid_from": "2014-05-08T09:00:00.000000Z",
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
        },
        {
            "created": datetime_to_float(string_to_datetime("2014-05-08T09:00:00.000Z")),
            "id": "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463",
            "modified": datetime_to_float(string_to_datetime("2014-05-08T09:00:00.000Z")),
            "relationship_type": "indicates",
            "source_ref": "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
            "target_ref": "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111",
            "type": "relationship",
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
        },
        {
            "type": "marking-definition",
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
            "id": "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
            "created": datetime_to_float(string_to_datetime("2017-01-20T00:00:00.000Z")),
            "definition_type": "tlp",
            "definition": {
                "tlp": "green",
            },
        },
        {
            "created": datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
            "description": "Accessing this url will infect your machine with malware.",
            "id": "indicator--b81f86b9-975b-bb0b-775e-810c5bd45b4f",
            "labels": [
                "url-watchlist",
            ],
            "modified": datetime_to_float(string_to_datetime("2016-11-03T12:30:59.000Z")),
            "name": "Malicious site hosting downloader",
            "pattern": "[url:value = 'http://z4z10farb.cn/4712']",
            "type": "indicator",
            "valid_from": "2017-01-27T13:49:53.935382Z",
            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
        },
    ])

    date_index = IndexModel([("date_added", ASCENDING)])
    id_index = IndexModel([("id", ASCENDING)])
    collection_index = IndexModel([("_collection_id", ASCENDING)])
    collection_and_date_index = IndexModel([("_collection_id", ASCENDING), ("date_added", ASCENDING)])
    type_index = IndexModel([("_type", ASCENDING)])
    api_root_db["manifests"].create_indexes(
        [date_index, id_index, collection_index, collection_and_date_index, type_index],
    )
    api_root_db["objects"].create_indexes([id_index])


def create_users(url="mongodb://root:example@localhost:27017/"):
    client = connect_to_client(url)
    client.drop_database("auth")
    db = client["auth"]
    users = db.create_collection("users")

    users.insert_many([
        {
          "_id": "admin",
          "password": "pbkdf2:sha256:150000$vhWiAWXq$a16882c2eaf4dbb5c55566c93ec256c189ebce855b0081f4903f09a23e8b2344"
        },
        {
          "_id": "user1",
          "password": "pbkdf2:sha256:150000$TVpGAgEI$dd391524abb0d9107ff5949ef512c150523c388cfa6490d8556d604f90de329e"
        },
        {
          "_id": "user2",
          "password": "pbkdf2:sha256:150000$CUo7l9Vz$3ff2da22dcb84c9ba64e2df4d1ee9f7061c1da4f8506618f53457f615178e3f3"
        }
    ])

    api_keys = db.create_collection("api_keys")
    api_keys.insert_many([
        {
            "_id": "abc123",
            "user_id": "admin"
        },
        {
            "_id": "123456",
            "user_id": "admin"
        },
        {
            "_id": "abcdef",
            "user_id": "user1"
        }
    ])


def wipe_mongodb_server():
    """remove all databases on the server (excluding required MongoDB system databases)"""
    client = connect_to_client()

    for db in set(client.list_database_names()) - set(["admin", "config", "local"]):
        client.drop_database(db)


if __name__ == "__main__":
    reset_db()
    create_users()
