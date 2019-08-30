Custom Backends and Users
=========================

How to create your custom Backend
---------------------------------

To create a custom Backend compatible with medallion you need to subclass ``medallion.backends.base.Backend``. This object provides the basic skeleton used to handle each of the endpoint requests.

For further examples of on how to build a custom backend look under the ``\medallion\backends\`` directory.

How to load your custom Backend
-------------------------------

New changes made to the library makes it easy to dynamically load a new backend into your medallion server. You only need to provide the module path and the class you wish to instantiate for the medallion server. Any other key value pairs found under the ``backend`` value can be used to pass arguments to your custom backend. For example,

.. code:: json

    {
        "backend": {
            "module": "medallion.backends.memory_backend",
            "module_class": "MemoryBackend",
            "filename": "../test/data/default_data.json"
        },
    }

Another way to provide a custom backend using flask proxy could be,

.. code:: python

    import MyCustomBackend
    from flask import current_app
    from medallion import application_instance, set_config

    MyCustomBackend.init()  # Do some setup before attaching to application... (Imagine other steps happening here)

    with application_instance.app_context():
        current_app.medallion_backend = MyCustomBackend

    #  Do some other stuff...

    set_config(application_instance, {...})
    application_instance.run()


How to use a different authentication library
---------------------------------------------

If you need or prefer a library different from ``Flask-HTTPAuth``, you can override it by modifying the ``auth`` global to your preference. Now, if you want to keep changes at a minimum throughout the library. You can wrap the behavior inside another class, but remember all changes need to be performed before the call to ``run()``. For example,

.. code:: python

    from flask import current_app
    from medallion import application_instance, auth, set_config, init_backend

    # This is a dummy implementation of Flask Auth that always returns false
    dummy_auth = class DummyAuth(object):

        def login_required(self, f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated_function

        def get_password():
            return None  # Custom stuff to get password using other libraries, users_backend can go here.

    # Set the default implementation to the dummy auth
    auth = dummy_auth()

    set_config(application_instance, {...})
    init_backend(application_instance, {...})
    application_instance.run()


How to use a different backend to control users
-----------------------------------------------

Our implementation of a users authentication system is not suitable for a production environment. Thus requiring to write custom code to handle credential authentication, sessions, etc. Most likely you will require the changes described in the section above on `How to use a different authentication library`_, plus changing the ``users_backend``.

.. code:: python

    import MyCustomDBforUsers
    from flask import current_app
    from medallion import application_instance, set_config

    # This is a dummy implementation of Flask Auth that always returns false
    dummy_auth = class DummyAuth(object):

        def login_required(self, f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated_function

        def get_password():
            # Usage of MyCustomDBforUsers would likely happen here.
            return something # Custom stuff to get password using other libraries, users_backend functionality.

    # Set the default implementation to the dummy auth
    auth = dummy_auth()

    db = MyCustomDBforUsers.init()  # Do some setup before attaching to application... (Imagine other steps happening here)

    with application_instance.app_context():
        current_app.users_backend = db  # This will make it available inside the Flask instance in case you decide to perform changes to the internal blueprints.

    init_backend(application_instance, {...})
    application_instance.run()
