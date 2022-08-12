# From https://eugene.kovalev.systems/posts/flask-client-side-tls-authentication/

"""A worker for Gunicorn that sets the client's Common Name as the X-USER header
   variable for every request after the client has been authenticated so that
   a Flask application can contain the authorization logic.
   Based on: https://gist.github.com/kgriffs/289206f07e23b9a30d29a2b23e28c41c"""

import ssl

from gunicorn.workers.sync import SyncWorker


class CertAuthWorker(SyncWorker):
    """A custom worker for putting authentication information into the X-USER
       header variable of each request."""
    def handle_request(self, listener, req, client, addr):
        """Handles each incoming request after a client has been authenticated."""
        subject = dict([i for subtuple in client.getpeercert().get('subject') for i in subtuple])
        issuer = dict([i for subtuple in client.getpeercert().get('issuer') for i in subtuple])
        headers = dict(req.headers)
        headers['X-USER'] = subject.get('commonName')
        serial = client.getpeercert().get('serialNumber')
        headers['X-PASS'] = serial
        not_before = client.getpeercert().get('notBefore')
        not_after = client.getpeercert().get('notAfter')
        headers['X-NOT_BEFORE'] = ssl.cert_time_to_seconds(not_before)
        headers['X-NOT_AFTER'] = ssl.cert_time_to_seconds(not_after)
        headers['X-ISSUER'] = issuer['commonName']

        req.headers = list(headers.items())
        super(CertAuthWorker, self).handle_request(listener, req, client, addr)
