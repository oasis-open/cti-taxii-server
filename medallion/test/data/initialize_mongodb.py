
from pymongo import MongoClient
from medallion.test.generic_initialize_mongodb import (build_new_mongo_databases_and_collection, add_api_root,
                                                       connect_to_client)


def reset_db():
    client = connect_to_client()
    client.drop_database("discovery_database")
    db = build_new_mongo_databases_and_collection(client)

    db["discovery_information"].insert_one({
             "title": "Some TAXII Server",
             "description": "This TAXII Server contains a listing of",
             "contact": "string containing contact information",
             "api_roots": []
         })
    client.drop_database("trustgroup1")
    api_root_db = add_api_root(client,
                               url="http://localhost:5000/trustgroup1/",
                               title="Malware Research Group",
                               description="A trust group setup for malware researchers",
                               max_content_length=9765625,
                               default=True)
    api_root_db["status"].insert_many([
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
                 },
                 {
                     "id": "2d086da7-4bdc-4f91-900e-f4566be4b780",
                     "status": "pending",
                     "request_timestamp": "2016-11-02T12:34:34.12345Z",
                     "total_objects": 2,
                     "success_count": 0,
                     "successes": [],
                     "failure_count": 0,
                     "failures": [],
                     "pending_count": 0,
                     "pendings": []
                 }
             ])

    api_root_db["manifests"].insert_many([
                        {
                            "id": "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
                            "date_added": "2016-11-01T03:04:05Z",
                            "versions": [
                                "2014-05-08T09:00:00.000Z"
                            ],
                            "media_types": [
                                "application/vnd.oasis.stix+json; version=2.0"
                            ],
                            '_collection_id': '91a7b528-80eb-42ed-a74d-c6fbd5a26116'
                        },
                        {
                            "id": "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111",
                            "date_added": "2016-11-01T10:29:05Z",
                            "versions": [
                                "2017-01-27T13:49:53.997Z"
                            ],
                            "media_types": [
                                "application/vnd.oasis.stix+json; version=2.0"
                            ],
                            '_collection_id': '91a7b528-80eb-42ed-a74d-c6fbd5a26116'
                        }
                    ])

    api_root_db["collections"].insert_one({
                     "id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116",
                     "title": "High Value Indicator Collection",
                     "description": "This data collection is for collecting high value IOCs",
                     "can_read": True,
                     "can_write": True,
                     "media_types": [
                         "application/vnd.oasis.stix+json; version=2.0"
                     ]})

    api_root_db["collections"].insert_one({
                                "id": "52892447-4d7e-4f70-b94d-d7f22742ff63",
                                "title": "Indicators from the past 24-hours",
                                "description": "This data collection is for collecting current IOCs",
                                "can_read": True,
                                "can_write": False,
                                "media_types": [
                                    "application/vnd.oasis.stix+json; version=2.0"
                                ]
                           })

    api_root_db["objects"].insert_many([{
                             "created": "2016-11-03T12:30:59.000Z",
                             "id": "indicator--d81f86b9-975b-bc0b-775e-810c5ad45a4f",
                             "labels": [
                                 "url-watchlist"
                             ],
                             "modified": "2017-01-27T13:49:53.935Z",
                             "name": "Malicious site hosting downloader",
                             "pattern": "[url:value = 'http://x4z9arb.cn/4712']",
                             "type": "indicator",
                             "valid_from": "2016-11-03T12:30:59.000Z",
                             "_collection_id": "52892447-4d7e-4f70-b94d-d7f22742ff63"
                         },
                         {
                             "created": "2016-11-03T12:30:59.000Z",
                             "description": "Accessing this url will infect your machine with malware.",
                             "id": "indicator--d81f86b9-975b-bc0b-775e-810c5ad45a4f",
                             "labels": [
                                 "url-watchlist"
                             ],
                             "modified": "2016-11-03T12:30:59.000Z",
                             "name": "Malicious site hosting downloader",
                             "pattern": "[url:value = 'http://x4z9arb.cn/4712']",
                             "type": "indicator",
                             "valid_from": "2017-01-27T13:49:53.935382Z",
                             "_collection_id": "52892447-4d7e-4f70-b94d-d7f22742ff63"
                         },
                         {
                            "created": "2017-01-27T13:49:53.997Z",
                            "description": "Poison Ivy",
                            "id": "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111",
                            "labels": [
                                "remote-access-trojan"
                            ],
                            "modified": "2017-01-27T13:49:53.997Z",
                            "name": "Poison Ivy",
                            "type": "malware",
                            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116"
                         },
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
                         },
                         {
                            "created": "2014-05-08T09:00:00.000Z",
                            "id": "relationship--2f9a9aa9-108a-4333-83e2-4fb25add0463",
                            "modified": "2014-05-08T09:00:00.000Z",
                            "relationship_type": "indicates",
                            "source_ref": "indicator--a932fcc6-e032-176c-126f-cb970a5a1ade",
                            "target_ref": "malware--fdd60b30-b67c-11e3-b0b9-f01faf20d111",
                            "type": "relationship",
                            "_collection_id": "91a7b528-80eb-42ed-a74d-c6fbd5a26116"
                         }
                         ])

    client.drop_database("api2")
    api_root_db = add_api_root(client,
                               url="http://localhost:5000/api2/",
                               title="STIX 2.0 Indicator Collections",
                               description="A repo for general STIX data.",
                               max_content_length=9765625)

