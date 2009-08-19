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
from lib import Messages
from lib.Options import Options
from lib.templates.Login import Login
import config

import SpineClient

class Client(object):
    def __init__(self):
        self.__connect()

    def __call__(self):
        if self.spine:
            return self.spine
        else:
            return self.__connect()

    def __connect(self):
        try:
            self.spine = SpineClient.SpineClient(config=config.conf)
        except CORBA.TRANSIENT, e:
            self.spine = None
        return self.spine

    def disconnect(self):
        self.spine = None
Client = Client()

def login(**kwargs):
    if 'msg' in kwargs:
        Messages.queue_message(
            title='No Title',
            message=kwargs.get('msg'),
            is_error=True,
        )

    logged_in = utils.has_valid_session() or try_login(**kwargs)

    if logged_in:
        next = get_next(**kwargs)
        utils.redirect(next)
    else:
        namespace = {
            'username': kwargs.get('username', ''),
            'messages': utils.get_messages(),
        }
        template = Login(searchList=[namespace])
        return template.respond()
login.exposed = True

def try_login(username=None, password=None, **kwargs):
    if not username or not password:
        return False

    if not is_allowed_login(username):
        Messages.queue_message(
            title="Login failed",
            message="You're not allowed to login to the test/development server.",
            is_error=True)
        return False

    Spine = Client()
    
    try:
        if not Spine:
            raise CORBA.TRANSIENT('Could not connect.')

        spine = Spine.connect()
    except CORBA.TRANSIENT, e:
        Messages.queue_message(
            title="Connection Failed",
            message="Could not connect to the Spine server.  Please contact Orakel.",
            is_error=True,
        )
        return False

    try:
        session = spine.login(username, password)
    except Exception, e:
        Messages.queue_message(
            title="Login Failed",
            message="Incorrect username/password combination.  Please try again.",
            is_error=True,
        )
        return False

    return create_cherrypy_session(session, username)

def is_allowed_login(username):
    return username == "bootstrap_account"

def create_cherrypy_session(session, username):
    cherrypy.session['username'] = username
    cherrypy.session['session'] = session
    cherrypy.session['timeout'] = session.get_timeout()
    cherrypy.session['spine_encoding'] = session.get_encoding()
    cherrypy.session['options'] = Options(session, username)
    cherrypy.session['client_encoding'] = negotiate_encoding()
    return True

def negotiate_encoding():
    prefered_charset = default_charset = 'utf-8'
    allowed_charsets = cherrypy.request.headerMap.get('Accept-Charset', '')
    
    if not allowed_charsets:
        return default_charset

    charsets = [c.strip().lower() for c in allowed_charsets.split(',')]
    if prefered_charset in charsets:
        return prefered_charset
    return charsets[0]

def logout():
    session = cherrypy.session.get('session')
    if session:
        del cherrypy.session['session']
        session.logout()
    utils.redirect("/login")
logout.exposed = True


def get_next(redirect=None, **kwargs):
    session_next = cherrypy.session.pop('next', None)
    next = redirect or session_next
    if next is not None:
        return utils.clean_url(next)
    return '/index'
    
# arch-tag: c1c42d44-1800-4608-b215-8a669cf10821
