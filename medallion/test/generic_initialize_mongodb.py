from pymongo import MongoClient


def connect_to_client(url="mongodb://localhost:27017/"):
    return MongoClient(url)


def build_new_mongo_databases_and_collection(client):
    db = client["discovery_database"]
    db["discovery_information"]
    db["api_root_info"]
    return db


def add_api_root(client, url=None, title=None, description=None, versions=["taxii-2.0"], max_content_length=0, default=False):
    db = client["discovery_database"]
    url_parts = url.split("/")
    name = url_parts[-2]
    discovery_info = db["discovery_information"]
    info = discovery_info.find_one()
    info["api_roots"].append(name)
    discovery_info.update_one({"_id": info["_id"]}, {"$set": {"api_roots": info["api_roots"]}})
    api_root_info = db["api_root_info"]
    api_root_info.insert_one({
        "_url": url,
        "_name": name,
        "title": title,
        "description": description,
        "versions": versions,
        "max_content_length": max_content_length})
    api_root_db = client[name]
    api_root_db["status"]
    api_root_db["objects"]
    api_root_db["manifests"]
    api_root_db["collections"]
    return api_root_db
