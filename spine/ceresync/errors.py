from doc_exception import DocstringException, ProgrammingError

class SyncError(DocstringException):
    """General Sync error"""

class WrongModeError(SyncError, ProgrammingError):
    """Not supported in this mode of operation"""

class ServerError(SyncError):
    """Server error"""

class LoginError(ServerError):
    """Could not login"""

class NotSupportedError(SyncError):
    """Object not supported"""

class NotPosixError(NotSupportedError):
    """Not POSIX user/group"""


