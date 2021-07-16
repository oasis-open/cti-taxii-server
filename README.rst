|Build_Status| |Coverage| |Version| |Documentation_Status|

cti-taxii-server
================

This is an `OASIS TC Open Repository <https://www.oasis-open.org/resources/open-repositories/>`_.
See the `Governance`_ section for more information.

Trusted Automated Exchange of Intelligence Information (TAXII™) is an application layer
protocol for the communication of cyber threat information in a simple and scalable manner.

*Medallion* is a minimal implementation of a TAXII 2.1 Server in Python.

**WARNING:** *medallion* was designed as a prototype and reference
implementation of TAXII 2.1, and is not intended for production use.

*medallion* has been designed to be a simple front-end REST server providing
access to the endpoints defined in that specification.
It uses the python framework - `Flask <http://flask.pocoo.org/>`_.  *medallion*
depends on back-end "plugins" which handle the persistence of the TAXII data and
metadata. The TAXII specification is agnostic to what type of data a TAXII
server stores, but this will usually be STIX 2 content.

Two back-end plugins are provided with *medallion*: the Memory back-end and the
MongoDB back-end.  The Memory back-end persists data "in memory".  It is
initialized using a json file that contains TAXII data and metadata.
It is possible to save the current state of the in memory store, but this
back-end is really intended only for testing purposes.  The MongoDB backend is
somewhat more robust and makes use of a MongoDB server, installed independently.
The MongoDB back-end can only be used if the pymongo python package is
installed. An error message will result if it is used without that package.

For more information, see `the documentation <https://medallion.readthedocs.io/>`__ on
ReadTheDocs.

Installation
------------

The easiest way to install *medallion* is with pip

.. code-block:: bash

  $ pip install medallion

Usage
-----

As a script
-----------

Medallion provides a command-line interface to start the TAXII Server

.. code-block:: text

    usage: medallion [-h] [--host HOST] [--port PORT] [--debug-mode]
                     [--log-level {DEBUG,INFO,WARN,ERROR,CRITICAL}]
                     [-c CONF_FILE] [--conf-dir CONF_DIR | --no-conf-dir]
                     [--conf-check] [CONFIG_PATH]

    medallion v3.0.0

    positional arguments:
      CONFIG_PATH           Deprecated argument for specifying a single
                            JSON configuration file. Do not specify this
                            and `--conf-file`.

    optional arguments:
      -h, --help            show this help message and exit

      --host HOST           The host to listen on.

      --port PORT           The port of the web server.

      --debug-mode          If set, start application in debug mode.

      --log-level {DEBUG,INFO,WARN,ERROR,CRITICAL}
                            The logging output level for medallion.

      -c CONF_FILE, --conf-file CONF_FILE
                            Path to a single configuration file. Defaults to the
                            value of the MEDALLION_CONFFILE environment variable
                            or /etc/xdg/medallion/3/medallion.conf.

      --conf-dir CONF_DIR   Path to a directory containing JSON configuration
                            files with names ending in .json or .conf. Defaults to
                            the value of the MEDALLION_CONFDIR environment
                            variable or /etc/xdg/medallion/3/config.d.

      --no-conf-dir         Disable the use of any configuration directory as
                            described for --conf-dir. This may be used to ensure
                            that the default or some value from the environment is
                            not used.

      --conf-check          Evaluate medallion configuration without running the
                            server.

To run *medallion*

.. code-block:: bash

    $ python medallion/scripts/run.py --conf-file <config-file>

Make sure medallion is using the same port that your TAXII client will be connecting on. You can specify which port medallion runs on using the `--port` option, for example

.. code-block:: bash

    $ medallion --port 80 --conf-file config_file.json

The <config_file> contains:

- configuration information for the backend plugin
- a simple user name/password dictionary

To use the Memory back-end plug, include the following in the <config-file>:

.. code-block:: json

    {
        "backend": {
            "module_class": "MemoryBackend",
            "filename": "<path to json file with initial data>"
        }
    }

To use the Mongo DB back-end plug, include the following in the <config-file>:

.. code-block:: json

    {
         "backend": {
            "module_class": "MongoBackend",
            "uri": "<Mongo DB server url>  # e.g., 'mongodb://localhost:27017/'"
         }
    }

*Note: A Mongo DB should be available at some URL when using the Mongo DB back-end*

A description of the Mongo DB structure expected by the mongo db backend code is
described in `the documentation <https://medallion.readthedocs.io/en/latest/mongodb_schema.html>`_.

As required by the TAXII specification, *medallion* supports HTTP Basic
authorization.  However, the user names and passwords are currently stored in
the <config_file> in plain text.

Here is an example:

.. code-block:: json

    {
        "users": {
           "admin": "Password0",
           "user1": "Password1",
           "user2": "Password2"
        }
    }

The authorization is enabled using the python package
`flask_httpauth <https://flask-httpauth.readthedocs.io>`_.
Authorization could be enhanced by changing the method "decorated" using
@auth.get_password in medallion/__init__.py

Configs may also contain a "taxii" section as well, as shown below:

.. code-block:: json

    {
        "taxii": {
           "max_page_size": 100
        }
    }

All TAXII servers require a config, though if any of the sections specified above
are missing, they will be filled with default values.

We welcome contributions for other back-end plugins.

Docker
------

We also provide a Docker image to make it easier to run *medallion*

.. code-block:: bash

    $ docker build . -t medallion -f docker_utils/Dockerfile

If operating behind a proxy, add the following option (replacing `<proxy>` with
your proxy location and port): ``--build-arg https_proxy=<proxy>``.

Then run the image

.. code-block:: bash

    $ docker run --rm -p 5000:5000 -v <directory>:/var/taxii medallion

Replace ``<directory>`` with the full path to the directory containing your
medallion configuration.

Governance
----------

This GitHub public repository (
**https://github.com/oasis-open/cti-taxii-server** ) was created at the request
of the `OASIS Cyber Threat Intelligence (CTI) TC <https://www.oasis-open.org/committees/cti/>`__
as an `OASIS TC Open Repository <https://www.oasis-open.org/resources/open-repositories/>`__ to support
development of open source resources related to Technical Committee work.

While this TC Open Repository remains associated with the sponsor TC, its
development priorities, leadership, intellectual property terms, participation
rules, and other matters of governance are `separate and distinct
<https://github.com/oasis-open/cti-taxii-server/blob/master/CONTRIBUTING.md#governance-distinct-from-oasis-tc-process>`__
from the OASIS TC Process and related policies.

All contributions made to this TC Open Repository are subject to open source
license terms expressed in the `BSD-3-Clause License
<https://www.oasis-open.org/sites/www.oasis-open.org/files/BSD-3-Clause.txt>`__.
That license was selected as the declared `"Applicable License"
<https://www.oasis-open.org/resources/open-repositories/licenses>`__ when the
TC Open Repository was created.

As documented in `"Public Participation Invited <https://github.com/oasis-open/cti-taxii-server/blob/master/CONTRIBUTING.md#public-participation-invited>`__",
contributions to this OASIS TC Open Repository are invited from all parties,
whether affiliated with OASIS or not. Participants must have a GitHub account,
but no fees or OASIS membership obligations are required. Participation is
expected to be consistent with the `OASIS TC Open Repository Guidelines and Procedures <https://www.oasis-open.org/policies-guidelines/open-repositories>`__, the open
source `LICENSE <https://github.com/oasis-open/cti-taxii-server/blob/master/LICENSE>`__
designated for this particular repository, and the requirement for an
`Individual Contributor License Agreement <https://www.oasis-open.org/resources/open-repositories/cla/individual-cla>`__
that governs intellectual property.

Maintainers
-----------

TC Open Repository `Maintainers <https://www.oasis-open.org/resources/open-repositories/maintainers-guide>`__
are responsible for oversight of this project's community development
activities, including evaluation of GitHub `pull requests <https://github.com/oasis-open/cti-taxii-server/blob/master/CONTRIBUTING.md#fork-and-pull-collaboration-model>`__
and `preserving <https://www.oasis-open.org/policies-guidelines/open-repositories#repositoryManagement>`__
open source principles of openness and fairness. Maintainers are recognized and
trusted experts who serve to implement community goals and consensus design
preferences.

Initially, the associated TC members have designated one or more persons to
serve as Maintainer(s); subsequently, participating community members may select
additional or substitute Maintainers, per `consensus agreements <https://www.oasis-open.org/resources/open-repositories/maintainers-guide#additionalMaintainers>`__.

Current Maintainers of this TC Open Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  `Chris Lenk <mailto:clenk@mitre.org>`__; GitHub ID: https://github.com/clenk/; WWW: `MITRE Corporation <https://www.mitre.org/>`__
-  `Rich Piazza <mailto:rpiazza@mitre.org>`__; GitHub ID: https://github.com/rpiazza/; WWW: `MITRE Corporation <https://www.mitre.org/>`__
-  `Zach Rush <mailto:zrush@mitre.org>`__; GitHub ID: https://github.com/zrush-mitre/; WWW: `MITRE Corporation <https://www.mitre.org/>`__
-  `Jason Keirstead <mailto:Jason.Keirstead@ca.ibm.com>`__; GitHub ID: https://github.com/JasonKeirstead; WWW: `IBM <http://www.ibm.com/>`__

About OASIS TC Open Repositories
--------------------------------

-  `TC Open Repositories: Overview and Resources <https://www.oasis-open.org/resources/open-repositories/>`__
-  `Frequently Asked Questions <https://www.oasis-open.org/resources/open-repositories/faq>`__
-  `Open Source Licenses <https://www.oasis-open.org/resources/open-repositories/licenses>`__
-  `Contributor License Agreements (CLAs) <https://www.oasis-open.org/resources/open-repositories/cla>`__
-  `Maintainers' Guidelines and Agreement <https://www.oasis-open.org/resources/open-repositories/maintainers-guide>`__

Feedback
--------

Questions or comments about this TC Open Repository's activities should be composed
as GitHub issues or comments. If use of an issue/comment is not possible or
appropriate, questions may be directed by email to the Maintainer(s) `listed
above <#currentMaintainers>`__. Please send general questions about Open
Repository participation to OASIS Staff at repository-admin@oasis-open.org and
any specific CLA-related questions to repository-cla@oasis-open.org.

.. |Build_Status| image:: https://github.com/oasis-open/cti-taxii-server/workflows/cti-taxii-server%20test%20harness/badge.svg
   :target: https://github.com/oasis-open/cti-taxii-server/actions?query=workflow%3A%22cti-taxii-server+test+harness%22
   :alt: Build Status
.. |Coverage| image:: https://codecov.io/gh/oasis-open/cti-taxii-server/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/oasis-open/cti-taxii-server
   :alt: Codecov Coverage
.. |Version| image:: https://img.shields.io/pypi/v/medallion.svg?maxAge=3600
   :target: https://pypi.python.org/pypi/medallion/
   :alt: PyPI Version 3.0.0
.. |Documentation_Status| image:: https://readthedocs.org/projects/medallion/badge/?version=latest
   :target: https://medallion.readthedocs.io/en/latest/
   :alt: ReadTheDocs Documentation Status
