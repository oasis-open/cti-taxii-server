import datetime
import json
import os
import uuid

from medallion.backends.taxii.base import Backend
from medallion.exceptions import ProcessingError
from medallion.filters.basic_filter import BasicFilter
from medallion.utils.common import create_bundle, generate_status


class DirectoryBackend(Backend):
    # access control is handled at the views level

    def __init__(self, path=None, **kwargs):
        self.path = path
        self.discovery_config = self.init_discovery_config(kwargs.get('discovery', None))
        self.api_root_config = self.init_api_root_config(kwargs.get('api-root', None))
        self.collection_config = self.init_collection_config(kwargs.get('collection', None))
        self.cache = {}
        self.statuses = []

    # noinspection PyMethodMayBeStatic
    def init_discovery_config(self, discovery_config):
        if not self.path:
            raise ProcessingError('path was not specified in the config file', 400)

        if not os.path.isdir(self.path):
            raise ProcessingError("directory '{}' was not found".format(self.path), 500)

        return discovery_config

    def update_discovery_config(self):
        dc = self.discovery_config
        collection_dirs = sorted([f for f in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, f))])

        if not collection_dirs:
            raise ProcessingError('at least one api-root directory is required', 500)

        updated_roots = ['{}{}/'.format(dc['host'], f) for f in collection_dirs]

        self.discovery_config['default'] = updated_roots[0]
        self.discovery_config['api_roots'] = updated_roots

    # noinspection PyMethodMayBeStatic
    def init_api_root_config(self, api_root_config):
        if api_root_config:
            return api_root_config
        else:
            raise ProcessingError('api-root was not specified in the config file', 400)

    # noinspection PyMethodMayBeStatic
    def init_collection_config(self, collection_config):
        if collection_config:
            return collection_config
        else:
            raise ProcessingError('collection was not specified in the config file', 400)

    def validate_requested_api_root(self, requested_api_root):
        api_roots = self.discovery_config['api_roots']

        host_port = self.discovery_config['default'].rsplit('/', 2)[0]

        full_api_root = '{}/{}/'.format(host_port, requested_api_root)

        return full_api_root in api_roots

    def server_discovery(self):
        self.update_discovery_config()
        return self.discovery_config

    def get_api_root_information(self, api_root):
        self.update_discovery_config()

        api_roots = self.discovery_config['api_roots']

        for r in api_roots:
            c_dir = r.rsplit('/', 2)[1]

            if api_root == c_dir:
                i_title = "Indicators from directory '{}'".format(c_dir)

                i = {
                    "title": i_title,
                    "description": "",
                    "versions": self.api_root_config['versions'],
                    "max-content-length": self.api_root_config['max-content-length']
                }

                return i

    def get_collections(self, api_root, start_index, end_index):
        self.update_discovery_config()

        api_roots = self.discovery_config['api_roots']

        collections = []

        # Generate a collection object for each api_root
        for r in api_roots:
            c_dir = r.rsplit('/', 2)[1]

            if api_root == c_dir:
                c_id = uuid.uuid3(uuid.NAMESPACE_URL, r)
                c_title = "Indicators from directory '{}'".format(c_dir)

                c = {
                    "id": str(c_id),
                    "title": c_title,
                    "description": self.collection_config['description'],
                    "can_read": self.collection_config['can_read'],
                    "can_write": self.collection_config['can_write'],
                    "media_types": self.collection_config['media_types']
                }

                collections.append(c)

        count = len(collections)

        collections = collections if end_index == -1 else collections[start_index:end_index]

        return count, collections

    def get_collection(self, api_root, collection_id):
        count, collections = self.get_collections(api_root, 0, -1)

        for c in collections:
            if 'id' in c and collection_id == c['id']:
                return c

    def set_modified_time_stamp(self, objects, modified):
        for o in objects:
            o['modified'] = modified

        return objects

    def get_modified_time_stamp(self, fp):
        fp_modified = os.path.getmtime(fp)
        dt = datetime.datetime.utcfromtimestamp(fp_modified)
        modified = '{:%Y-%m-%dT%H:%M:%S.%fZ}'.format(dt)

        return modified

    def delete_from_cache(self, api_root):
        p = os.path.join(self.path, api_root)
        files = [f for f in os.listdir(p) if os.path.isfile(os.path.join(p, f)) and f.endswith('.json')]

        for f in self.cache[api_root]['files'].keys():
            if f not in files:
                del self.cache[api_root]['files'][f]

    def add_to_cache(self, api_root, api_root_modified, file_name, file_modified):
        fp = os.path.join(self.path, api_root, file_name)

        u_objects = []

        with open(fp, 'r') as raw_json:
            try:
                stix2 = json.load(raw_json)

                if stix2.get('type', '') == 'bundle' and stix2.get('spec_version', '') == '2.0':
                    objects = stix2.get('objects', [])
                    u_objects = self.set_modified_time_stamp(objects, file_modified)

                    if api_root not in self.cache:
                        self.cache[api_root] = {'modified': '', 'files': {}}

                    self.cache[api_root]['modified'] = api_root_modified
                    self.cache[api_root]['files'][file_name] = {'modified': file_modified, 'objects': u_objects}
            except Exception as e:
                raise ProcessingError('error adding objects to cache', 500, e)
            finally:
                return u_objects

    def with_cache(self, api_root):
        api_root_path = os.path.join(self.path, api_root)
        api_root_modified = self.get_modified_time_stamp(api_root_path)

        if api_root in self.cache:
            if self.cache[api_root]['modified'] == api_root_modified:
                # Return objects from cache
                objects = []
                for k, v in self.cache[api_root]['files'].items():
                    objects.extend(v['objects'])
                return objects
            else:
                # Cleanup the cache
                self.delete_from_cache(api_root)

                # Add to the cache and return objects for collection
                dir_list = os.listdir(api_root_path)
                files = [f for f in dir_list if os.path.isfile(os.path.join(api_root_path, f)) and f.endswith('.json')]

                objects = []
                for f in files:
                    fp = os.path.join(api_root_path, f)
                    file_modified = self.get_modified_time_stamp(fp)

                    cached_files = self.cache[api_root]['files']
                    if f in cached_files and cached_files[f]['modified'] == file_modified:
                        objects.extend(cached_files[f]['objects'])
                    else:
                        u_objects = self.add_to_cache(api_root, api_root_modified, f, file_modified)
                        objects.extend(u_objects)
                return objects
        else:
            # Update the cache and return the objects for the collection
            dir_list = os.listdir(api_root_path)
            files = [f for f in dir_list if os.path.isfile(os.path.join(api_root_path, f)) and f.endswith('.json')]

            objects = []
            for f in files:
                fp = os.path.join(api_root_path, f)
                file_modified = self.get_modified_time_stamp(fp)

                u_objects = self.add_to_cache(api_root, api_root_modified, f, file_modified)
                objects.extend(u_objects)
            return objects

    def get_objects_without_bundle(self, api_root, collection_id, filter_args, allowed_filters):
        self.update_discovery_config()

        if self.validate_requested_api_root(api_root):
            # Get the collection
            collection = None
            num_collections, collections = self.get_collections(api_root, 0, -1)

            for c in collections:
                if 'id' in c and collection_id == c['id']:
                    collection = c
                    break

            if not collection:
                raise ProcessingError("collection for api-root '{}' was not found".format(api_root), 500)

            # Add the objects to the collection
            collection['objects'] = self.with_cache(api_root)

            # Filter the collection
            filtered_objects = []

            if filter_args:
                full_filter = BasicFilter(filter_args)
                filtered_objects.extend(
                    full_filter.process_filter(
                        collection.get('objects', []),
                        allowed_filters,
                        collection.get('manifest', [])
                    )
                )
            else:
                filtered_objects.extend(collection.get('objects', []))

            return filtered_objects

    def get_objects(self, api_root, collection_id, filter_args, allowed_filters, start_index, end_index):
        # print('start_index: {}, end_index: {}'.format(start_index, end_index))

        objects = self.get_objects_without_bundle(api_root, collection_id, filter_args, allowed_filters)

        objects.sort(key=lambda x: datetime.datetime.strptime(x['modified'], '%Y-%m-%dT%H:%M:%S.%fZ'))

        count = len(objects)

        objects = objects if end_index == -1 else objects[start_index:end_index]

        return count, create_bundle(objects)

    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        objects = self.get_objects_without_bundle(api_root, collection_id, filter_args, allowed_filters)

        req_object = [i for i in objects if i['id'] == object_id]

        if len(req_object) == 1:
            return create_bundle(req_object)

    def get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters, start_index, end_index):
        self.update_discovery_config()

        if self.validate_requested_api_root(api_root):
            count, collections = self.get_collections(api_root, 0, -1)

            for collection in collections:
                if 'id' in collection and collection_id == collection['id']:
                    manifest = collection.get('manifest', [])
                    if filter_args:
                        full_filter = BasicFilter(filter_args)
                        manifest = full_filter.process_filter(
                            manifest,
                            allowed_filters,
                            None
                        )

                    count = len(manifest)

                    manifest = manifest if end_index == -1 else manifest[start_index:end_index]

                    return count, manifest

    def add_objects(self, api_root, collection_id, objs, request_time):
        failed = 0
        succeeded = 0
        pending = 0
        successes = []
        failures = []

        file_name = '{}--{}.{}'.format(request_time, objs['id'], 'json')
        p = os.path.join(self.path, api_root)
        fp = os.path.join(p, file_name)

        try:
            add_objs = objs['objects']
            num_objs = len(add_objs)

            try:
                # Each add_object request writes the provided bundle to a new file
                with open(fp, 'w') as out_file:
                    out_file.write(json.dumps(objs, indent=4, sort_keys=True))

                    succeeded += num_objs
                    successes = list(map(lambda x: x['id'], add_objs))

                # Update the cache after the file is written
                self.with_cache(api_root)
            except IOError:
                failed += num_objs
                failures = list(map(lambda x: x['id'], add_objs))

        except Exception as e:
            raise ProcessingError('error adding objects', 500, e)

        status = generate_status(request_time, 'complete', succeeded, failed,
                                 pending, successes_ids=successes, failures=failures)

        self.statuses.append(status)

        return status

    def get_status(self, api_root, status_id):
        for s in self.statuses:
            if status_id == s['id']:
                return s
