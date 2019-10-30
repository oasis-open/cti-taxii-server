def _base_config(backend, auth):
    return {
        'flask': {
            'SECRET_KEY': 'testsecret',
            'TESTING': True,
        },
        'multi-auth': ['api_key', 'jwt', 'basic'],
        "taxii": {
            "max_page_size": 20
        },
        'backend': backend,
        'auth': auth,
    }


def memory_config(data_file):
    return _base_config({
        "module": "medallion.backends.taxii.memory_backend",
        "module_class": "MemoryBackend",
        "filename": data_file
    }, {
        "module": "medallion.backends.auth.memory_auth",
        "module_class": "AuthMemoryBackend",
        "users": {
            "admin": "pbkdf2:sha256:150000$vhWiAWXq$a16882c2eaf4dbb5c55566c93ec256c189ebce855b0081f4903f09a23e8b2344",
            "user1": "pbkdf2:sha256:150000$TVpGAgEI$dd391524abb0d9107ff5949ef512c150523c388cfa6490d8556d604f90de329e",
            "user2": "pbkdf2:sha256:150000$CUo7l9Vz$3ff2da22dcb84c9ba64e2df4d1ee9f7061c1da4f8506618f53457f615178e3f3"
        },
        "api_keys": {
            "123456": "admin",
            "abc123": "admin",
            "abcdef": "user1"
        }
    })


def directory_config():
    return _base_config({
        "module": "medallion.backends.taxii.directory_backend",
        "module_class": "DirectoryBackend",
        "path": "./medallion/test/directory/",
        "discovery": {
            "title": "Indicators from the directory backend",
            "description": "Indicators from the directory backend",
            "contact": "",
            "host": "http://localhost:5000/"
        },
        "api-root": {
            "title": "",
            "description": "",
            "versions": [
                "taxii-2.0"
            ],
            "max-content-length": 9765625
        },
        "collection": {
            "id": "",
            "title": "",
            "description": "",
            "can_read": True,
            "can_write": True,
            "media_types": [
                "application/vnd.oasis.stix+json; version=2.0"
            ]
        }
    }, {
        "module": "medallion.backends.auth.memory_auth",
        "module_class": "AuthMemoryBackend",
        "users": {
            "admin": "pbkdf2:sha256:150000$vhWiAWXq$a16882c2eaf4dbb5c55566c93ec256c189ebce855b0081f4903f09a23e8b2344",
            "user1": "pbkdf2:sha256:150000$TVpGAgEI$dd391524abb0d9107ff5949ef512c150523c388cfa6490d8556d604f90de329e",
            "user2": "pbkdf2:sha256:150000$CUo7l9Vz$3ff2da22dcb84c9ba64e2df4d1ee9f7061c1da4f8506618f53457f615178e3f3"
        },
        "api_keys": {
            "123456": "admin",
            "abc123": "admin",
            "abcdef": "user1"
        }
    })


def mongodb_config():
    return _base_config({
        "module": "medallion.backends.taxii.mongodb_backend",
        "module_class": "MongoBackend",
        "uri": "mongodb://root:example@localhost:27017/"
    }, {
        "module": "medallion.backends.auth.mongodb_auth",
        "module_class": "AuthMongodbBackend",
        "uri": "mongodb://root:example@localhost:27017/",
        "db_name": "auth"
    })
