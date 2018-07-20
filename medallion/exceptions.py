# Medallion Custom Exceptions


class MedallionError(Exception):
    "base error class for Medallion"""
    pass


class ProcessingError(Exception):
    """Internal processing error when processing user supplied data

    Args:
        root_exception (Exception): Exception instance of root exception
    """
    def __init__(self, root_exception=None):
        self.root_exception = root_exception


class BackendError(Exception):
    """cannot connect or obtain access to Medallion backend

    Args:
        root_exception (Exception): Exception instance of root exception
    """
    def __init__(self, root_exception=None):
        self.root_exception = root_exception
