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
from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import url, transaction_decorator
from Cereweb.templates.FullHistoryLogTemplate import FullHistoryLogTemplate

def index(req):
    page = Main(req)
    #page.menu.setFocus("group/search")
    viewhistory = FullHistoryLogTemplate()
    #page.content = viewhistory.form
    return page

@transaction_decorator
def view(req, transaction, id):
    """Creates a page with a view of the entire historylog
       based on an entity"""
    page = Main(req)
    try:
        entity = transaction.get_entity(int(id))
        #entity.quarantines = entity.get_quarantines()
        #entity.uri = req.unparsed_uri
    except:
        page.add_message(_("Could not load entity with id %s") % id)
        return page

    view = FullHistoryLogTemplate()
    content = view.viewFullHistoryLog(entity)
    page.content = lambda: content
    return page

# arch-tag: b5256b7a-e7d9-48f8-9623-92875f2a4f46
