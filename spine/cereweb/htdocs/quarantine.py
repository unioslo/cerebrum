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
from lib.utils import redirect_object, strftime, commit, html_quote
from lib.utils import object_link, transaction_decorator, queue_message
from lib.utils import legal_date, redirect
from lib.templates.QuarantineTemplate import QuarantineTemplate

def edit(transaction, entity, type, why="", start="", end="", disable_until=""):
    entity = transaction.get_entity(int(entity))
    q_type = transaction.get_quarantine_type(type)

    quarantine = entity.get_quarantine(q_type)
    formvalues = {}
    formvalues['type'] = type
    formvalues['why'] = why or quarantine.get_description()
    formvalues['start'] = start or strftime(quarantine.get_start_date())
    formvalues['end'] = end or strftime(quarantine.get_end_date())
    formvalues['disable_until'] = disable_until or strftime(quarantine.get_disable_until())
    
    page = Main()
    page.title = _('Edit quarantine for ')
    page.title += object_link(entity)
    edit = QuarantineTemplate()
    edit.formvalues = formvalues
    content = edit.quarantine_form(entity, "/quarantine/save")
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, entity, type, why="",
         start="", end="", disable_until="", submit=None):
    id = entity
    entity = transaction.get_entity(int(entity))
    
    if submit == "Cancel":
        redirect_object(entity)
        return

    err = False
    if not start:
        queue_message('Start date is empty.', error=True)
        err = True
    if not legal_date(start):
        queue_message('Start date is unlegal.', error=True)
        err = True
    if end:
        if not legal_date(end):
            queue_message('End date is unlegal.', error=True)
            err = True
    if disable_until:
        if not legal_date(disable_until):
            queue_message('Disable until date is unlegal.', error=True)
            err = True
    if err:
        redirect("/quarantine/edit?entity=%s&type=%s&why=%s&start=%s&end=%s&disable_until=%s" % (id, type, why, start, end, disable_until))
    q_type = transaction.get_quarantine_type(type)
    quarantine = entity.get_quarantine(q_type)
    c = transaction.get_commands()
    
    def strptime(date, default=''):
        return date and c.strptime(date, "%Y-%m-%d") or default

    quoted = ''
    if why:
        quoted = html_quote(why)
    quarantine.set_description(quoted)
    quarantine.set_start_date(strptime(start, c.get_date_now()))
    quarantine.set_end_date(strptime(end, None))
    quarantine.set_disable_until(strptime(disable_until, None))

    msg = _("Updated quarantine '%s' successfully.") % type
    commit(transaction, entity, msg=msg)
save = transaction_decorator(save) 
save.exposed = True

def add(transaction, entity, type="", why="", start="", end="", disable_until=""):
    # FIXME: Should only present types appropriate for the
    # entity_type. (how could we know that?) 
    entity = transaction.get_entity(int(entity))
    has_types = [q.get_type().get_name() for q in entity.get_quarantines()]
    types = [(qt.get_name(), "%s (%s)" % (qt.get_description(), qt.get_name())) 
             for qt in transaction.get_quarantine_type_searcher().search()
             if qt.get_name() not in has_types]

    formvalues = {}
    formvalues['start'] = start or mx.DateTime.now().strftime("%Y-%m-%d")
    if type:
        formvalues['type'] = type
    if why:
        formvalues['why'] = why
    if end:
        formvalues['end'] = end
    if disable_until:
        formvalues['disable_until'] = disable_until
        
    page = Main()
    page.title = _("Add quarantine on ")
    page.title += object_link(entity)
    add = QuarantineTemplate()
    add.formvalues = formvalues
    content = add.quarantine_form(entity, "make", types)
    page.content = lambda: content
    page.links = ()
    return page
add = transaction_decorator(add)
add.exposed = True

def make(transaction, entity, type, why="",
         start="", end="", disable_until="", submit=None):
    id = entity
    entity = transaction.get_entity(int(entity))
    if submit == "Cancel":
        redirect_object(entity)
        return

    err = False
    if not start:
        queue_message('Start date must be set.', error=True)
        err = True
    if not legal_date(start):
        queue_message('Start date is not legal.', error=True)
        err = True
    if end:
        if not legal_date(end):
            queue_message('End date is not legal.',error=True)
            err = True
    if disable_until:
        if not legal_date(disable_until):
            queue_message('Postpone until date is not legal.', error=True)
            err = True
    if err:
        redirect('/quarantine/add?entity=%i&type=%s&why=%s&start=%s&end=%s&disable_until=%s' % (id, type, why, start, end, disable_until))

    q_type = transaction.get_quarantine_type(type)
    c = transaction.get_commands()
    date_start = start and c.strptime(start, "%Y-%m-%d") or c.get_date_now()
    date_end = end and c.strptime(end, "%Y-%m-%d") or None
    date_dis = disable_until and c.strptime(disable_until, "%Y-%m-%d") or None
    quoted = ''
    if why:
        quoted = html_quote(why)
    entity.add_quarantine(q_type, quoted, date_start, date_end, date_dis)
    
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
