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

import cherrypy

from lib import utils
from gettext import gettext as _
from lib.Main import Main
from lib.utils import commit, commit_url, queue_message, object_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.utils import get_messages, rollback_url
from lib.templates.ActivationTemplate import ActivationTemplate
import config
import SpineIDL
import SpineClient

def _login():
    Spine = SpineClient.SpineClient(config=config.conf)
    spine = Spine.connect()
    service_user = config.conf.get('SpineClient','activation_user')
    server_pw = config.conf.get('SpineClient','activation_password')
    return spine.login(service_user,server_pw)

def _get_session():
    cps = cherrypy.session
    ss = cps.get('session') 
    if not ss:
        ss = cps['session'] = _login()
    ss.set_encoding("utf-8")
    return ss

def index(**vargs):
    session = _get_session()
    tr = session.new_transaction()
    print 'post-args: %s' % vargs
    print 'session-args: %s' % cherrypy.session

    try:
        page = _get_next_page(tr, **vargs)
        cherrypy.session.update(vargs)
    except Exception, e:
        v = dict(cherrypy.session)
        page = _retry_page(tr, **v)
        queue_message(str(e))

    tr.rollback()
    return page.respond()
index.exposed = True


path = ['language', 'fodselsnr', 'studentnr', 'pinkode', 'eula', 'initpassword', 'welcome']
def _get_next_page(tr, **vargs):
    pp = vargs.get('page', path[-1])
    next = (path.index(pp) + 1 % len(path))
    next = path[next]

    return _get_page(tr, next, **vargs)

def _get_page(tr, name, **vargs):
    lang = vargs.get('lang','')
    try:
        page = ActivationTemplate()
        page.vargs = vargs
        page.content = getattr(page, name)
    except SpineIDL.Errors.AccessDeniedError, e:
        page = object
        page.respond = lambda x: [str(e)]
    return page

def _retry_page(tr, **vargs):
    return _get_page(tr, vargs.get('page', path[0]), **vargs)



