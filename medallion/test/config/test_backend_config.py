import unittest.mock as mock

import pytest

import medallion
from medallion.backends import base as mbe_base
from medallion.backends import memory_backend as mbe_mem


class SavesArgs(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


def test_backend_registration():
    """
    Sanity test that backends get registered in the base class.
    """
    with mock.patch(
        "medallion.backends.base.BackendRegistry.register",
    ) as mock_reg:
        class Foo(mbe_base.Backend):
            pass
    mock_reg.assert_called_once_with("Foo", Foo)


class TestBackendConfig:
    def test_backend_without_name(self):
        with pytest.raises(ValueError):
            medallion.connect_to_backend(dict())

    def test_backend_lookup(self):
        cfg = {"module_class": mock.sentinel.class_name}
        with mock.patch(
            "medallion.backends.base.BackendRegistry.get",
        ) as mock_find:
            medallion.connect_to_backend(cfg)
        mock_find.assert_called_once_with(mock.sentinel.class_name)

    def test_backend_lookup_unknown(self):
        cfg = {"module_class": mock.sentinel.class_name}
        with mock.patch(
            "medallion.backends.base.BackendRegistry.get",
            side_effect=KeyError,
        ) as mock_find:
            with pytest.raises(ValueError):
                medallion.connect_to_backend(cfg)
        mock_find.assert_called_once_with(mock.sentinel.class_name)

    def test_backend_instantiation(self):
        cfg = {"module_class": mock.sentinel.class_name}
        with mock.patch(
            "medallion.backends.base.BackendRegistry.get",
        ) as mock_find:
            be_obj = medallion.connect_to_backend(cfg)
        mock_find.assert_called_once_with(mock.sentinel.class_name)
        assert be_obj is mock_find.return_value()

    def test_backend_instantiation_raises(self):
        class SentinelError(BaseException):
            pass

        cfg = {"module_class": mock.sentinel.class_name}
        with mock.patch(
            "medallion.backends.base.BackendRegistry.get",
            return_value=mock.MagicMock(side_effect=SentinelError),
        ) as mock_find:
            with pytest.raises(SentinelError):
                medallion.connect_to_backend(cfg)
        mock_find.assert_called_once_with(mock.sentinel.class_name)

    def test_backend_instantiation_with_args(self):
        cfg = {
            "module_class": mock.sentinel.class_name,
            "foo": 42, "bar": "baz",
        }
        with mock.patch(
            "medallion.backends.base.BackendRegistry.get",
        ) as mock_find:
            be_obj = medallion.connect_to_backend(cfg)
        mock_find.assert_called_once_with(mock.sentinel.class_name)
        mock_find.return_value.assert_called_once_with(**cfg)
        assert be_obj is mock_find.return_value()

    def test_builtin_backend(self):
        be_obj = medallion.connect_to_backend(dict(
            module_class="MemoryBackend",
        ))
        assert isinstance(be_obj, mbe_mem.MemoryBackend)

    def test_backend_module_path(self):
        cfg = {
            "module": __name__,
            "module_class": "SavesArgs",
        }
        with mock.patch(
            "medallion.backends.base.BackendRegistry.get",
        ) as mock_find:
            be_obj = medallion.connect_to_backend(cfg)
        assert mock_find.call_count == 0
        assert isinstance(be_obj, SavesArgs)
        assert be_obj.args == tuple()
        assert be_obj.kwargs == cfg

    def test_backend_module_path_nonexistent(self):
        cfg = {
            "module": "nonexistent.module.path",
            "module_class": mock.sentinel.class_name,
        }
        with pytest.raises(ImportError):
            medallion.connect_to_backend(cfg)

    def test_backend_module_name_nonexistent(self):
        cfg = {
            "module": __name__,
            "module_class": "NonexistentClassName",
        }
        with pytest.raises(AttributeError):
            medallion.connect_to_backend(cfg)
