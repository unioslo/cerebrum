# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

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
        
# arch-tag: 789a854d-e709-4545-9780-735b17baf3e2
