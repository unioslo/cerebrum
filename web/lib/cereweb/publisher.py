"""Adds the session before starting publisher"""

from mod_python import publisher
from mod_python import util
from mod_python.Session import Session
from time import strftime
from Cerebrum.web.utils import url
from Cerebrum.web.profile import get_profile

def logg(tekst):
    file = open("tmp/cleanup", "a")
    file.write("%s %s\n" % (tekst, strftime("%H:%M:%S")))
    file.close()

def handler(req):
    logg("Started handler")
    req.session = Session(req)
    req.content_type = "text/html; charset=utf8";
    logg("Got session - put it in req.session")
    check_connection(req)
    check_profile(req)
    logg("Calling normal handler")
    return publisher.handler(req)

def check_connection(req):
    if req.session.has_key("server"):
        # everything ok
        return
    # server not found    
    logg("Redirecting")
    util.redirect(req, url("login/"))
    # This should never happen, as redirect raises
    # apache.SERVER_RETURN
    raise "RealityError"

def check_profile(req):
    if req.session.has_key("profile"):
        # everything ok
        return
    req.session['profile'] = get_profile(req)
        
    
