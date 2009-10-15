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

from gettext import gettext as _
from lib.utils import redirect_entity
from lib.utils import entity_link, queue_message
from lib.utils import web_to_spine, spine_to_web
from lib.utils import get_database, session_required_decorator
from lib.HistoryLog import view_history, view_history_all
from lib.templates.EntityViewTemplate import EntityViewTemplate
from lib.data.EntityFactory import EntityFactory
from lib.data.HistoryDAO import HistoryDAO
from lib.data.DTO import DTO

def view(id):
    redirect_entity(id)
view.exposed = True

@session_required_decorator
def add_external_id(id, external_id, id_type):
    if not external_id:
        queue_message('External identifier is empty.  Identifier not set.', error=True)
        redirect_entity(id)
    if not external_id.isdigit():
        queue_message('External identifier should contain only digits.', error=True)
        redirect_entity(id)

    db = get_database()
    dao = EntityFactory(db).get_dao_by_entity_id(id)
    dao.add_external_id(id, external_id, id_type)
    db.commit()

    msg = _("External id successfully added.")
    queue_message(msg, title=_("Operation succeeded"))
    redirect_entity(id)
add_external_id.exposed = True

@session_required_decorator
def remove_external_id(id, id_type):
    db = get_database()
    dao = EntityFactory(db).get_dao_by_entity_id(id)
    dao.remove_external_id(id, id_type)
    db.commit()

    msg = _("External id successfully removed.")
    queue_message(msg, title=_("Operation succeeded"))
    redirect_entity(id)
remove_external_id.exposed = True

@session_required_decorator
def add_spread(id, spread):
    db = get_database()
    dao = EntityFactory(db).get_dao_by_entity_id(id)
    dao.add_spread(id, spread)
    db.commit()

    msg = _("Spread successfully added.")
    queue_message(msg, title=_("Operation succeeded"))
    redirect_entity(id)
add_spread.exposed = True

@session_required_decorator
def remove_spread(id, spread):
    db = get_database()
    dao = EntityFactory(db).get_dao_by_entity_id(id)
    dao.remove_spread(id, spread)
    db.commit()

    msg = _("Spread successfully removed.")
    queue_message(msg, title=_("Operation succeeded"))
    redirect_entity(id)
remove_spread.exposed = True

@session_required_decorator
def add_quarantine(id, quarantine, why="", start="", end="", disable_until=""):
    db = get_database()
    dao = EntityFactory(db).get_dao_by_entity_id(id)

    why = why or None
    start = start or None
    end = end or None
    disable_until = disable_until or None
    
    dao.add_quarantine(id, quarantine, why, start, end, disable_until)
    db.commit()

    msg = _("Quarantine successfully added.")
    queue_message(msg, title=_("Operation succeeded"))
    redirect_entity(id)
add_quarantine.exposed = True

@session_required_decorator
def disable_quarantine(id, type, disable_until=""):
    db = get_database()
    dao = EntityFactory(db).get_dao_by_entity_id(id)

    disable_until = disable_until or None
    
    dao.disable_quarantine(id, type, disable_until)
    db.commit()

    msg = _("Quarantine successfully updated.")
    queue_message(msg, title=_("Operation succeeded"))
    redirect_entity(id)
disable_quarantine.exposed = True

@session_required_decorator
def remove_quarantine(id, type):
    db = get_database()
    dao = EntityFactory(db).get_dao_by_entity_id(id)
    dao.remove_quarantine(id, type)
    db.commit()

    msg = _("Quarantine successfully removed.")
    queue_message(msg, title=_("Operation succeeded"))
    redirect_entity(id)
remove_quarantine.exposed = True

@session_required_decorator
def full_historylog(id):
    """Creates a page with the full historylog for an entity."""
    db = get_database()
    entity = EntityFactory(db).get_entity(id)
    entity.history = HistoryDAO(db).get_entity_history(id)

    page = EntityViewTemplate()
    page.links = ()
    page.title = entity.type_name.capitalize() + ': ' + entity_link(entity)
    page.set_focus('%s/view' % entity.type_name)
    page.content = lambda: page.viewHistoryLog(entity)
    return page
full_historylog.exposed = True

@session_required_decorator
def global_historylog(n=50, offset=0):
    """Creates a page from the global historylog."""
    db = get_database()
    dto = DTO()
    dto.id = None
    dto.history = HistoryDAO(db).get_history(n, offset)

    page = EntityViewTemplate()
    page.links = ()
    page.title = "History"
    page.content = lambda: page.viewHistoryLog(dto)
    return page
global_historylog.exposed = True
