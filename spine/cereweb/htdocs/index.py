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

import forgetHTML as html
from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import transaction_decorator, url, commit_url
from Cereweb.templates.MotdTemplate import MotdTemplate
from Cereweb.templates.ActivityLogTemplate import ActivityLogTemplate

def index(req, transaction):
    page = Main(req)
    page.title = _("Welcome to Cereweb")
    motd = MotdTemplate()
    
    motd_search = transaction.get_cereweb_motd_searcher()
    motd_search.order_by_desc(motd_search, 'create_date')
    motd_search.set_search_limit(3, 0)
    content = motd.viewMotds(motd_search.search())
    page.content = lambda: content
    return page
index = transaction_decorator(index)

def all_motds(req, transaction):
    page = Main(req)
    page.title = _("Messages of the day")
    motd = MotdTemplate()
    
    motd_search = transaction.get_cereweb_motd_searcher()
    motd_search.order_by_desc(motd_search, 'create_date')
    content = motd.viewMotds(motd_search.search())
    page.content = lambda: content
    return page
all_motds = transaction_decorator(all_motds)

def create_motd(req, transaction, subject, message):
    """Create a new motd."""
    transaction.get_commands().create_cereweb_motd(subject, message)
    msg = _('Motd successfully created.')
    commit_url(transaction, req, url('index'), msg=msg)
create_motd = transaction_decorator(create_motd)

def edit_motd(req, transaction, id, subject, message):
    """Delete and recreate the motd to the server."""
    motd = transaction.get_cereweb_motd(int(id))
    motd.delete()
    transaction.get_commands().create_cereweb_motd(subject, message)
    msg = _('Motd successfully updated.')
    commit_url(transaction, req, url('index'), msg=msg)
edit_motd = transaction_decorator(edit_motd)

def delete_motd(req, transaction, id):
    """Delete the Motd from the server."""
    motd = transaction.get_cereweb_motd(int(id))
    msg = _("Motd '%s' successfully deleted.") % motd.get_subject()
    motd.delete()
    commit_url(transaction, req, url('index'), msg=msg)
delete_motd = transaction_decorator(delete_motd)

def full_activitylog(req):
    messages = req.session.get('al_messages', [])
    page = Main(req)
    page.title = _("Activity log")
    log = ActivityLogTemplate()
    content = log.full_activitylog(messages[::-1])
    page.content = lambda: content
    return page

# arch-tag: d11bf90a-f730-4568-9234-3fc494982911
