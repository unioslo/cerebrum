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

import forgetHTML as html
from mod_python.Session import Session
from Cereweb import ServerConnection
from Cereweb.utils import url, redirect

def index(req, user="", password=""):
    # Do this ourself since we are invoked by 
    # mod_python.publisher instead of Cerebrum.web.publisher
    error = user
    if user:
        error = "Login"
        try:
            spine = ServerConnection.connect()
            server = spine.login(user, password).new_transaction()
            server = ServerConnection.get_orb().object_to_string(server)
        except Exception, e:
            error = str(e)
            error = error.replace("<", "")
            error = error.replace(">", "")
        else:
            #remove old session
            req.session = Session(req)
            req.session.invalidate()

            #create new session
            req.session = Session(req)
            req.session['server'] = server
            req.session.save()
            
            #redirect to the main page and start using the cereweb.publisher.
            redirect(req, url("/"))
    
    doc = html.SimpleDocument("Log in to Cerebrum")
    body = doc.body
    body.append(html.Paragraph("Cerebrum is powered by 230V"))
    if error:
        body.append(html.Paragraph(error, style="color: red;"))
    form = html.SimpleForm(method="POST")
    body.append(form)
    form.addText("user", "Username:", user)
    form.addText("password", "Password:", password)
    form.append(html.Submit("Login"))
    return doc

# arch-tag: 4dc1ddde-c201-4b09-8a81-b007662cabca
