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
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.ntnu.bofhd_auth import BofhdAuth
from lib.data.AccountDAO import AccountDAO

Database = Factory.get("Database")
Account = Factory.get("Account")
Constants = Factory.get("Constants")

import cgi
from lib import utils
from lib import Messages
from lib.Options import Options
from lib.templates.LoginTemplate import LoginTemplate
import config

import cereconf

logger = None

def login(**kwargs):
    global logger
    logger = Factory.get_logger("root")
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
        username = kwargs.get('username', '')
        namespace = {
            'username': utils.html_quote(username),
            'messages': utils.get_messages(),
        }
        template = LoginTemplate(searchList=[namespace])
        return template.respond()
login.exposed = True

def try_login(username=None, password=None, **kwargs):
    global logger
    try:
        if (username and not password) or (not username and password):
            raise Exception("Login failed.")
        if not username or not password:
            return False

        db = Database()
        const = Constants(db)
        method = const.auth_type_md5_crypt

        account = Account(db)
        account.find_by_name(username)
        hash = account.get_account_authentication(method)

        remote = cherrypy.request.headerMap.get("Remote-Addr", '')
        if not account.verify_password(method, password, hash):
            logger.warn("Login failed for " + username + ". Remote-addr = " + remote)
            raise Exception("Login failed.")

        auth = BofhdAuth(db)
        if not auth.can_login_to_cereweb(account.entity_id):
            logger.warn("Login failed for " + username + ". Not authorized. Remote-addr = " + remote)
            raise Exception("Login failed.")

    except Exception, e:
        Messages.queue_message(
            title="Login Failed",
            message="Incorrect username/password combination.  Please try again.",
            is_error=True,
        )
        return False

    return create_cherrypy_session(username)

def create_cherrypy_session(username):
    global logger
    db = Database()
    acc = AccountDAO(db).get_by_name(username)
    cherrypy.session['realname'] = acc.owner.name
    cherrypy.session['username'] = username
    cherrypy.session['timeout'] = get_timeout()
    cherrypy.session['client_encoding'] = negotiate_encoding()
    cherrypy.session['spine_encoding'] = 'iso-8859-1'
    cherrypy.session['options'] = Options(username)
    remote = cherrypy.request.headerMap.get("Remote-Addr", '')
    logger.info("Login successful for " + username + ". Remote-addr = " + remote)
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
    global logger
    remote = cherrypy.request.headerMap.get("Remote-Addr", '')
    username = cherrypy.session.get('username','')
    cherrypy.session.clear()
    logger.info("Logout successful for " + username +". Remote-addr = " + remote)
    utils.redirect("/login")
logout.exposed = True

def get_next(redirect=None, **kwargs):
    session_next = cherrypy.session.pop('next', None)
    next = redirect or session_next
    if next is not None:
        return utils.clean_url(next)
    return '/index'

def get_timeout():
    """Returns the time it takes in seconds for _a_ session to time out."""
    return getattr(cereconf, 'SPINE_SESSION_TIMEOUT', 900)
