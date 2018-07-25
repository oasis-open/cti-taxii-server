# Medallion Custom Exceptions


class MedallionError(Exception):
    "base error class for Medallion"""
    pass


class ProcessingError(MedallionError):
    """Internal processing error when processing user supplied data

    Args:
        root_exception (Exception): Exception instance of root exception
    """
    def __init__(self, root_exception, desc=None):
        self.root_exception = root_exception
        self.desc = desc


class BackendError(MedallionError):
    """Medallion data backend error

    Args:
        root_exception (Exception): Exception instance of root exception
    """
    def __init__(self, root_exception, desc=None):
        self.root_exception = root_exception
        self.desc = desc


class MongoBackendError(BackendError):
    """cannot connect or obtain access to MongoDC backend

    Args:
        root_exception (Exception): Exception instance of root exception
    """
    def __init__(self, root_exception, desc=None):
        self.root_exception = root_exception
        self.desc = desc
