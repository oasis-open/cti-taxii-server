import json
import sys

from medallion import (application_instance, get_config, init_backend,
                       set_config)


def main():

    if len(sys.argv) < 2:
        raise ValueError("No config file")
    config_file_path = sys.argv[1]
    with open(config_file_path, 'r') as f:
        set_config(json.load(f))

    init_backend(get_config()['backend'])

    application_instance.run(debug=True)


if __name__ == '__main__':
    main()
