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

import md5
import time

import forgetHTML as html

from Cereweb.utils import url, redirect
from Cereweb.Session import Session
import Cereweb.SpineClient

def index(req, username="", password=""):
    # Do this ourself since we are invoked by 
    # mod_python.publisher instead of Cerebrum.web.publisher
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
            #create new session. Security & obscurity
            if not req.session:
                id = md5.new('ce%sre%swe%sb' % (time.time(), username, password))
                req.session = Session(id.hexdigest(), create=True)
            req.session['session'] = session
            req.session.save()
            
            #redirect to the main page and start using the cereweb.publisher.
            redirect(req, url("/index"))

    doc = html.SimpleDocument("Log in to Cerebrum")
    body = doc.body
    if error:
        body.append(html.Paragraph(error, style="color: red;"))
    form = html.SimpleForm(method="POST")
    body.append(form)
    form.addText("username", "Username:", username)
    form.addText("password", "Password:", password)
    form.append(html.Submit("Login"))
    return doc

# arch-tag: c1c42d44-1800-4608-b215-8a669cf10821
