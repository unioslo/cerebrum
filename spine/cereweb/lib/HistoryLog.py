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

from TableView import TableView
from utils import object_link
from gettext import gettext as _
from templates.HistoryLogTemplate import HistoryLogTemplate
import SpineIDL.Errors

def view_history_short(entity):
    # Could use some other template for 'short' view 
    template = HistoryLogTemplate()
    events = entity.get_history()[:5]
    table = _history_tableview(events)
    return template.viewHistoryLog(table, entity.get_id())

def view_history(entity):
    template = HistoryLogTemplate()
    events = entity.get_history()
    table = _history_tableview(events)
    return template.viewCompleteHistoryLog(table)


def view_history_all(transaction, n=50, offset=0):
    template = HistoryLogTemplate()
    cls = transaction.get_change_log_searcher()
    cls.order_by_desc(cls, 'id')
    cls.set_search_limit(n, offset)
    events = cls.search()
    table = _history_tableview(events, show_subject=True,
                               transaction=transaction)
    return template.viewCompleteHistoryLog(table)

def object_wrapper(object):
    """Wraps an object into a nice stringified link, if possible"""
    try:
        return str(object_link(object))
    except:
        try:
            return str(object)
        except:
            return repr(object)    


def _history_tableview(events, show_subject=False, transaction=None):
    columns = ['timestamp']
    headers = [_('Timestamp')]
    if show_subject:
        columns += ['subject_entity']
        headers += [_('Object')]
    columns += ['icon', 'who', 'category', 'message']
    headers += [_('Icon'), _('Changed by'), _('Category'), _('Message')]

    table = TableView(columns, headers)
    for change in events:
        row={}
        change_by = change.get_change_by()
        if change_by:
            row['who'] = object_link(change_by)
        else:
            row['who'] = change.get_change_program() or 'unknown'

        if show_subject:
            subject_entity_id = change.get_subject_entity()
            try:
                subject_entity = transaction.get_entity(subject_entity_id)
                row['subject_entity'] = object_link(subject_entity)
            except SpineIDL.Errors.NotFoundError:
                row['subject_entity'] = _('Deleted (%s)') % subject_entity_id
        type = change.get_type()

        row['timestamp'] = change.get_timestamp().strftime("%Y-%m-%d %H:%M:%S")
        row['category'] = type.get_category()
        row['icon'] = '<img src=\"/img/%s\" alt=\"%s\" />' % (
            get_icon_by_change_type(type.get_type()),
            type.get_type())
        row['message'] = change.get_message()
        table.add(**row)
    return table  

        
def get_icon_by_change_type(changetype):
    type = changetype.split("_")[-1]
    icon_map = {
        "add" : "add.png",
        "del" : "delete.png",
        "delete" : "delete.png",
        "rem" : "remove.png",
        "create" : "create.png",
        "mod" : "modify.png"
    }
    icon=icon_map.get(type, "blank.png")
    return icon
 
# arch-tag: c867b6bd-9a66-4967-9e41-fa88f669a641
