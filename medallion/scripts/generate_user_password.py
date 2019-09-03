#!/usr/bin/env python

from __future__ import print_function

import six
from werkzeug.security import check_password_hash, generate_password_hash

if __name__ == '__main__':
    password = six.moves.input("password: ")
    password_hash = generate_password_hash(password)
    password = six.moves.input("verify: ")
    if check_password_hash(password_hash, password):
        print(password_hash)
    else:
        print("Failure!")
