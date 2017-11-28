Compatibility
=============

*Medallion* does NOT support the following features of the `TAXII 2.0
specification <https://docs.oasis-open.org/cti/taxii/v2.0/taxii-v2.0.html>`_:

- Sorting
- Pagination
- Content-Types other than the default
- Pending Add Objects responses (all Add Objects request process all objects
  before sending back a response)
- *Medallion* uses HTTP only (not HTTPS). It can be run using a WSGI server
  (such as Gunicorn or uWSGI) behind a production server such as Apache or NGINX
  that acts as a reverse proxy for *medallion*.

*Medallion* conforms to most of the `interoperability specification
<https://docs.google.com/document/d/11MocPK3s8im8O5-7rgZhtVHoxO72aQicJj2v-HDx-Q8/>`_.

Its main purpose is for use in testing scenarios of STIX-based applications that
use the `python-stix2 API <https://github.com/oasis-open/cti-python-stix2>`_.
It has been developed in conjunction with `cti-taxii-client
<https://github.com/oasis-open/cti-taxii-client>`_ but should be compatible with
any TAXII client which makes HTTP requests as defined in TAXII 2.0
specification.
