#!/usr/bin/env python

import argparse
import textwrap

import six
from werkzeug.security import check_password_hash, generate_password_hash

from medallion import __version__


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
    desc = "medallion generate-user-password script v{0}".format(__version__)
    parser = argparse.ArgumentParser(
        description=desc,
        formatter_class=NewlinesHelpFormatter,
    )

    parser.add_argument(
        "--hash-method",
        default="sha256",
        type=str,
        help="The hash method to use (one that hashlib supports).",
    )

    parser.add_argument(
        "--salt-length",
        default=8,
        type=int,
        help="The length of the salt in letters.",
    )

    return parser


def main():
    parser = _get_argparser()
    args = parser.parse_args()
    method = "pbkdf2:{}".format(args.hash_method)
    salt_length = args.salt_length

    password = six.moves.input("password:\t")
    password_hash = generate_password_hash(password, method=method, salt_length=salt_length)

    password = six.moves.input("verify:\t\t")
    if check_password_hash(password_hash, password):
        print(password_hash)
    else:
        print("Failure!")


if __name__ == '__main__':
    main()
