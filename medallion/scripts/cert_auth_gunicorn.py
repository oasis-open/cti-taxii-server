# From https://eugene.kovalev.systems/posts/flask-client-side-tls-authentication/

from multiprocessing import cpu_count
from pathlib import Path

import gunicorn.app.base

NUMBER_OF_WORKERS = (cpu_count() * 2) + 1


class ClientAuthApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, app, ca_path: Path, cert_path: Path, key_path: Path,
                 hostname='localhost', port=80, num_workers=NUMBER_OF_WORKERS, timeout=30):
        self.options = {
            'loglevel': 'debug',
            'bind': '{}:{}'.format(hostname, port),
            'workers': num_workers,
            'worker_class': 'medallion.scripts.cert_auth_worker.CertAuthWorker',
            'timeout': timeout,
            'ca_certs': str(ca_path),
            'certfile': str(cert_path),
            'keyfile': str(key_path),
            'cert_reqs': 2,
            'do_handshake_on_connect': True
        }
        self.application = app
        super().__init__()

    def init(self, parser, opts, args):
        return super().init(parser, opts, args)

    def load_config(self):
        config = dict([(key, value) for key, value in self.options.items()
                       if key in self.cfg.settings and value is not None])
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application
