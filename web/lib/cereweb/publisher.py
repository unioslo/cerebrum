"""Adds the session before starting publisher"""

from mod_python import publisher
from mod_python import util
from mod_python.Session import Session
from time import strftime

def logg(tekst):
    file = open("tmp/cleanup", "a")
    file.write("%s %s\n" % (tekst, strftime("%H:%M:%S")))
    file.close()

def handler(req):
    logg("Started handler")
    req.session = Session(req)
    logg("Got session - put it in req.session")
    if not req.session.has_key("server"):
        logg("Redirecting")
        util.redirect(req,
            "http://garbageman.itea.ntnu.no/~stain/login/")
        # This should never happen, as redirect raises
        # apache.SERVER_RETURN
        return apache.HTTP_INTERNAL_SERVER_ERROR
    
    logg("Calling normal handler")
    return publisher.handler(req)
