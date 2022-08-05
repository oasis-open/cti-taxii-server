import logging
from unittest import mock

import pytest
import pytest_subtests  # noqa: F401

import medallion.common
import medallion.config
import medallion.scripts.run

pytestmark = pytest.mark.usefixtures("empty_environ")


def test_parser_help(capsys):
    """
    Confirm that the parser help can be printed with the custom formatter.
    """
    parser = medallion.scripts.run._get_argparser()
    parser.print_help()
    (out, _) = capsys.readouterr()
    assert "medallion v" in out


def test_config_path(subtests):
    """
    Confirm that the positional CONFIG_PATH argument works as expected.
    """
    config_path_arg = "/we're/on/the/road/to/nowhere"
    parser = medallion.scripts.run._get_argparser()
    with subtests.test(msg="CONFIG_PATH provided"):
        args = parser.parse_args([config_path_arg])
        assert args.CONFIG_PATH == config_path_arg
    with subtests.test(msg="CONFIG_PATH omitted"):
        args = parser.parse_args([])
        assert args.CONFIG_PATH is None


def test_conffile(subtests):
    """
    Confirm that the --conf-file option works as expected.
    """
    config_path_arg = "/we're/on/the/road/to/nowhere"
    parser = medallion.scripts.run._get_argparser()
    with subtests.test(msg="--conf-file omitted"):
        args = parser.parse_args([])
        assert args.conf_file == medallion.config.DEFAULT_CONFFILE
    with subtests.test(msg="--conf-file with space"):
        args = parser.parse_args(["--conf-file", config_path_arg])
        assert args.conf_file == config_path_arg
    with subtests.test(msg="--conf-file with equals"):
        args = parser.parse_args([f"--conf-file={config_path_arg}"])
        assert args.conf_file == config_path_arg
    with subtests.test(msg="MEDALLION_CONFFILE envvar"):
        with mock.patch.dict(
            "os.environ", {"MEDALLION_CONFFILE": config_path_arg}
        ):
            # We need to make a new parser after mocking the environment
            parser_with_envvar = medallion.scripts.run._get_argparser()
            args = parser_with_envvar.parse_args([])
        assert args.conf_file == config_path_arg


def test_confdir(subtests):
    """
    Confirm that the --conf-dir option works as expected.
    """
    config_path_arg = "/we're/on/the/road/to/nowhere"
    parser = medallion.scripts.run._get_argparser()
    with subtests.test(msg="--conf-dir omitted"):
        args = parser.parse_args([])
        assert args.conf_dir == medallion.config.DEFAULT_CONFDIR
    with subtests.test(msg="--conf-dir with space"):
        args = parser.parse_args(["--conf-dir", config_path_arg])
        assert args.conf_dir == config_path_arg
    with subtests.test(msg="--conf-dir with equals"):
        args = parser.parse_args([f"--conf-dir={config_path_arg}"])
        assert args.conf_dir == config_path_arg
    with subtests.test(msg="MEDALLION_CONFDIR envvar"):
        with mock.patch.dict(
            "os.environ", {"MEDALLION_CONFDIR": config_path_arg}
        ):
            # We need to make a new parser after mocking the environment
            parser_with_envvar = medallion.scripts.run._get_argparser()
            args = parser_with_envvar.parse_args([])
        assert args.conf_dir == config_path_arg


def test_noconfdir(subtests):
    """
    Confirm that the --no-conf-dir option works as expected.
    """
    class ExpectedException(BaseException):
        pass

    parser = medallion.scripts.run._get_argparser()
    with subtests.test(msg="--no-conf-dir omitted"):
        args = parser.parse_args([])
        assert args.no_conf_dir is False
    with subtests.test(msg="--no-conf-dir provided without a value"):
        args = parser.parse_args(["--no-conf-dir"])
        assert args.no_conf_dir is True
    with subtests.test(msg="--conf-dir with equals"):
        with mock.patch.object(
            parser, "error", side_effect=ExpectedException,
        ) as mock_error, pytest.raises(ExpectedException):
            parser.parse_args(["--no-conf-dir=1"])
        mock_error.assert_called_once()
        (expected_call, ) = mock_error.mock_calls
        (msg, ) = expected_call[1]
        assert "ignored explicit argument" in msg


def test_config_args_mutex(subtests):
    """
    Confirm that certain arguments and options are mutually exclusive.
    """
    class ExpectedException(BaseException):
        pass

    config_path_arg = "/we're/on/the/road/to/nowhere"
    parser = medallion.scripts.run._get_argparser()

    with subtests.test(msg="CONFIG_PATH and --conf-file provided"):
        with mock.patch.object(
            parser, "error", side_effect=ExpectedException,
        ) as mock_error, pytest.raises(ExpectedException):
            parser.parse_args([
                "--conf-file", config_path_arg,
                config_path_arg,
            ])
        mock_error.assert_called_once()
        (expected_call, ) = mock_error.mock_calls
        (msg, ) = expected_call[1]
        assert "not allowed with argument" in msg

    with subtests.test(msg="--conf-dir and --no-conf-dir provided"):
        with mock.patch.object(
            parser, "error", side_effect=ExpectedException,
        ) as mock_error, pytest.raises(ExpectedException):
            parser.parse_args([
                "--conf-dir", config_path_arg,
                "--no-conf-dir",
            ])
        mock_error.assert_called_once()
        (expected_call, ) = mock_error.mock_calls
        (msg, ) = expected_call[1]
        assert "not allowed with argument" in msg


@mock.patch("medallion.APPLICATION_INSTANCE.run")
def test_confcheck(mock_app, subtests):

    class ExpectedException(BaseException):
        pass

    """
    Confirm that the --conf-check option works as expected.
    """
    with subtests.test(msg="--conf-check omitted"):
        with mock.patch(
            "medallion.scripts.run.log"
        ) as mock_logger, mock.patch(
            "sys.argv", ["ARGV0", "-c", "medallion/test/data/config.json"]
        ):
            medallion.scripts.run.main()
        # default `--log-level` value
        mock_logger.setLevel.assert_called_once_with("WARN")
        assert mock_app.call_count == 1
    mock_app.reset_mock()

    with subtests.test(msg="--conf-check provided without a value"):
        with mock.patch(
            "medallion.scripts.run.log"
        ) as mock_logger, mock.patch(
            "sys.argv", ["ARGV0", "--conf-check", "-c", "medallion/test/data/config.json"]
        ):
            medallion.scripts.run.main()
        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
        mock_app.assert_not_called()
    mock_app.reset_mock()

    with subtests.test(msg="--conf-check with equals"):
        with mock.patch(
            "sys.argv", ["ARGV0", "--conf-check=1"]
        ), mock.patch(
            "argparse.ArgumentParser.error", side_effect=ExpectedException,
        ) as mock_error, pytest.raises(ExpectedException):
            medallion.scripts.run.main()
        mock_error.assert_called_once()
        (expected_call, ) = mock_error.mock_calls
        (msg, ) = expected_call[1]
        assert "ignored explicit argument" in msg
    mock_app.reset_mock()

    with subtests.test(msg="--conf-check overrides --log-level"):
        with mock.patch(
            "medallion.scripts.run.log"
        ) as mock_logger, mock.patch(
            "sys.argv", ["ARGV0", "--conf-check", "--log-level=CRITICAL", "-c", "medallion/test/data/config.json"]
        ):
            medallion.scripts.run.main()
        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
        mock_app.assert_not_called()


def test_main_config_arg_handling(subtests):
    """
    Confirm that config arguments and options in `argv` are respected when run.
    """
    config_file_arg = "/we're/on/the/road/to/nowhere"
    config_dir_arg = "/i/wanna/really/really/really/wanna/zigazig/dir/"
    # We need to provide this to satisfy the backend module loading code
    safe_config = {"backend": {"module_class": "MemoryBackend"}}
    default_medallion_kwargs = {
        "host": "127.0.0.1",
        "port": 5000,
        "debug": False,
    }

    with mock.patch(
        "medallion.scripts.run.APPLICATION_INSTANCE",
    ) as mock_app, mock.patch(
        "medallion.current_app", new=mock_app,
    ), mock.patch(
        "medallion.config.load_config", return_value=safe_config,
    ) as mock_load_config, mock.patch("medallion.scripts.run.APPLICATION_INSTANCE.backend_config", None):
        with subtests.test(msg="No config args provided"):
            with mock.patch(
                "sys.argv", ["ARGV0"]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                medallion.config.DEFAULT_CONFFILE,
                medallion.config.DEFAULT_CONFDIR,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="CONFIG_PATH provided only"):
            with mock.patch(
                "sys.argv", ["ARGV0", config_file_arg]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                config_file_arg, medallion.config.DEFAULT_CONFDIR,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="--conf-file provided only"):
            with mock.patch(
                "sys.argv", ["ARGV0", "--conf-file", config_file_arg]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                config_file_arg, medallion.config.DEFAULT_CONFDIR,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="--conf-dir provided only"):
            with mock.patch(
                "sys.argv", ["ARGV0", "--conf-dir", config_dir_arg]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                medallion.config.DEFAULT_CONFFILE, config_dir_arg,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="CONFIG_PATH before --conf-dir"):
            with mock.patch(
                "sys.argv",
                ["ARGV0", config_file_arg, "--conf-dir", config_dir_arg]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                config_file_arg, config_dir_arg,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="CONFIG_PATH after  --conf-dir"):
            with mock.patch(
                "sys.argv",
                ["ARGV0", "--conf-dir", config_dir_arg, config_file_arg]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                config_file_arg, config_dir_arg,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="--conf-file and --conf-dir"):
            with mock.patch(
                "sys.argv", [
                    "ARGV0",
                    "--conf-file", config_file_arg,
                    "--conf-dir", config_dir_arg,
                ]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                config_file_arg, config_dir_arg,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="CONFIG_PATH and --no-conf-dir"):
            with mock.patch(
                "sys.argv",
                ["ARGV0", config_file_arg, "--no-conf-dir"]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                config_file_arg, None,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()

        with subtests.test(msg="--conf-file and --no-conf-dir"):
            with mock.patch(
                "sys.argv",
                ["ARGV0", "--conf-file", config_file_arg, "--no-conf-dir"]
            ):
                medallion.scripts.run.main()
            mock_load_config.assert_called_once_with(
                config_file_arg, None,
            )
            mock_app.run.assert_called_once_with(**default_medallion_kwargs)
        mock_app.reset_mock()
        mock_load_config.reset_mock()


def test_get_flask_config_values():
    # We don't need a real Flask instance to test this; we just need
    # something we can hang some attribute values off of.
    class fake_app:
        taxii_config = {"key1": "value1"}
        users_config = {"key2": "value2"}
        backend_config = {"key3": "value3"}

    result = medallion.common.get_application_instance_config_values(fake_app, "taxii")
    assert result == {"key1": "value1"}

    result = medallion.common.get_application_instance_config_values(fake_app, "taxii", "key1")
    assert result == "value1"

    result = medallion.common.get_application_instance_config_values(fake_app, "users")
    assert result == {"key2": "value2"}

    result = medallion.common.get_application_instance_config_values(fake_app, "users", "key2")
    assert result == "value2"

    result = medallion.common.get_application_instance_config_values(fake_app, "backend")
    assert result == {"key3": "value3"}

    result = medallion.common.get_application_instance_config_values(fake_app, "backend", "key3")
    assert result == "value3"
