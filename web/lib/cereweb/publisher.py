"""Adds the session before starting publisher"""

from mod_python import publisher
from mod_python import util
from mod_python.Session import Session
from time import strftime
from Cerebrum.web.utils import url
from Cerebrum.web.profile import get_profile
import sys

def logg(tekst):
    file = open("tmp/cleanup", "a")
    file.write("%s %s\n" % (tekst, strftime("%H:%M:%S")))
    file.close()

def handler(req):
    logg("Started handler")
    req.session = Session(req)
    req.content_type = "text/html; charset=utf8";
    logg("Got session - put it in req.session")
    check_encoding()
    check_connection(req)
    check_profile(req)
    logg("Calling normal handler")
    return publisher.handler(req)

def check_encoding():
    if sys.getdefaultencoding() <> "utf8":
        ## If this doesn't work, add this to sitecustomize.py:
        ##   # save a copy for hacking since site.py deletes setdefaultencoding 
        ##   sys.setenc = sys.setdefaultencoding
        sys.setenc("utf8")   
    logg("Enkodingen er %s" % sys.getdefaultencoding())

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
        
    
# arch-tag: 1afe2a16-d38f-434d-a9fe-081e54c8b235
