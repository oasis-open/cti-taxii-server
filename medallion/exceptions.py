# Medallion Custom Exceptions


class MedallionError(Exception):
    """base error class for Medallion

    Args:
        root_exception (Exception): Exception instance of root exception
        desc (str): specific error description
    """
    def __init__(self, root_exception, desc=None):
        self.root_exception = root_exception
        self.desc = desc


class ProcessingError(MedallionError):
    """Internal processing error when processing user supplied data

    Args:
        root_exception (Exception): Exception instance of root exception
        desc (str): specific error description
    """
    def __init__(self, root_exception, desc=None):
        super(ProcessingError, self).__init__(root_exception, desc)


class BackendError(MedallionError):
    """Medallion data backend error

    Args:
        root_exception (Exception): Exception instance of root exception
        desc (str): specific error description
    """
    def __init__(self, root_exception, desc=None):
        super(BackendError, self).__init__(root_exception, desc)


class MongoBackendError(BackendError):
    """cannot connect or obtain access to MongoDC backend

    Args:
        root_exception (Exception): Exception instance of root exception
        desc(str): specific error description
    """
    def __init__(self, root_exception, desc=None):
        super(MongoBackendError, self).__init__(root_exception, desc)
