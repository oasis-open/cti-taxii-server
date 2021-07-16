import importlib
import json
import json.decoder
import logging
import pathlib
import re
from unittest import mock

import appdirs
import pytest
import pytest_subtests  # noqa: F401

import medallion.config as m_cfg
import medallion.version as m_vers

pytestmark = pytest.mark.usefixtures("empty_environ")


def test_load_config_appdir_discovery_none_found(tmp_path):
    """
    Ensure that if no config directories exist the current version's is used.
    """
    current_major = m_vers.__version__.split(".")[0]
    default_appdirs = appdirs.AppDirs(
        "medallion", "oasis-open", version=current_major
    )
    default_cfg_p = pathlib.Path(default_appdirs.site_config_dir)

    with mock.patch("pathlib.Path.is_dir", return_value=False):
        m_cfg_local = importlib.reload(m_cfg)
    assert m_cfg_local.DEFAULT_CONFFILE == default_cfg_p / "medallion.conf"
    assert m_cfg_local.DEFAULT_CONFDIR == default_cfg_p / "config.d"


def test_load_config_appdir_discovery_current_found(tmp_path):
    """
    Ensure that if the current version's config directory is found it's used.

    This should be the case even if other directories exist so we ensure that
    `Path.is_dir()` returns True for any instances.
    """
    current_major = m_vers.__version__.split(".")[0]
    default_appdirs = appdirs.AppDirs(
        "medallion", "oasis-open", version=current_major
    )
    default_cfg_p = pathlib.Path(default_appdirs.site_config_dir)

    with mock.patch("pathlib.Path.is_dir", return_value=True):
        m_cfg_local = importlib.reload(m_cfg)
    assert m_cfg_local.DEFAULT_CONFFILE == default_cfg_p / "medallion.conf"
    assert m_cfg_local.DEFAULT_CONFDIR == default_cfg_p / "config.d"


def test_load_config_appdir_discovery_compat_found(tmp_path):
    """
    Ensure that a compatible version's config directory will be used.
    """
    compat_major = "COMPAT"     # Doesn't need to be an integer
    compat_appdirs = appdirs.AppDirs(
        "medallion", "oasis-open", version=compat_major,
    )
    compat_cfg_p = pathlib.Path(compat_appdirs.site_config_dir)

    def is_dir(inst):
        return inst == compat_cfg_p

    with mock.patch(
        # Mock the `sorted()` builtin for the config module when we reload it
        # and return a faked "CURRENT" candidate and a "COMPAT" candidate which
        # our `is_dir()` mock knows to return `True` for
        "medallion.config.sorted", return_value=["CURRENT", compat_major]
    ) as mock_sorted, mock.patch(
        "pathlib.Path.is_dir", new=is_dir
    ):
        m_cfg_local = importlib.reload(m_cfg)
    mock_sorted.assert_called_once_with(mock.ANY, reverse=True)
    assert m_cfg_local.DEFAULT_CONFFILE == compat_cfg_p / "medallion.conf"
    assert m_cfg_local.DEFAULT_CONFDIR == compat_cfg_p / "config.d"


def test_load_config_defaults():
    """
    Ensure that `conf_file` and `conf_dir` arguments have expected defaults.

    We do this since we don't want to attempt to create those files for parsing
    in any of our actual functional tests below.
    """
    assert m_cfg.load_config.__defaults__ == (
        m_cfg.DEFAULT_CONFFILE, m_cfg.DEFAULT_CONFDIR,
    )


def test_load_config_default_file_missing(subtests, tmp_path):
    """
    Confirm that nothing bad happens if the default config file is missing.
    """
    with mock.patch(
        "medallion.config.DEFAULT_CONFFILE", str(tmp_path / "medallion.conf"),
    ) as mock_conf_file_default:
        with subtests.test(msg="conf_dir omitted"):
            config = m_cfg.load_config(conf_file=mock_conf_file_default)
            assert config == {}
        with subtests.test(msg="conf_dir is None"):
            config = m_cfg.load_config(
                conf_file=mock_conf_file_default, conf_dir=None,
            )
            assert config == {}


def test_load_config_non_default_file_missing(subtests, tmp_path):
    """
    Confirm an exception is raised if a non-default config file is missing.
    """
    conf_file = tmp_path / "missing.conf"
    exc_patt = re.escape(repr(str(conf_file)))
    with pytest.raises(FileNotFoundError, match=exc_patt):
        m_cfg.load_config(conf_file=conf_file)


def test_load_config_default_dir_missing(subtests, tmp_path):
    """
    Confirm that nothing bad happens if the default config dir is missing.
    """
    with mock.patch(
        "medallion.config.DEFAULT_CONFDIR", str(tmp_path / "medallion.d"),
    ) as mock_conf_dir_default:
        with subtests.test(msg="conf_file omitted"):
            config = m_cfg.load_config(conf_dir=mock_conf_dir_default,)
            assert config == {}
        with subtests.test(msg="conf_file is None"):
            config = m_cfg.load_config(
                conf_dir=mock_conf_dir_default, conf_file=None,
            )
            assert config == {}


def test_load_config_non_default_dir_missing(tmp_path):
    """
    Confirm an exception is raised if a non-default config dir is missing.
    """
    conf_dir = tmp_path / "missing.d"
    exc_patt = re.escape(repr(str(conf_dir)))
    with pytest.raises(FileNotFoundError, match=exc_patt):
        m_cfg.load_config(conf_dir=conf_dir)


def test_load_config_logging(subtests, tmp_path, caplog):
    """
    Ensure that config loading emits log messages about paths and data.
    """
    confdata = {"foo": "bar"}
    conf_file = tmp_path / "medallion.conf"
    json.dump(confdata, conf_file.open("w"))
    caplog.set_level(logging.DEBUG, logger="medallion.config")
    with subtests.test(msg="Used as config file"):
        assert m_cfg.load_config(conf_file=conf_file) == confdata
        # We put the single quotes in ourself to avoid Windows/UNIX path issues
        assert f"load configuration from '{str(conf_file)}'" in caplog.text
        for record in caplog.records:
            if '"foo": "bar"' in record.message:
                break
        else:
            raise AssertionError("Config data not seen in log output")
    caplog.clear()
    with subtests.test(msg="Used from config dir"):
        assert m_cfg.load_config(conf_dir=tmp_path) == confdata
        # We put the single quotes in ourself to avoid Windows/UNIX path issues
        assert f"and '{str(tmp_path)}'" in caplog.text
        for record in caplog.records:
            if '"foo": "bar"' in record.message:
                break
        else:
            raise AssertionError("Config data not seen in log output")


@pytest.mark.parametrize(
    "confdata", ({}, {"foo": "bar"}, {"foo": {"bar": ["baz", ]}}, )
)
def test_load_config_json_objects(confdata, subtests, tmp_path):
    """
    Confirm that config files get loaded correctly.
    """
    conf_file = tmp_path / "medallion.conf"
    json.dump(confdata, conf_file.open("w"))
    with subtests.test(msg="Used as config file"):
        assert m_cfg.load_config(conf_file=conf_file) == confdata
    with subtests.test(msg="Used from config dir"):
        assert m_cfg.load_config(conf_dir=tmp_path) == confdata


@pytest.mark.parametrize(
    "confdata", ([], ["foo", "bar"], "", 42, )
)
def test_load_config_file_json_not_objects(confdata, subtests, tmp_path):
    """
    Confirm that config files with non-JSON-object data are rejected.

    Specifically, we cannot allow the top level JSON type be anything other
    than an object since we rely on being able to merge objects from the
    various config files and the environment variable collection logic.
    """
    conf_file = tmp_path / "medallion.conf"
    json.dump(confdata, conf_file.open("w"))
    with subtests.test(msg="Used as config file"):
        with pytest.raises(TypeError, match="must contain a JSON object"):
            m_cfg.load_config(conf_file=conf_file)
    with subtests.test(msg="Used from config dir"):
        with pytest.raises(TypeError, match="must contain a JSON object"):
            m_cfg.load_config(conf_dir=tmp_path)


@pytest.mark.parametrize("confdata", (
    "", "[,]", "{,}",
    "'wrong quotes'", "{missing: quotes}", '{"trailing": "comma",}',
    "\x7FELFverywrong",
))
def test_load_config_file_bad_json(confdata, subtests, tmp_path):
    """
    Confirm that config files with non-JSON-object data are rejected.

    Specifically, we cannot allow the top level JSON type be anything other
    than an object since we rely on being able to merge objects from the
    various config files and the environment variable collection logic.
    """
    conf_file = tmp_path / "medallion.conf"
    conf_file.open("w").write(confdata)
    with subtests.test(msg="Used as config file"):
        with pytest.raises(ValueError, match="Invalid JSON") as exc:
            m_cfg.load_config(conf_file=conf_file)
        assert isinstance(exc.value.__cause__, json.decoder.JSONDecodeError)
    with subtests.test(msg="Used from a config dir"):
        with pytest.raises(ValueError, match="Invalid JSON") as exc:
            m_cfg.load_config(conf_dir=tmp_path)
        assert isinstance(exc.value.__cause__, json.decoder.JSONDecodeError)


def test_env_config_empty_env(subtests):
    """
    Confirm that the `MedallionConfig` return an empty dict from an empty env.

    This test module does this for all tests but an explicit one doesn't hurt!
    """
    env = expected = {}
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected


def test_env_config_taxii(subtests):
    """
    Confirm that the `MedallionConfig` can get TAXII config from the env.
    """
    env = {
        "MEDALLION_TAXII_MAX_PAGE_SIZE": "42",
    }
    expected = {
        "taxii": {
            "max_page_size": int(env["MEDALLION_TAXII_MAX_PAGE_SIZE"]),
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected


def test_env_config_backend_type(subtests):
    """
    Confirm that the `MedallionConfig` can get a backend type from the env.
    """
    env = {
        "MEDALLION_BACKEND_MODULE_CLASS": "MemoryBackend",
    }
    expected = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected


def test_env_config_backend_memory(subtests):
    """
    Confirm that the `MedallionConfig` can get `MemoryBackend` config.
    """
    env = {
        "MEDALLION_BACKEND_MODULE_CLASS": "MemoryBackend",
        "MEDALLION_BACKEND_MEMORY_FILENAME": "/path/to/nowhere",
    }
    expected = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            # This has to be flattened by the config loader
            env["MEDALLION_BACKEND_MODULE_CLASS"]: {
                "filename": env["MEDALLION_BACKEND_MEMORY_FILENAME"],
            },
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected

    expected_flat = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            "filename": env["MEDALLION_BACKEND_MEMORY_FILENAME"],
        },
    }
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected_flat


def test_env_config_backend_mongo(subtests):
    """
    Confirm that the `MedallionConfig` can get `MongoBackend` config.
    """
    env = {
        "MEDALLION_BACKEND_MODULE_CLASS": "MongoBackend",
        "MEDALLION_BACKEND_MONGO_URI": "mongodb://user:resu@localhost:27017/",
    }
    expected = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            # This has to be flattened by the config loader
            env["MEDALLION_BACKEND_MODULE_CLASS"]: {
                "uri": env["MEDALLION_BACKEND_MONGO_URI"],
            },
        },
    }
    with subtests.test(msg="Loading config directly"):
        assert m_cfg.MedallionConfig.from_environ(env).as_dict() == expected

    expected_flat = {
        "backend": {
            "module_class": env["MEDALLION_BACKEND_MODULE_CLASS"],
            "uri": env["MEDALLION_BACKEND_MONGO_URI"],
        },
    }
    with subtests.test(msg="Loading config via loader"):
        with mock.patch.dict("os.environ", **env, clear=True):
            config_data = m_cfg.load_config(conf_file=None, conf_dir=None)
        assert config_data == expected_flat
