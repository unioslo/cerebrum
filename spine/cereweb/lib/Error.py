import os
import sys
import traceback
from Cereweb.templates.ErrorTemplate import ErrorTemplate

class SessionError(Exception):
    """Indicates a problem with the connection
    """

class NotFoundError(Exception):
    """A non existing resource was requested
    """

class CustomError(Exception):
    """Used as a shortcut to display an error-page with a title and message.

    The first argument should be the title of the error, and the
    seccond should be its message. Both must be included.
    """

class Redirected(Exception):
    pass # presentere en side for browsere som ikke støtter redirect?


def handle(req, error):
    title, message, tracebk = None, None, None
    
    if isinstance(error, SessionError):
        title = "Session Error."
        message = "Your session has most likely timed out."
    elif isinstance(error, Redirected):
        title = "Redirection error."
        message = "Your browser does not seem to support redirection."
    elif isinstance(error, NotFoundError):
        title = "Resource not found."
        message = "The requested resource was not found."
    elif isinstance(error, CustomError):
        title, message = error.args
        tracebk = "No traceback"
        
    if title is None:
        title = "Unknown exception!"
    if message is None:
        message = str(error)
    if tracebk is None:
        tracebk = "".join(traceback.format_exception(*sys.exc_info()))

    referer = "" #FIXME: referer is found in headers in req
    
    return ErrorTemplate().error(title, message, referer, tracebk)

# arch-tag: 52b56f54-2b55-11da-97eb-80927010959a
