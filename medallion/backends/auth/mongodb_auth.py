import logging

from medallion.backends.auth.base import AuthBackend

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure
except ImportError:
    raise ImportError("'pymongo' package is required to use this module.")


# Module-level logger
log = logging.getLogger(__name__)


class AuthMongodbBackend(AuthBackend):
    def __init__(self, uri, **kwargs):
        try:
            self.client = MongoClient(uri)
            self.db_name = kwargs["db_name"]
            # The ismaster command is cheap and does not require auth.
            # self.client.admin.command("ismaster")
        except ConnectionFailure:
            log.error("Unable to establish a connection to MongoDB server {}".format(uri))

    def get_password_hash(self, username):
        db = self.client[self.db_name]
        users = db['users']
        user_obj = users.find_one({"_id": username})
        if user_obj:
            return user_obj['password']
        else:
            return None

    def get_username_for_api_key(self, api_key):
        db = self.client[self.db_name]
        api_keys = db['api_keys']
        api_key_obj = api_keys.find_one({"_id": api_key})

        if api_key_obj:
            username = api_key_obj['user_id']
            return username
        else:
            return None
