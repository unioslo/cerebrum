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
import cherrypy

from lib import utils
from lib.Options import Options
from lib.templates.Login import Login
from lib import config

import SpineClient

url = config.conf.get('SpineClient', 'url')
idl_path = config.conf.get('SpineClient', 'idl_path')
use_ssl = config.conf.getboolean('SpineClient', 'use_ssl')
ca_file = config.conf.get('SpineClient', 'ca_file')
key_file = config.conf.get('SpineClient', 'key_file')
key_password = config.conf.get('SpineClient', 'key_password')

Spine = SpineClient.SpineClient(url, use_ssl, ca_file, key_file, key_password, idl_path)

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
            
            #redirect to the main page and start using the cereweb.publisher.
            utils.redirect(redirect)

    messages = []
    if error:
        messages.append(error)
    if msg:
        messages.append(msg)

    return Login().login(username, messages)
login.exposed = True

def logout():
    username = cherrypy.session.get('username', '')
    cherrypy.session.clear()
    utils.redirect("/login?username=%s" % username)
logout.exposed = True


# arch-tag: c1c42d44-1800-4608-b215-8a669cf10821
