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
from Cereweb.utils import queue_message, redirect_object
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

def edit(req, entity_id, type, submit=None, why=None, start=None, end=None, disable_until=None):
    server = req.session['server']
    err_msg = ""
    (fields, formvalues) = _quarantine_vars()
    ent = ClientAPI.fetch_object_by_id(server, entity_id)
    quarantines = ent.get_quarantines()
    for row in quarantines:
        if row.type.name == type:
            formvalues['type'] = type
            formvalues['why'] = row.why
            if row.start:
                formvalues['start'] = row.start.strftime("%Y-%m-%d")
            if row.end:
                formvalues['end'] = row.end.strftime("%Y-%m-%d")
            if row.disable_until:
                formvalues['disable_until'] = row.disable_until.strftime("%Y-%m-%d")
            formvalues['entity_type'] = ent.type
            formvalues['entity_name'] = ent.name

    if (submit == 'Save'):
        did_add = False
        if (formvalues['why'] != why or
            formvalues['start'] != start or
            formvalues['end'] != end):
            try:
                ent.remove_quarantine(type=type)
                ent.add_quarantine(type, why, start, end)
                did_add = True
            except:
                err_msg += "Unable to edit quarantine!"
        if (did_add or formvalues['disable_until'] != disable_until):
            try:
                ent.disable_quarantine(type=type, until=disable_until)
                did_add = True
            except:
                did_add = False
                err_msg += "Unable to disable quarantine!"
        if (did_add):
            redirect_object(req, ent, seeOther=True)
        else:
            for name, desc in fields:
                try:
                    formvalues[name] = eval(name)
                except:
                    pass
    page = Main(req)
    edit = QuarantineTemplate()
    edit.fields = fields
    edit.formvalues = formvalues
    page.content = lambda: edit.quarantine_form(ent, "quarantine/edit")
    if (err_msg):
        page.add_message(err_msg, True)
    return page

def remove(req, entity_id, type):
    err_msg = ""
    server = req.session['server']
    try:
        ent = ClientAPI.fetch_object_by_id(server, entity_id)
        ent.remove_quarantine(type=type)
    except:
        err_msg = _("Unable to remove quarantine!")
    queue_message(req, _("Removed quarantine"))
    return redirect_object(req, ent, seeOther=True)

def add(req, entity_id, submit=None,entity_type=None,\
        type=None,why=None,start=None,end=None,disable_until=None):

    server = req.session['server']
    err_msg = ""
    ent = ClientAPI.fetch_object_by_id(server,entity_id)
    (fields, formvalues) = _quarantine_vars()

    if (submit == 'Save'):
        try:
            """ Set up a new quarantine with registered values.
                Return to the entity's form if OK.
            """
            ent.add_quarantine(type,why=why,start=start,end=end)
            if (disable_until):
                try:
                    ent.disable_quarantine(type=type, until=disable_until)
                except:
                    err_msg = _("Unable to disable the quarantine.")
            if (not err_msg):
                queue_message(req, _("Added quarantine %s" % type))
                return redirect_object(req, ent, seeOther=True)
        except "Jeg vil se feilmeldingen":
            """ Save the values given by the user, and set up
                en error message to be shown.
            """
            for name, desc in fields:
                try:
                    formvalues[name] = eval(name)
                except:
                    pass
            err_msg = _("Add new quarantine failed!")

    formvalues['entity_type'] = ent.type
    formvalues['entity_name'] = ent.name
    page = Main(req)
    add = QuarantineTemplate()
    add.fields = fields
    add.formvalues = formvalues
    all_types = ClientAPI.QuarantineType.get_all(server)
    has_types = [quarantine.type for quarantine in ent.get_quarantines()]
    # only present types not already set
    # FIXME: Should only present types appropriate for the
    # entity_type. (how could we know that?) 
    types = [type for type in all_types if type not in has_types]
    page.content = lambda: add.quarantine_form(ent, "quarantine/add", types)
    if (err_msg):
        page.add_message(err_msg, True)

    return page

# arch-tag: fd438bb2-ecb9-480b-b833-e42484da0a39
