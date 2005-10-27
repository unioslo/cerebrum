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
from Cereweb.utils import transaction_decorator
from Cereweb.templates.MotdViewTemplate import MotdViewTemplate
from Cereweb.templates.ActivityLogTemplate import ActivityLogTemplate

def index(req, transaction):
    page = Main(req)
    page.title = _("Welcome to Cereweb")
    motd = MotdViewTemplate()
    content = motd.viewMotds(transaction)
    page.content = lambda: content

    return page
index = transaction_decorator(index)

def full_activitylog(req):
    messages = req.session.get('al_messages', [])
    page = Main(req)
    page.title = _("Activity log")
    log = ActivityLogTemplate()
    content = log.full_activitylog(messages[::-1])
    page.content = lambda: content
    return page

# arch-tag: d11bf90a-f730-4568-9234-3fc494982911
