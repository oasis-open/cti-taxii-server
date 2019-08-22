class AuthBackend(object):
    def get_password_hash(self, username):
        raise NotImplementedError()

    def get_username_for_api_key(self, api_key):
        raise NotImplementedError()
