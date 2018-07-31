# Medallion Custom Exceptions


class MedallionError(Exception):
    """base error class for Medallion

    Args:
        message (str): specific error message
        root_exception (Exception): Exception instance of root exception
    """
    def __init__(self, message, root_exception):
        self.message = message
        self.root_exception = root_exception

    def __str__(self):
        return "{0.message}. Root exception: {0.root_exception}".format(self)


class ProcessingError(MedallionError):
    """Internal processing error when processing user supplied data"""
    pass


class BackendError(MedallionError):
    """Medallion data backend error"""
    pass


class MongoBackendError(BackendError):
    """cannot connect or obtain access to MongoDC backend"""
