from medallion.backends.auth_base import AuthBackend


class AuthMemoryBackend(AuthBackend):
    def __init__(self, users, **kwargs):
        self.users = users
        self.api_keys = kwargs.get("api_keys", {})

    def get_password_hash(self, username):
        return self.users.get(username)

    def get_username_for_api_key(self, api_key):
        return self.api_keys.get(api_key)
