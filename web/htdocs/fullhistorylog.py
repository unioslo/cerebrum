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

import cerebrum_path
import forgetHTML as html
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from Cerebrum.web.templates.FullHistoryLogTemplate import FullHistoryLogTemplate
from Cerebrum.web.Main import Main
from gettext import gettext as _
from Cerebrum.web.utils import url

def index(req):
    page = Main(req)
    #page.menu.setFocus("group/search")
    viewhistory = FullHistoryLogTemplate()
    #page.content = viewhistory.form
    return page

def _create_view(req, id):
    """Creates a page with a view of the entire historylog
       based on an entity"""
    server = req.session['server']
    page = Main(req)
    try:
        entity = ClientAPI.fetch_object_by_id(server, id)
        #entity.quarantines = entity.get_quarantines()
        #entity.uri = req.unparsed_uri
    except:
        page.add_message(_("Could not load entity with id %s") % id)
        return (page, None)

    view = FullHistoryLogTemplate()
    page.content = lambda: view.viewFullHistoryLog(entity)
    return (page, entity)
                                                                                                                                                                            
def view(req, id):
    server = req.session['server']
    page = Main(req)
    entity = ClientAPI.fetch_object_by_id(server,id)
    (page, entity) = _create_view(req, id)
    return page

# arch-tag: 6fc2eda4-a9d8-4b6e-bc7d-a7d31da32fd4
