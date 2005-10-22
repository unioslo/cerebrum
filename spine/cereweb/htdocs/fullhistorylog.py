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

from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.HistoryLog import view_history
from Cereweb.utils import transaction_decorator, object_link

def view(req, transaction, id):
    """Creates a page with the full historylog for an entity."""
    entity = transaction.get_entity(int(id))
    type = entity.get_type().get_name()
    
    page = Main(req)
    page.title = type.capitalize() + ': ' + object_link(entity)
    page.setFocus('%s/view' % type, id)
    content = view_history(entity)
    page.content = lambda: content
    return page
view = transaction_decorator(view)

# arch-tag: b5256b7a-e7d9-48f8-9623-92875f2a4f46
