import logging
from urllib.parse import urlparse

from ..common import APPLICATION_INSTANCE, TaskChecker, get_application_instance_config_values
from ..exceptions import InitializationError

# Module-level logger
log = logging.getLogger(__name__)

SECONDS_IN_24_HOURS = 24*60*60


def get_api_root_name(url):
    pr = urlparse(url)
    return pr.path.replace("/", "")


class BackendRegistry(type):
    __SUBCLASS_MAP = dict()

    def __new__(mcls, name, bases, attrs):
        clsobj = super(BackendRegistry, mcls).__new__(mcls, name, bases, attrs)
        mcls.register(name, clsobj)
        return clsobj

    @classmethod
    def register(mcls, kind, clsobj):
        if mcls.__SUBCLASS_MAP.get(kind, clsobj) is not clsobj:
            raise ValueError(
                "Backend name {!r} registered more than once"
                .format(kind)
            )
        mcls.__SUBCLASS_MAP[kind] = clsobj

    @classmethod
    def get(mcls, kind):
        return mcls.__SUBCLASS_MAP[kind]

    @classmethod
    def iter_(mcls):
        yield from mcls.__SUBCLASS_MAP.items()


class Backend(object, metaclass=BackendRegistry):

    def __init__(self, **kwargs):
        self.next = {}

        if kwargs.get("run_cleanup_threads", True):
            self.timeout = kwargs.get("session_timeout", 30)
            checker = TaskChecker(kwargs.get("check_interval", 10), self._pop_expired_sessions)
            checker.start()

            self.status_retention = kwargs.get("status_retention", SECONDS_IN_24_HOURS)
            if self.status_retention != -1:
                if self.status_retention < SECONDS_IN_24_HOURS and get_application_instance_config_values(APPLICATION_INSTANCE,
                                                                                                          "backend",
                                                                                                          "interop_requirements"):
                    # interop MUST requirement
                    raise InitializationError("Status retention interval must be more than 24 hours", 408)
                status_checker = TaskChecker(kwargs.get("check_interval", 10), self._pop_old_statuses)
                status_checker.start()
        else:
            if get_application_instance_config_values(APPLICATION_INSTANCE,
                                                      "backend",
                                                      "interop_requirements"):
                # interop MUST requirement
                raise InitializationError("Status retention interval must be more than 24 hours", 408)

    def _get_all_api_roots(self):
        discovery_info = self.server_discovery()
        return [get_api_root_name(x) for x in discovery_info["api_roots"]]

    def _get_api_root_statuses(self, api_root):
        """
        Fill:
            Returns the statuses of the given api root

        Args:
            api_root -

        Returns:
            list of statuses

        """
        raise NotImplementedError()

    def server_discovery(self):
        """
        Fill:
            Returns the discovery information (api_roots, etc) for this server

        Args:
            -none-

        Returns:
            discovery information

        """
        raise NotImplementedError()

    def get_collections(self, api_root):
        """
        Fill:
            Implement the get_collections TAXII endpoint by obtaining the collection metadata
            for this api_root

        Args:
            api_root (str): the name of the api_root.

        Returns:
            tuple containing the total count, and metadata for all collections at this api root

        """
        raise NotImplementedError()

    def get_collection(self, api_root, collection_id):
        """
        Fill:
            Implement the get_collection TAXII service by obtaining the collection metadata
            for collection

        Args:
            api_root (str): the name of the api_root.
            collection_id (str): the id of the collection

        Returns:
            collection metadata

        """
        raise NotImplementedError()

    def get_object_manifest(self, api_root, collection_id, filter_args, allowed_filters, limit):
        """
        Fill:
            Implement the get_object_manifest TAXII endpoint by obtaining the metadata
            for the selected objects

        Args:
            api_root (str): the name of the api_root.
            collection_id (str): the id of the collection
            filter_args (werkzeug.datastructures.ImmutableMultiDict): query string from URL
                containing filter args
            allowed_filters (tuple): STIX properties which are allowed in the filter for this endpoint
            limit (int): Used for pagination requests. limits objects to the amount specified

        Returns:
            tuple containing the total count of matching objects, and a collection of metadata for the objects

        """
        raise NotImplementedError()

    def get_api_root_information(self, api_root):
        """
        Fill:
            Implement the get_api_root_information TAXII endpoint by obtaining api_root metadata

        Args:
            api_root (str): the name of the api_root.

        Returns:
            metadata for the api root

        """
        raise NotImplementedError()

    def get_status(self, api_root, status_id):
        """
        Fill:
            Implement the get_status TAXII endpoint by obtaining the status of an add_objects request

        Args:
            api_root (str): the name of the api_root.
            status_id (str): the id of the add_objects request

        Returns:
            status of the request (including):
                how many objects were successful saved
                how many objects failed to be saved
                how many objects are pending

        """
        raise NotImplementedError()

    def get_objects(self, api_root, collection_id, filter_args, allowed_filters, limit):
        """
        Fill:
            Implement the get_objects TAXII endpoint by obtaining the data from a collection

        Args:
            api_root (str): the name of the api_root.
            collection_id (str): the id of the collection
            filter_args (werkzeug.datastructures.ImmutableMultiDict): query string from URL
                containing filter args
            allowed_filters (tuple): STIX properties which are allowed in the filter for this endpoint
            limit (int): Used for pagination requests. limits objects to the amount specified

        Returns:
            tuple containing the total count of matching objects, and a collection of objects containing
            the data from the collection that satisfies the filter

        """
        raise NotImplementedError()

    def add_objects(self, api_root, collection_id, objs, request_time):
        """
        Fill:
            Implement the add_objects TAXII endpoint by save data into a collection

        Args:
            api_root (str): the name of the api_root.
            collection_id (str): the id of the collection
            objs (dict): bundle containing objects to insert into the collection
            request_time (str): a formatted timestamp string with the time of the request

        Returns:
            status of the request (including):
                how many objects were successful saved
                how many objects failed to be saved
                how many objects are pending

        METADATA ABOUT EACH SUCCESSFUL OBJECT SAVED MUST BE AVAILABLE VIA THE get_object_manifest API CALL
        THIS CAN BE IMPLEMENTED AS A SEPARATE STORE, OTHERWISE IT NEEDS TO BE GENERATABLE DYNAMICALLY

        """
        raise NotImplementedError()

    def get_object(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):
        """
        Fill:
            Implement the get_object TAXII endpoint by obtaining the data from a collection related
            to the object_id

        Args:
            api_root (str): the name of the api_root.
            collection_id (str): the id of the collection
            object_id (str): the id of the requested object
            filter_args (werkzeug.datastructures.ImmutableMultiDict): query string from URL
                containing filter args
            allowed_filters (tuple): STIX properties which are allowed in the filter for this endpoint
            limit (int): Used for pagination requests. limits objects to the amount specified

        Returns:
            data from the collection that satisfies the filter

        """
        raise NotImplementedError()

    def delete_object(self, api_root, collection_id, object_id, filter_args, allowed_filters):
        """
        Fill:
            Implement the delete_object TAXII endpoint by obtaining the metadata for a selected
            object

        Args:
            api_root (str): the name of the api_root.
            collection_id (str): the id of the collection
            object_id (str): the id of the requested object
            filter_args (werkzeug.datastructures.ImmutableMultiDict): query string from URL
                containing filter args
            allowed_filters (tuple): STIX properties which are allowed in the filter for this endpoint

        Returns:
            Nothing.

        """
        raise NotImplementedError()

    def get_object_versions(self, api_root, collection_id, object_id, filter_args, allowed_filters, limit):
        """
        Fill:
            Implement the get_object_versions TAXII endpoint by obtaining the metadata for a selected
            object

        Args:
            api_root (str): the name of the api_root.
            collection_id (str): the id of the collection
            object_id (str): the id of the requested object
            filter_args (werkzeug.datastructures.ImmutableMultiDict): query string from URL
                containing filter args
            allowed_filters (tuple): STIX properties which are allowed in the filter for this endpoint
            limit (int): Used for pagination requests. limits objects to the amount specified

        Returns:
            data from the collection that satisfies the filter

        """
        raise NotImplementedError()

    def _pop_expired_sessions(self):
        """
        Fill:
            Implement thread to remove expired get requests from request queue

        Args:
            None

        Returns:
            None

        """
        raise NotImplementedError()

    def _pop_old_statuses(self):
        """
        Fill:
            Implement thread to remove old request status info

        Args:
            None

        Returns:
            None

        """
        raise NotImplementedError()
