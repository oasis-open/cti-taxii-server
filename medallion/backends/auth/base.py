
class AuthBackend(object):

    def get_password_hash(self, username):
        """Given a username provide the password hash for verification."""
        raise NotImplementedError()

    def get_username_for_api_key(self, api_key):
        """Given an API key provide the username for verification."""
        raise NotImplementedError()
