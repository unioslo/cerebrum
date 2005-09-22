import os

class SessionError(Exception):
    """Indicates a problem with the connection
    """

class NotFoundError(Exception):
    """A non existing resource was requested
    """

class Redirected(Exception):
    pass # presentere en side for browsere som ikke støtter redirect?


def handle(req, error):
    if isinstance(error, SessionError):
        return '<html><body><pre>%s</pre>SessionError</body></html>' % os.environ
    elif isinstance(error, Redirected):
        return '<html><body>Redirected</body></html>'

    # fange python-greier som ImportError.
    return '<html><body><pre>%s</pre></html>' % error

# arch-tag: 52b56f54-2b55-11da-97eb-80927010959a
