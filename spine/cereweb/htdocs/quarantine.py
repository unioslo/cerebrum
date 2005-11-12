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

import mx.DateTime
from gettext import gettext as _
from lib.Main import Main
from lib.utils import redirect_object, strftime, commit
from lib.utils import object_link, transaction_decorator
from lib.templates.QuarantineTemplate import QuarantineTemplate

def edit(transaction, entity, type):
    entity = transaction.get_entity(int(entity))
    q_type = transaction.get_quarantine_type(type)

    quarantine = entity.get_quarantine(q_type)
    formvalues = {}
    formvalues['type'] = type
    formvalues['why'] = quarantine.get_description()
    formvalues['start'] = strftime(quarantine.get_start_date())
    formvalues['end'] = strftime(quarantine.get_end_date())
    formvalues['disable_until'] = strftime(quarantine.get_disable_until())
    
    page = Main()
    page.title = _("Edit quarantine %s on ") % type
    page.title += object_link(entity)
    edit = QuarantineTemplate()
    edit.formvalues = formvalues
    content = edit.quarantine_form(entity, "quarantine/save")
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, entity, type, why="",
         start="", end="", disable_until="", submit=None):
    entity = transaction.get_entity(int(entity))
    
    if submit == "Cancel":
        redirect_object(entity)
        return

    q_type = transaction.get_quarantine_type(type)
    quarantine = entity.get_quarantine(q_type)
    c = transaction.get_commands()
    
    def strptime(date, default=''):
        return date and c.strptime(date, "%Y-%m-%d") or default
    
    quarantine.set_description(why)
    quarantine.set_start_date(strptime(start, c.get_date_now()))
    quarantine.set_end_date(strptime(end, c.get_date_none()))
    quarantine.set_disable_until(strptime(disable_until, c.get_date_none()))

    msg = _("Updated quarantine '%s' successfully.") % type
    commit(transaction, entity, msg=msg)
save = transaction_decorator(save) 
save.exposed = True

def add(transaction, entity):
    # FIXME: Should only present types appropriate for the
    # entity_type. (how could we know that?) 
    entity = transaction.get_entity(int(entity))
    has_types = [q.get_type().get_name() for q in entity.get_quarantines()]
    types = [(qt.get_name(), "%s (%s)" % (qt.get_description(), qt.get_name())) 
             for qt in transaction.get_quarantine_type_searcher().search()
             if qt.get_name() not in has_types]

    formvalues = {}
    formvalues['start'] = mx.DateTime.now().strftime("%Y-%m-%d")
    
    page = Main()
    page.title = _("Add a new quarantine on ")
    page.title += object_link(entity)
    add = QuarantineTemplate()
    add.formvalues = formvalues
    content = add.quarantine_form(entity, "quarantine/make", types)
    page.content = lambda: content
    return page
add = transaction_decorator(add)
add.exposed = True

def make(transaction, entity, type, why="",
         start="", end="", disable_until="", submit=None):
    entity = transaction.get_entity(int(entity))
    
    if submit == "Cancel":
        redirect_object(entity)
        return

    q_type = transaction.get_quarantine_type(type)
    c = transaction.get_commands()
    date_none = c.get_date_none()

    date_start = start and c.strptime(start, "%Y-%m-%d") or c.get_date_now()
    date_end = end and c.strptime(end, "%Y-%m-%d") or date_none
    date_dis = disable_until and c.strptime(disable_until, "%Y-%m-%d") or date_none
    
    entity.add_quarantine(q_type, why, date_start, date_end, date_dis)
    
    msg = _("Added quarantine '%s' successfully") % type
    commit(transaction, entity, msg=msg)
make = transaction_decorator(make)
make.exposed = True

def remove(transaction, entity, type):
    entity = transaction.get_entity(int(entity))
    q_type = transaction.get_quarantine_type(type)
    
    entity.remove_quarantine(q_type)
    
    msg = _("Removed quarantine '%s' successfully.") % type
    commit(transaction, entity, msg=msg)
remove = transaction_decorator(remove)
remove.exposed = True

# arch-tag: fd438bb2-ecb9-480b-b833-e42484da0a39
