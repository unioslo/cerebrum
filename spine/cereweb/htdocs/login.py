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

import urllib
import cherrypy

from lib import utils
from lib.Options import Options
from lib.templates.Login import Login
import config

import SpineClient

Spine = SpineClient.SpineClient(config=config.conf)

def login(username='', password='', redirect='/index', msg=''):
    error = None
    if username and password:
        error = "Login"
        try:
            spine = Spine.connect()
            session = spine.login(username, password)
        except Exception, e:
            error = str(e)
            error = error.replace("<", "")
            error = error.replace(">", "")
        else:
            cherrypy.session.clear()

            cherrypy.session['session'] = session
            cherrypy.session['username'] = username
            cherrypy.session['timeout'] = session.get_timeout()
            cherrypy.session['options'] = Options(session, username)
            
            #clean redirect
            if not redirect.startswith('/'):
                parts = redirect.split('/')
                # parts = [ 'http[s]?:', '', 'pointy...:8000', 'index', '...']
                if parts[0].startswith('http'):
                    redirect = "/".join(parts[3:]) 
                else:
                    redirect = '/%s' % redirect
            #redirect to the main page and start using the cereweb.publisher.
            utils.redirect(redirect)

    messages = []
    if error:
        messages.append(error)
    if msg:
        messages.append(msg)
    namespace = {
        'username': username,
        'messages': messages,
        'redirect': redirect,
    }
    template = Login(searchList=[namespace])
    return template.respond()
login.exposed = True

def logout():
    username = cherrypy.session.get('username', '')
    cherrypy.session.clear()
    utils.redirect("/login?username=%s" % username)
logout.exposed = True


# arch-tag: c1c42d44-1800-4608-b215-8a669cf10821
