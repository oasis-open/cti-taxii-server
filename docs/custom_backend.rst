Custom Backends and Users
=========================

How to create your custom Backend
---------------------------------

To create a custom Backend compatible with medallion you should subclass
``medallion.backends.Backend``. This object provides the basic skeleton used to
handle each of the endpoint requests. For further examples of on how to build a
custom backend look under the ``medallion/backends/`` directory.

How to load your custom Backend
-------------------------------

Backends are loaded based on the content of the ``backend`` map element in the
``medallion`` configuration file. Built-in backend implementations can be
loaded by simply setting the ``module_class`` key to the subclass' names. Extra
keyword arguments can be passed to the backend implementation by including them
in the ``backend`` map element. A simple example of loading the built-in
``MemoryBackend`` and passing it a keyword argument looks like:

.. code-block:: json

    {
        "backend": {
            "module_class": "MemoryBackend",
            "filename": "../test/data/default_data.json"
        }
    }

Loading custom backends can be a little more complicated depending on how the
backend class is implemented. If the custom backend subclasses the base
``Backend`` and is somehow imported prior to starting the ``medallion`` flask
application, the configuration file may simply refer to it by name in the
``module_class`` key. This might be useful in environments where it is
preferable to use something like the Python ``site`` module rather than
installing an extra package.

.. code-block:: json

    {
        "backend": {
            "module_class": "MyCustomBackend",
        }
    }

To make loading out-of-tree backend implementations easier, the
``medallion.backends`` entrypoint is defined which may be used by other
packages to point to external modules or classes which should be loaded by the
backend machinery. This should be defined in your package's ``setup.py`` like:

.. code-block:: python

    setup(
        # ...
        entry_points={
            "medallion.backends": [
                "MyEPName = mypackage.with_backends:MyCustomBackend",
            ],
        }
    )

The entrypoint will be loaded and if it refers to a class object it will be
registered with the base ``Backend`` class using the entrypoint's name. If the
entrypoint is a subclass of the base ``Backend``, it will also be registered
using the name of the loaded class object, supporting the use of implementation
which do not subclass the base ``Backend`` properly. The entrypoint might also
validly point to a module to be loaded, in which case any backend
implementations must be subclasses of the base ``Backend`` and they will be
registered under their class names.

A previous implementation allowed a dotted module path to be specified in the
``module`` key of the ``backend`` map in the configuration. This behaviour is
deprecated but will continue to work with a warning. This is done to allow
implementations to pivot to using the entry-point mechanism instead. An example
configuration snippet for this approach looks like:

.. code-block:: json

    {
        "backend": {
            "module": "mypackage.with_backends",
            "module_class": "MyCustomBackend",
        }
    }

Another way to provide a custom backend using flask proxy could be:

.. code-block:: python

    import MyCustomBackend
    from flask import current_app
    from medallion import application_instance, set_config, register_blueprints

    MyCustomBackend.init()  # Do some setup before attaching to application... (Imagine other steps happening here)

    with application_instance.app_context():
        current_app.medallion_backend = MyCustomBackend

    #  Do some other stuff...
    set_config(application_instance, "backend", {
        "backend": {
            "module": "mypackage.with_backends",
            "module_class": "MyCustomBackend",
        }
    })
    register_blueprints(application_instance)
    application_instance.run()

How to use a different authentication library
---------------------------------------------

If you need or prefer a library different from ``Flask-HTTPAuth``, you can override it by modifying the ``auth`` global to your preference. Now, if you want to keep changes at a minimum throughout the library. You can wrap the behavior inside another class, but remember all changes need to be performed before the call to ``run()``. For example,

.. code-block:: python

    from flask import current_app
    from medallion import application_instance, auth, set_config, init_backend, register_blueprints

    # This is a dummy implementation of Flask Auth that always returns false
    dummy_auth = class DummyAuth(object):

        def login_required(self, f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated_function

        def get_password():
            return None  # Custom stuff to get password using other libraries, users_config can go here.

    # Set the default implementation to the dummy auth
    auth = dummy_auth()

    set_config(application_instance, {...})
    init_backend(application_instance, {...})
    register_blueprints(application_instance)
    application_instance.run()

How to use a different backend to control users
-----------------------------------------------

Our implementation of a users authentication system is not suitable for a production environment. Thus requiring to write custom code to handle credential authentication, sessions, etc. Most likely you will require the changes described in the section above on `How to use a different authentication library`_, plus changing the ``users_config``.

.. code-block:: python

    import MyCustomDBforUsers
    from flask import current_app
    from medallion import application_instance, set_config, register_blueprints

    # This is a dummy implementation of Flask Auth that always returns false
    dummy_auth = class DummyAuth(object):

        def login_required(self, f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated_function

        def get_password():
            # Usage of MyCustomDBforUsers would likely happen here.
            return something # Custom stuff to get password using other libraries, users_config functionality.

    # Set the default implementation to the dummy auth
    auth = dummy_auth()

    db = MyCustomDBforUsers.init()  # Do some setup before attaching to application... (Imagine other steps happening here)

    with application_instance.app_context():
        current_app.users_config = db  # This will make it available inside the Flask instance in case you decide to perform changes to the internal blueprints.

    init_backend(application_instance, {...})
    register_blueprints(application_instance)
    application_instance.run()
