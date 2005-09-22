# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import md5
import time

import forgetHTML as html

from Cereweb import utils
from Cereweb.Session import Session
import Cereweb.SpineClient
from Cereweb.templates.Login import Login

def index(req, username='', password='', redirect=utils.url('/index')):
    error = username
    if username:
        error = "Login"
        try:
            spine = Cereweb.SpineClient.connect()
            session = spine.login(username, password)
        except Exception, e:
            error = str(e)
            error = error.replace("<", "")
            error = error.replace(">", "")
        else:
            
            if not req.session: # Create new session. Security & obscurity
                id = md5.new('ce%sre%swe%sb' % (time.time(), username, password))
                req.session = Session(id.hexdigest(), create=True)
            else: # Reuse an old session, but clear it first.
                req.session.clear()

            req.session['session'] = session
            req.session.save()
            
            #redirect to the main page and start using the cereweb.publisher.
            utils.redirect(req, redirect)

    if error:
        messages = [error]
    else:
        messages = []

    return Login().login(username, messages)

# arch-tag: c1c42d44-1800-4608-b215-8a669cf10821
