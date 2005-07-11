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
from Cereweb.utils import queue_message, redirect_object, transaction_decorator
from Cereweb.templates.QuarantineTemplate import QuarantineTemplate

def _quarantine_vars():
    fields =[("entity_type", "Entity type"),
             ("entity_name", "Entity name"),
             ("type", "Type"),
             ("why", "Description"),
             ("start", "Start date"),
             ("end", "End date"),
             ("disable_until", "Disabled until")]
    formvalues = {}
    for name, label in fields:
        formvalues[name] = ""
    return (fields, formvalues)

def format_date(date, format="%Y-%m-%d"):
    if not date:
        return ""
    return date.strftime(format)

def edit(req, transaction, entity_id, type):
    (fields, formvalues) = _quarantine_vars()
    entity = transaction.get_entity(int(entity_id))

    page = Main(req)
    edit = QuarantineTemplate()
    edit.fields = fields
    edit.formvalues = formvalues

    for q in entity.get_quarantines():
        if q.get_type().get_name() == type:
            formvalues['type'] = type
            formvalues['why'] = q.get_description()
            formvalues['start'] = format_date(q.get_start_date())
            formvalues['end'] = format_date(q.get_end_date())
            formvalues['disable_until'] = format_date(q.get_disable_until())
    content = edit.quarantine_form(entity, "quarantine/save")
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)

def save(req, transaction, entity_id, type, why="", submit=None,
         start=None, end=None, disable_until=None):

    entity = transaction.get_entity(int(entity_id))
    for quarantine in entity.get_quarantines():
        if quarantine.get_type().get_name() == type:
            break
    else:
        queue_message(req, 
                      _("No such quarantine %s on entity") % type, 
                      error=True)
        redirect_object(req, entity, seeOther=True)

    c = transaction.get_commands()
    quarantine.set_description(why)
    quarantine.set_start_date(start and c.strptime(start, "%Y-%m-%d") or c.get_date_now())
    quarantine.set_end_date(end and c.strptime(end, "%Y-%m-%d") or c.get_date_none())
    quarantine.set_disable_until(disable_until and
            c.strptime(disable_until, "%Y-%m-%d") or c.get_date_none())

    queue_message(req, _("Updated quarantine %s" % type))
    redirect_object(req, entity, seeOther=True)
    transaction.commit()
save = transaction_decorator(save) 

def remove(req, transaction, entity_id, type):
    entity = transaction.get_entity(int(entity_id))
    q_type = transaction.get_quarantine_type(type)
    entity.remove_quarantine(q_type)
    queue_message(req, _("Removed quarantine %s") % q_type.get_name())
    redirect_object(req, entity, seeOther=True)
    transaction.commit()
remove = transaction_decorator(remove)

def add(req, transaction, entity_id, submit=None, type=None, why="",
        start=None, end=None, disable_until=None):

    err_msg = ""
    entity = transaction.get_entity(int(entity_id))
    (fields, formvalues) = _quarantine_vars()

    if type:
        q_type = transaction.get_quarantine_type(type)

        search = transaction.get_entity_quarantine_searcher()
        search.set_entity(entity)
        search.set_type(q_type)
        result = search.search()
        if result:
            quarantine, = result
        else:
            quarantine = None
    else:
        quarantine = None

    if (submit == 'Save'):
        try:
            """ Set up a new quarantine with registered values.
                Return to the entity's form if OK.
            """
            q_type = transaction.get_quarantine_type(type)
            c = transaction.get_commands()
            date_none = c.get_date_none()

            date_start = start and c.strptime(start, "%Y-%m-%d") or c.get_date_now()
            date_end = end and c.strptime(end, "%Y-%m-%d") or date_none
            date_dis = disable_until and c.strptime(disable_until, "%Y-%m-%d") or date_none
            entity.add_quarantine(q_type, why, date_start, date_end, date_dis)
            queue_message(req, _("Added quarantine %s" % type))
            redirect_object(req, entity, seeOther=True)
            transaction.commit()
            return
        
        except "Jeg vil se feilmeldingen":
            """ Save the values given by the user, and set up
                en error message to be shown.
            """
            for name, desc in fields:
                try:
                    formvalues[name] = eval(name) #<- eh, eval? wtf
                except:
                    pass
            err_msg = _("Add new quarantine failed!")

    page = Main(req)
    add = QuarantineTemplate()
    add.fields = fields
    add.formvalues = formvalues

    has_types = [q.get_type().get_name() for q in entity.get_quarantines()]
    # only present types not already set
    types = [(qt.get_name(), "%s (%s)" % (qt.get_description(), qt.get_name())) 
             for qt in transaction.get_quarantine_type_searcher().search()
             if qt.get_name() not in has_types]

    # FIXME: Should only present types appropriate for the
    # entity_type. (how could we know that?) 
    content = add.quarantine_form(entity, "quarantine/add", types)
    page.content = lambda: content
    if (err_msg):
        page.add_message(err_msg, True)

    return page
add = transaction_decorator(add)

# arch-tag: fd438bb2-ecb9-480b-b833-e42484da0a39
