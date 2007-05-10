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
from omniORB import CORBA

import cgi
from lib import utils
from lib.Options import Options
from lib.templates.Login import Login
import config

import SpineClient

Spine = SpineClient.SpineClient(config=config.conf)

def get_redirect(redirect, client):
    if not redirect:
        # If we don't have a redirect, we try to use the client argument.
        # This argument still needs to be sanitized since it is provided
        # by the user.
        redirect = client
        client = '/'
        if not redirect:
            redirect = '/'

    # Normalize redirect.
    if not redirect.startswith('/'):
        parts = redirect.split('/')
        # parts = [ 'http[s]?:', '', 'pointy...:8000', 'index', '...']
        if parts[0].startswith('http'):
            redirect = "/".join(parts[3:]) 
        else:
            redirect = '/%s' % redirect

    # Sanitize redirect.
    if redirect.startswith('/login') or redirect.startswith('/logout'):
        redirect = get_redirect(client, '/')
    return redirect

def login(**vargs):
    # Merge our session with the supplied info.  This way, we can remember
    # what client the user used last time he logged in, etc.
    vargs.update(cherrypy.session)
    username = vargs.get('username')
    password = vargs.get('password')

    # We default to the user_client
    client = vargs.get('client') or '/user_client'
    redirect = get_redirect(vargs.get('redirect'), client)

    msg = utils.get_messages()
    if vargs.get('msg'):
        msg.append(vargs.get('msg'))

    # See if we have a working spine-session already.
    try: 
        session = cherrypy.session.get('session')
        if session and session.get_timeout():
            utils.redirect(cherrypy.session.get('client', client))
    # cherrypy session exists but no spine session
    except CORBA.OBJECT_NOT_EXIST, e:
        pass

    if username and password:
        msg.append("Login")
        try:
            spine = Spine.connect()
            session = spine.login(username, password)
            if not session.is_admin():
                client = '/user_client'
        except Exception, e:
            error = cgi.escape(str(e))
            msg.append(error)
        else:
            cherrypy.session.clear()

            cherrypy.session['session'] = session
            cherrypy.session['username'] = username
            cherrypy.session['client'] = client
            cherrypy.session['timeout'] = session.get_timeout()
            cherrypy.session['encoding'] = session.get_encoding()
            cherrypy.session['options'] = Options(session, username)
            
            if redirect == '/index':
                redirect = client
            utils.redirect(redirect)

    namespace = {
        'username': username,
        'messages': msg,
        'client': client,
    }
    template = Login(searchList=[namespace])
    return template.respond()
login.exposed = True

def logout():
    session = cherrypy.session.get('session')
    if session:
        del cherrypy.session['session']
        session.logout()
    utils.redirect("/login")
logout.exposed = True


# arch-tag: c1c42d44-1800-4608-b215-8a669cf10821
