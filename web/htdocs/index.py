# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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
html.Element.__call__ = html.Element.__str__

from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web import ActivityLog
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.SideMenu import SideMenu

def index(req, tag="p"):
    req.content_type="text/html"
    body = MainTemplate()
    body.title = "Cereweb"
    table = html.SimpleTable(header="row")
    table.add("Her", "kommer en", "velkomsthilsen")
    table.add("Dette", "er")
    table.add("Ganske", "bra", "altså")
    body.content = table

    #log = ActivityLog()
    #body.activitylog = log

    worklist = WorkList()
    body.worklist = worklist


    sidemenu = SideMenu()
    body.menu = sidemenu


    return body

# arch-tag: d11bf90a-f730-4568-9234-3fc494982911
