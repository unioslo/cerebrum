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

import forgetHTML as html
from gettext import gettext as _

from lib.Main import Main
from lib.utils import transaction_decorator, commit_url
from lib.templates.MotdTemplate import MotdTemplate
from lib.templates.ActivityLogTemplate import ActivityLogTemplate

from login import login, logout

import account
import disk
import email
import entity
import error
import group
import host
import note
import options
import ou
import person
import quarantine
import worklist
import permissions
import user_client

def index(transaction):
    page = Main()
    page.title = _("Welcome to Cereweb")
    motd = MotdTemplate()
    
    motd_search = transaction.get_cereweb_motd_searcher()
    motd_search.order_by_desc(motd_search, 'create_date')
    motd_search.set_search_limit(3, 0)
    content = motd.viewMotds(motd_search.search())
    page.content = lambda: content
    return page
index = transaction_decorator(index)
index.exposed = True

def all_motds(transaction):
    page = Main()
    page.title = _("Messages of the day")
    motd = MotdTemplate()
    
    motd_search = transaction.get_cereweb_motd_searcher()
    motd_search.order_by_desc(motd_search, 'create_date')
    content = motd.viewMotds(motd_search.search())
    page.content = lambda: content
    return page
all_motds = transaction_decorator(all_motds)
all_motds.exposed = True

def create_motd(transaction, subject, message):
    """Create a new motd."""
    transaction.get_commands().create_cereweb_motd(subject, message)
    msg = _('Motd successfully created.')
    commit_url(transaction, 'index', msg=msg)
create_motd = transaction_decorator(create_motd)
create_motd.exposed = True

def edit_motd(transaction, id, subject, message):
    """Delete and recreate the motd to the server."""
    motd = transaction.get_cereweb_motd(int(id))
    motd.delete()
    transaction.get_commands().create_cereweb_motd(subject, message)
    msg = _('Motd successfully updated.')
    commit_url(transaction, 'index', msg=msg)
edit_motd = transaction_decorator(edit_motd)
edit_motd.exposed = True

def delete_motd(transaction, id):
    """Delete the Motd from the server."""
    motd = transaction.get_cereweb_motd(int(id))
    msg = _("Motd '%s' successfully deleted.") % motd.get_subject()
    motd.delete()
    commit_url(transaction, 'index', msg=msg)
delete_motd = transaction_decorator(delete_motd)
delete_motd.exposed = True

def full_activitylog():
    messages = cherrypy.session.get('al_messages', [])
    page = Main()
    page.title = _("Activity log")
    log = ActivityLogTemplate()
    content = log.full_activitylog(messages[::-1])
    page.content = lambda: content
    return page
full_activitylog.exposed = True

def session_time_left(hash=None):
    """Return time left before the session times out.
    
    'hash' allows the client to avoid a bug where the browser chaches
    the request.
    """
    timeout = cherrypy.session.get('timeout')
    timestamp = cherrypy.session.get('timestamp', None)
    
    if timestamp is None:
        return '0'
    
    time_left = int(timeout - (time.time() - timestamp))
    time_left = time_left > 0 and time_left or 0
    return str(time_left)
session_time_left.exposed = True

def session_keep_alive(hash=None):
    """Attempt to keep the session alive.
    
    Returns 'true' if the session was kept alive, 'false' if the 
    session has already timed out.
    """
    session = cherrypy.session['session']
    try:
        session.get_timeout()
        cherrypy.session['timestamp'] = time.time()
    except:
        return 'false'
    else:
        return 'true'
session_keep_alive.exposed = True

__module__ = 'htdocs.index'

# arch-tag: d11bf90a-f730-4568-9234-3fc494982911
