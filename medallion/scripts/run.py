import json
import sys
import os.path
import sys

from flask import Flask, url_for, render_template
from medallion import (init, register_blueprints)


def main():

    if len(sys.argv) < 2:
        raise ValueError("No config file specified")

    config_file_path = sys.argv[1]
    if os.path.isfile(config_file_path) and os.path.getsize(config_file_path) > 0:
        with open(config_file_path, 'r') as f:
            config = None
            try:
                config = json.load(f)
            except ValueError:
                raise ValueError("File {0} contains invalid JSON".format(config_file_path))
            init(config)

    else:
        raise ValueError("File {0} is empty or not present".format(config_file_path))

    application_instance = Flask(__name__)

    register_blueprints(application_instance)

    application_instance.run(debug=True)


if __name__ == '__main__':
    main()
