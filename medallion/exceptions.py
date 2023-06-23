# Medallion Custom Exceptions


class MedallionError(Exception):
    """Base error class for Medallion

    Args:
        message (str): specific error message
        root_exception (Exception): Exception instance of root exception
    """
    def __init__(self, message, status, root_exception=None):
        self.message = message
        self.status = status
        self.root_exception = root_exception

    def __str__(self):
        if self.root_exception is not None:
            return "{0.message}. Root exception: {0.root_exception}".format(self)
        else:
            return "{0.message}.".format(self)


class ProcessingError(MedallionError):
    """Internal processing error when processing user supplied data"""
    pass


class InitializationError(MedallionError):
    """Medallion Initialization Error, such as bad initial data"""
    pass


class BackendError(MedallionError):
    """Medallion data backend error"""
    pass


class MongoBackendError(BackendError):
    """Cannot connect or obtain access to MongoDB backend"""
    pass


class MemoryBackendError(BackendError):
    """Internal error in the memory backend."""
    pass