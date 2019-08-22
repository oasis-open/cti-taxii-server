import argparse
import datetime
import json
import uuid
import sys
import six

from werkzeug.security import generate_password_hash

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


def make_connection(uri):
    try:
        client = MongoClient(uri)
        # The ismaster command is cheap and does not require auth.
        client.admin.command("ismaster")

        return client
    except ConnectionFailure:
        print("Unable to establish a connection to MongoDB server {}".format(uri))


def add_auth_data_from_file(client, data):
    # Insert the new user.
    db = client['auth']
    users = db['users']

    data['user']['created'] = '{:%Y-%m-%dT%H:%M:%S}'.format(datetime.datetime.utcnow())

    users.insert_one(data['user'])

    api_keys = db['api_keys']

    data['api_key']['created'] = '{:%Y-%m-%dT%H:%M:%S}'.format(datetime.datetime.utcnow())

    api_keys.insert_one(data['api_key'])


def add_api_key_for_user(client, email):
    api_key = str(uuid.uuid4()).replace('-', '')
    api_key_obj = {
        "_id": api_key,
        "user_id": email,
        "created": '{:%Y-%m-%dT%H:%M:%S}'.format(datetime.datetime.utcnow()),
        "last_used_at": "",
        "last_used_from": ""
    }

    # Check that the user exists. If the user exists, insert the new api_key, and update the corresponding user.
    db = client['auth']
    users = db['users']
    user = users.find_one({"_id": email})

    if user:
        # Add an api key and print it.
        api_keys = db['api_keys']
        api_keys.insert_one(api_key_obj)

        print("new api key: {} added for email: {}".format(api_key, email))
    else:
        print("no user with email: {} was found in the database.".format(email))


def add_user(client, user):
    # Insert the new user.
    db = client['auth']
    users = db['users']
    users.insert_one(user)


def main():
    uri = "mongodb://root:example@localhost:27017/"

    parser = argparse.ArgumentParser('%prog [OPTIONS]', description='Auth DB Utils')

    group = parser.add_mutually_exclusive_group()

    parser.add_argument('--uri', dest='uri', default=uri, help='Set the Mongo DB connection information')

    group.add_argument('-f', '--file', dest='file', help='Add a user with API key to the Auth DB')
    group.add_argument('-u', '--user', dest='user', action='store_true', help='Add a user to the Auth DB')
    group.add_argument('-k', '--apikey', dest='apikey', action='store_true', help='Add an API key to an existing user')

    args = parser.parse_args()

    client = make_connection(args.uri)

    if args.file is not None:
        with open(args.file, 'r') as i:
            data = json.load(i)
            add_auth_data_from_file(client, data)
    elif args.user:
        email = six.moves.input('email address      : ').strip()

        password1 = six.moves.input('password           : ').strip()
        password2 = six.moves.input('verify password    : ').strip()

        if password1 != password2:
            sys.exit('passwords were not the same')

        company_name = six.moves.input('company name       : ').strip()
        contact_name = six.moves.input('contact name       : ').strip()
        add_api_key = six.moves.input('add api key (y/n)? : ').strip()

        password_hash = generate_password_hash(password1)

        user = {
            "_id": email,
            "password": password_hash,
            "company_name": company_name,
            "contact_name": contact_name,
            "created": '{:%Y-%m-%dT%H:%M:%S}'.format(datetime.datetime.utcnow()),
            "updated": ""
        }

        add_user(client, user)

        if add_api_key.lower() == 'y':
            add_api_key_for_user(client, email)
    elif args.apikey:
        email = six.moves.input('email address      : ')

        add_api_key_for_user(client, email)


if __name__ == "__main__":
    main()
