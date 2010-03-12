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

import time
import cherrypy

from gettext import gettext as _

from lib.Main import Main
from lib.utils import session_required_decorator
from lib import utils
from lib.templates.ActivityLogTemplate import ActivityLogTemplate
from lib.templates.Confirm import Confirm

from login import login, logout

import account
import disk
import email
import emailtarget
import emailaddress
import entity
import error
import group
import host
import ou
import person
import ajax
import motd
from search import search

@session_required_decorator
def index():
    db = utils.get_database()

    page = motd.get_page(3)
    page.title = _("Welcome to Cereweb")
    page.add_jscript("motd.js")
    return page.respond()
index.exposed = True

@session_required_decorator
def full_activitylog():
    if not utils.has_valid_session():
        utils.redirect_to_login()

    messages = cherrypy.session.get('al_messages', [])
    page = Main()
    page.title = _("Activity log")
    log = ActivityLogTemplate()
    content = log.full_activitylog(messages[::-1])
    page.content = lambda: content
    return page
full_activitylog.exposed = True

def confirm(*args, **kwargs):
    real_args = []
    for key, value in kwargs.items():
        real_args.append("%s=%s" % (key, value))

    real_url = '/' + "/".join(args) + '?' + "&".join(real_args)
    confirm = Confirm()
    confirm.yes = real_url
    confirm.no = cherrypy.request.headerMap.get('Referer', '')
    return confirm.respond()
confirm.exposed = True

__module__ = 'htdocs.index'

# arch-tag: d11bf90a-f730-4568-9234-3fc494982911
