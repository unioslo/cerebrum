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
from Cereweb.utils import transaction_decorator, commit
from Cereweb.utils import redirect_object, object_link
from Cereweb.HistoryLog import view_history

def view(req, transaction, id):
    entity = transaction.get_entity(int(id))
    redirect_object(req, entity, seeOther=True)
view = transaction_decorator(view)

def add_external_id(req, transaction, id, external_id, id_type):
    entity = transaction.get_entity(int(id))
    id_type = transaction.get_entity_external_id_type(id_type)
    source_system = transaction.get_source_system("Manual")
    entity.set_external_id(external_id, id_type, source_system)

    #TODO: Redirect to where we actualy came from.
    msg = _("External id successfully added.")
    commit(transaction, req, entity, msg=msg)
add_external_id = transaction_decorator(add_external_id)

def remove_external_id(req, transaction, id, external_id, id_type):
    entity = transaction.get_entity(int(id))
    id_type = transaction.get_entity_external_id_type(id_type)
    source_system = transaction.get_source_system("Manual")
    entity.remove_external_id(external_id, id_type, source_system)

    #TODO: Redirect to where we actualy came from.
    msg = _("External id successfully removed.")
    commit(transaction, req, entity, msg=msg)
remove_external_id = transaction_decorator(remove_external_id)

def add_spread(req, transaction, id, spread):
    entity = transaction.get_entity(int(id))
    spread = transaction.get_spread(spread)
    entity.add_spread(spread)

    #TODO: Redirect to where we actualy came from.
    msg = _("Spread successfully added.")
    commit(transaction, req, entity, msg=msg)
add_spread = transaction_decorator(add_spread)

def remove_spread(req, transaction, id, spread):
    entity = transaction.get_entity(int(id))
    spread = transaction.get_spread(spread)
    entity.delete_spread(spread)

    #TODO: Redirect to where we actualy came from.
    msg = _("Spread successfully removed.")
    commit(transaction, req, entity, msg=msg)
remove_spread = transaction_decorator(remove_spread)

def clear_search(req, url):
    """Resets the lastsearch for cls."""
    cls = url.split('/')[-2] # seccond last part should be the class.
    lastsearch = cls + '_ls'
    if lastsearch in req.session:
        del req.session[lastsearch]

    page = html.SimpleDocument("Search reseted")
    msg = "Search for class '%s' reseted." % cls
    page.body.append(html.Division(msg))
    return page

def full_historylog(req, transaction, id):
    """Creates a page with the full historylog for an entity."""
    entity = transaction.get_entity(int(id))
    type = entity.get_type().get_name()

    page = Main(req)
    page.title = type.capitalize() + ': ' + object_link(entity)
    page.setFocus('%s/view' % type, id)
    content = view_history(entity)
    page.content = lambda: content
    return page
full_historylog = transaction_decorator(full_historylog)

# arch-tag: 4ae37776-e730-11d9-95c2-2a4ca292867e
