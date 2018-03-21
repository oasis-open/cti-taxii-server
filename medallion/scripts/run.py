import argparse
import json
import textwrap

from medallion import (application_instance, get_config, init_backend,
                       register_blueprints, set_config, __version__)


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
        formatter_class=NewlinesHelpFormatter
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        type=str,
        help="The host to listen on."
    )

    parser.add_argument(
        "--port",
        default=5000,
        type=int,
        help="The port of the web server."
    )

    parser.add_argument(
        "--debug-mode",
        default=False,
        type=bool,
        help="If set, start application in debug mode.",
    )

    parser.add_argument(
        "CONFIG_PATH",
        metavar="CONFIG_PATH",
        type=str,
        help="The location of the JSON configuration file to use."
    )

    return parser


def main():
    medallion_parser = _get_argparser()
    medallion_args = medallion_parser.parse_args()

    with open(medallion_args.CONFIG_PATH, "r") as f:
        set_config(json.load(f))

    init_backend(get_config()["backend"])
    register_blueprints(application_instance)

    application_instance.run(
        host=medallion_args.host,
        port=medallion_args.port,
        debug=medallion_args.debug_mode
    )


if __name__ == "__main__":
    main()
