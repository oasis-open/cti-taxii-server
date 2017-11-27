|Build_Status| |Coverage| |Version|

=========
medallion
=========

NOTE: This is an `OASIS Open Repository <https://www.oasis-open.org/resources/open-repositories/>`_. See the `Governance`_ section for more information.

*medallion* is a minimal implementation of a TAXII 2.0 Server in python.

*medallion* does NOT support the following features of the `TAXII 2.0 specification <http://docs.oasis-open.org/cti/taxii/v2.0/csprd01/taxii-v2.0-csprd01.html>`_:

- Sorting
- Pagination
- Content-Types other than the default
- Pending Add Objects responses (all Add Objects request process all objects before sending back a response)
- *medallion* uses http only

Although *medallion* conforms to most of the `interoperability specification <https://docs.google.com/document/d/11MocPK3s8im8O5-7rgZhtVHoxO72aQicJj2v-HDx-Q8/>`_,
**it should not be used in a production environment**.
Its main purpose is for use in testing scenarios of STIX-based applications that use the `python-stix2 API <https://github.com/oasis-open/cti-python-stix2>`_.  It has been developed in conjunction
with `cti-taxii-client <https://github.com/oasis-open/cti-taxii-client>`_ but should be compatible with any TAXII client which makes HTTP requests
as defined in TAXII 2.0 specification.

*medallion* has been designed to be a simple front-end REST server providing access to the endpoints defined in that specification.
It uses the python framework - `Flask <http://flask.pocoo.org/>`_.  *medallion* depends on back-end "plugins" which handle the
persistance of the TAXII data and metadata.
The TAXII specification is agnostic to what type of data a TAXII server stores, but this will usually be STIX 2 content.

Two back-end plugins are provided with *medallion*:
the Memory back-end and the MongoDB back-end.  The Memory back-end persists data "in memory".  It is initalized using a json file that contains TAXII data
and metadata.
It is possible to save the current state of the in memory store, but this back-end is really intended only for testing purposes.  The MongoDB backend is
somewhat more robust
and makes use of a MongoDB server, installed independently.  The MongoDB back-end can only be used if the pymongo python package is installed.  An error
message will
result if it is used without that package.

Installation
============

The easiest way to install *medallion* is with pip:

::

  $ pip install medallion


Usage
=====



To run *medallion*:

::

    $ python medallion/scripts/run.py <config-file>

The <config_file> contains:

- configuration information for the backend plugin
- a simple user name/password dictionary

To use the Memory back-end plug, include the following in the <config-file>:

.. code:: python

    "backend": {
        "type": "memory",
        "data_file": <path to json file with initial data>
    }

To use the Mongo DB back-end plug, include the following in the <config-file>:

.. code:: python

    "backend": {
        "type": "mongodb",
        "url": <Mongo DB server url>  # e.g., "mongodb://localhost:27017/"
    }

*Note: A Mongo DB should be available at some URL when using the Mongo DB back-end*

A description of the Mongo DB structure expected by the mongo db backend code is described in `mongodb_schema.rst <https://github.com/oasis-open/cti-taxii-server/blob/mongo_db_design/mongodb_schema.rst>`_

As required by the TAXII specification, *medallion* supports BasicHTTP authorization.  However, the user names and passwords are currently
stored in the <config_file> in plain text.

Here is an example:

.. code:: python

    "users": {
        "admin": "Password0",
        "user1": "Password1",
        "user2": "Password2"
    }

The authorization is enabled using the python package `flask_httpauth <https://flask-httpauth.readthedocs.io>`_.
Authorization could be enhanced by changing the method "decorated" using
@auth.get_password in medallion/__init__.py

We welcome contributions for other back-end plugins.

Governance
==========

This GitHub public repository (
**https://github.com/oasis-open/cti-taxii-client** ) was created at the request
of the `OASIS Cyber Threat Intelligence (CTI) TC
<https://www.oasis-open.org/committees/cti/>`__ as an `OASIS Open Repository
<https://www.oasis-open.org/resources/open-repositories/>`__ to support
development of open source resources related to Technical Committee work.

While this Open Repository remains associated with the sponsor TC, its
development priorities, leadership, intellectual property terms, participation
rules, and other matters of governance are `separate and distinct
<https://github.com/oasis-open/cti-taxii-client/blob/master/CONTRIBUTING.md#governance-distinct-from-oasis-tc-process>`__
from the OASIS TC Process and related policies.

All contributions made to this Open Repository are subject to open source
license terms expressed in the `BSD-3-Clause License
<https://www.oasis-open.org/sites/www.oasis-open.org/files/BSD-3-Clause.txt>`__.
That license was selected as the declared `"Applicable License"
<https://www.oasis-open.org/resources/open-repositories/licenses>`__ when the
Open Repository was created.

As documented in `"Public Participation Invited
<https://github.com/oasis-open/cti-taxii-client/blob/master/CONTRIBUTING.md#public-participation-invited>`__",
contributions to this OASIS Open Repository are invited from all parties,
whether affiliated with OASIS or not. Participants must have a GitHub account,
but no fees or OASIS membership obligations are required. Participation is
expected to be consistent with the `OASIS Open Repository Guidelines and
Procedures
<https://www.oasis-open.org/policies-guidelines/open-repositories>`__, the open
source `LICENSE
<https://github.com/oasis-open/cti-taxii-client/blob/master/LICENSE>`__
designated for this particular repository, and the requirement for an
`Individual Contributor License Agreement
<https://www.oasis-open.org/resources/open-repositories/cla/individual-cla>`__
that governs intellectual property.

Maintainers
-----------

Open Repository `Maintainers
<https://www.oasis-open.org/resources/open-repositories/maintainers-guide>`__
are responsible for oversight of this project's community development
activities, including evaluation of GitHub `pull requests
<https://github.com/oasis-open/cti-taxii-client/blob/master/CONTRIBUTING.md#fork-and-pull-collaboration-model>`__
and `preserving
<https://www.oasis-open.org/policies-guidelines/open-repositories#repositoryManagement>`__
open source principles of openness and fairness. Maintainers are recognized and
trusted experts who serve to implement community goals and consensus design
preferences.

Initially, the associated TC members have designated one or more persons to
serve as Maintainer(s); subsequently, participating community members may select
additional or substitute Maintainers, per `consensus agreements
<https://www.oasis-open.org/resources/open-repositories/maintainers-guide#additionalMaintainers>`__.

Current Maintainers of this Open Repository
-------------------------------------------

-  `Greg Back <mailto:gback@mitre.org>`__; GitHub ID:
   https://github.com/gtback/; WWW: `MITRE
   Corporation <https://www.mitre.org/>`__
-  `Rich Piazza <mailto:rpiazza@mitre.org>`__; GitHub ID:
   https://github.com/rpiazza/; WWW: `MITRE
   Corporation <https://www.mitre.org/>`__

About OASIS Open Repositories
-----------------------------

-  `Open Repositories: Overview and
   Resources <https://www.oasis-open.org/resources/open-repositories/>`__
-  `Frequently Asked
   Questions <https://www.oasis-open.org/resources/open-repositories/faq>`__
-  `Open Source
   Licenses <https://www.oasis-open.org/resources/open-repositories/licenses>`__
-  `Contributor License Agreements
   (CLAs) <https://www.oasis-open.org/resources/open-repositories/cla>`__
-  `Maintainers' Guidelines and
   Agreement <https://www.oasis-open.org/resources/open-repositories/maintainers-guide>`__

Feedback
--------

Questions or comments about this Open Repository's activities should be composed
as GitHub issues or comments. If use of an issue/comment is not possible or
appropriate, questions may be directed by email to the Maintainer(s) `listed
above <#currentMaintainers>`__. Please send general questions about Open
Repository participation to OASIS Staff at repository-admin@oasis-open.org and
any specific CLA-related questions to repository-cla@oasis-open.org.

.. |Build_Status| image:: https://travis-ci.org/oasis-open/cti-taxii-server.svg?branch=master
   :target: https://travis-ci.org/oasis-open/cti-taxii-server
.. |Coverage| image:: https://codecov.io/gh/oasis-open/cti-taxii-server/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/oasis-open/cti-taxii-server
.. |Version| image:: https://img.shields.io/pypi/v/medallion.svg?maxAge=3600
   :target: https://pypi.python.org/pypi/medallion/
