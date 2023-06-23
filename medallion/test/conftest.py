from unittest import mock

import pytest


# This fixture is cheap so we just do it for every function it's requested by
# to ensure that functions which aren't opted-in themselves or by their module
# remain unaffected
@pytest.fixture(scope="function")
def empty_environ():
    with mock.patch.dict("os.environ", clear=True) as mocked_environ:
        yield mocked_environ