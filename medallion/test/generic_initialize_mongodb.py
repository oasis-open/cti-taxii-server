from pymongo import MongoClient


def connect_to_client(url="mongodb://root:example@localhost:27017/"):
    """
    Fill:
        Connect to a mongodb server accessible via the given url

    Args:
        url (str): url of the mongodb server

    Returns:
        mongodb client

    """
    return MongoClient(url)


def build_new_mongo_databases_and_collection(client):
    """
    Fill:
        Create the top-level mongodb for TAXII, discovery_database, with its two collections:
        discovery_information and api_root_info

    Args:
        client (pymongo.MongoClient): mongodb client connection

    Returns:
        discovery_database object

    """
    db = client["discovery_database"]
    return db


def add_api_root(client, url=None, title=None, description=None, versions=None, max_content_length=0, default=False):
    """
    Fill:
        Create a mongodb for a new api root, with collections: status, objects, manifest, (TAXII) collections.
        Update top-level mongodb for TAXII, discovery_database, with information about this api root.

    Args:
        client (pymongo.MongoClient): mongodb client connection
        url (str): url of this api root
        title (str):  title of this api root
        description (str): description of this api root
        versions (list of str):  versions of TAXII serviced by this api root
        max_content_length (int):  maximum size of requests to this api root
        default (bool):  is this the default api root for this TAXII server

    Returns:
        new api_root_db object

    """
    if not versions:
        versions = ["application/taxii+json;version=2.1"]
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
        "max_content_length": max_content_length,
    })
    api_root_db = client[name]
    api_root_db.drop_collection("status")
    return api_root_db
