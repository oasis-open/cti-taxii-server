Custom Page Size
=========================

How to set pagination limits
---------------------------------

To specify a pagination limit with medallion you should call ``set_config``
when creating your application.

.. code-block:: python

    from medallion import application_instance, set_config

    set_config(application_instance, "taxii", {"taxii": {"max_page_size": 100}})


How to access the pagination limit
-------------------------------

From within your application, you can then access the configured pagination limit
through the ``current_app`` object.

.. code-block:: python

    from medallion import current_app

    page_size = current_app.taxii_config["max_page_size"]



