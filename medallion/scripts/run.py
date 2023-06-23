import argparse
import inspect
import logging
import os
import textwrap

from medallion import __version__, create_app
import medallion.config

log = logging.getLogger("medallion")


class NewlinesHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter to insert newlines between argument help texts.
    """
    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(" ", text).strip()
        txt = textwrap.wrap(text, width)
        txt[-1] += "\n"
        return txt


def _get_argparser():
    """Create and return an ArgumentParser for this application."""
    desc = "medallion v{0}".format(__version__)
    parser = argparse.ArgumentParser(
        description=desc,
        formatter_class=NewlinesHelpFormatter,
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        type=str,
        help="The host to listen on.",
    )

    parser.add_argument(
        "--port",
        default=5000,
        type=int,
        help="The port of the web server.",
    )

    parser.add_argument(
        "--debug-mode",
        default=False,
        action="store_true",
        help="If set, start application in debug mode.",
    )

    parser.add_argument(
        "--log-level",
        default="WARN",
        type=str,
        help="The logging output level for medallion.",
        choices=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
    )

    config_path_group = parser.add_mutually_exclusive_group()
    config_path_group.add_argument(
        "CONFIG_PATH",
        metavar="CONFIG_PATH",
        nargs="?",
        type=str,
        help=inspect.cleandoc("""
            Deprecated argument for specifying a single JSON configuration
            file. Do not specify this and `--conf-file`.
        """),
    )
    config_path_group.add_argument(
        "-c", "--conf-file",
        default=os.environ.get(
            "MEDALLION_CONFFILE", medallion.config.DEFAULT_CONFFILE
        ),
        help=inspect.cleandoc(f"""
            Path to a single configuration file. Defaults to the value of
            the MEDALLION_CONFFILE environment variable or
            {medallion.config.DEFAULT_CONFFILE}.
        """),
    )
    config_dir_group = parser.add_mutually_exclusive_group()
    config_dir_group.add_argument(
        "--conf-dir",
        default=os.environ.get(
            "MEDALLION_CONFDIR", medallion.config.DEFAULT_CONFDIR
        ),
        help=inspect.cleandoc(f"""
            Path to a directory containing JSON configuration files with names
            ending in .json or .conf. Defaults to the value of the
            MEDALLION_CONFDIR environment variable or
            {medallion.config.DEFAULT_CONFDIR}.
        """),
    )
    config_dir_group.add_argument(
        "--no-conf-dir",
        action="store_true",
        help=inspect.cleandoc("""
            Disable the use of any configuration directory as described for
            --conf-dir. This may be used to ensure that the default or some
            value from the environment is not used.
        """),
    )
    parser.add_argument(
        "--conf-check", action="store_true",
        help="Evaluate medallion configuration without running the server.",
    )

    return parser


def main():
    medallion_parser = _get_argparser()
    medallion_args = medallion_parser.parse_args()
    # Configuration checking sets up debug logging and does not run the app
    if medallion_args.conf_check:
        medallion_args.log_level = logging.DEBUG
    log.setLevel(medallion_args.log_level)

    configuration = medallion.config.load_config(
        medallion_args.CONFIG_PATH or medallion_args.conf_file,
        medallion_args.conf_dir if not medallion_args.no_conf_dir else None,
    )

    app = create_app(configuration)

    if not medallion_args.conf_check:
        app.run(
            host=medallion_args.host,
            port=medallion_args.port,
            debug=medallion_args.debug_mode,
        )


if __name__ == "__main__":
    main()
