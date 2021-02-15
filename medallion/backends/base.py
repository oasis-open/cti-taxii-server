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


class Backend(object, metaclass=BackendRegistry):

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
