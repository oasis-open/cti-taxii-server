#!/usr/bin/env python
from codecs import open
import os.path

from setuptools import find_packages, setup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, "medallion", "version.py")


def get_version():
    with open(VERSION_FILE, encoding="utf-8") as f:
        for line in f.readlines():
            if line.startswith("__version__"):
                version = line.split()[-1].strip("\"")
                return version
        raise AttributeError("Package does not have a __version__")


def get_long_description():
    with open("README.rst", encoding="utf-8") as f:
        return f.read()


setup(
    name="medallion",
    version=get_version(),
    description="TAXII 2.0 Server implementing required endpoints",
    long_description=get_long_description(),
    long_description_content_type="text/x-rst",
    url="https://oasis-open.github.io/cti-documentation/",
    author="OASIS Cyber Threat Intelligence Technical Committee",
    author_email="cti-users@lists.oasis-open.org",
    maintainer="Emmanuelle Vargas-Gonzalez",
    maintainer_email="emmanuelle@mitre.org",
    license="BSD",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Security",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    keywords="taxii taxii2 server json cti cyber threat intelligence",
    packages=find_packages(exclude=["*.test", "*.test.data"]),
    install_requires=[
        "flask>=0.12.1",
        "Flask-HTTPAuth",
        "pytz",
        "six",
        "pyjwt",
    ],
    entry_points={
        "console_scripts": [
            "medallion = medallion.scripts.run:main",
            "medallion-generate-user-pass = medallion.scripts.generate_user_password:main",
            "medallion-mongo-db-utils = medallion.scripts.auth_db_utils:main",
        ],
    },
    extras_require={
        "test": [
            "coverage",
            "pytest",
            "pytest-cov",
            "tox",
        ],
        "docs": [
            "sphinx",
            "sphinx-prompt",
        ],
        "mongo": [
            "pymongo",
        ],
    },
    project_urls={
        'Documentation': 'https://medallion.readthedocs.io/',
        'Source Code': 'https://github.com/oasis-open/cti-taxii-server/',
        'Bug Tracker': 'https://github.com/oasis-open/cti-taxii-server/issues/',
    },
)
