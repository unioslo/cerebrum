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

import sys
from time import strftime

from mod_python import apache
from mod_python import publisher
from mod_python.Session import Session

from utils import url, no_cache, redirect
from profile import get_profile


def logg(tekst):
    """Write text to a logfile for debuging."""
    file = open("tmp/cleanup", "a")
    file.write("%s %s\n" % (tekst, strftime("%H:%M:%S")))
    file.close()

def handler(req):
    """Adds the session before starting publisher.
    
    Redirects back to login if the server obj is missing.
    Asks the browser not to cache any pages.
    Makes sure the session has a profile.
    Do some encoding magic, not sure how and why :)
    """
    logg("Started handler")
    no_cache(req)
    req.session = Session(req)
    req.content_type = "text/html; charset=utf8"; #fix charset
    logg("Got session %s id: %s" % (req.session.is_new(), str(req.session.id())))
    check_connection(req)
    #check_encoding()
    #check_profile(req)
    logg("Calling normal handler")
    return publisher.handler(req)

def check_connection(req):
    if not req.session.has_key("server"):
        logg("Redirecting since server is missing: %s" % str(req.session))
        redirect(req, url("login/"))

def check_encoding():
    if sys.getdefaultencoding() != "utf8":
        ## If this doesn't work, add this to sitecustomize.py:
        ##   # save a copy for hacking since site.py deletes setdefaultencoding
        ##   sys.setenc = sys.setdefaultencoding
        sys.setenc("utf8")
    logg("Enkodingen er %s" % sys.getdefaultencoding())

def check_profile(req):
    if not req.session.has_key("profile"):
        req.session['profile'] = get_profile(req)

# arch-tag: 1afe2a16-d38f-434d-a9fe-081e54c8b235
