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

from Cereweb.templates.HistoryLogTemplate import HistoryLogTemplate
from Cereweb.TableView import TableView
from Cereweb.utils import url
from Cereweb.utils import object_link
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
import types

def view_history_short(entity):
    # Could use some other template for 'short' view 
    template = HistoryLogTemplate()
    events = entity.get_history(5)
    id = entity.id
    table = _history_tableview(events)
    return template.viewHistoryLog(table, id)

def view_history(entity):
    template = HistoryLogTemplate()
    events = entity.get_history()
    table = _history_tableview(events)
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

def _history_tableview(events):    
            
    table = TableView("timestamp", "icon", "who", "message")
    for change in events:
        if type(change.change_by) in types.StringTypes:
            who = change.change_by
        else:
            who = object_link(change.change_by)
        icon = get_icon_by_change_type(change.type.type)
        #server = req.session['server']
        #ent = ClientAPI.fetch_object_by_id(server, change.change_by)
        #who = ent.name            
        table.add(timestamp=change.date.Format("%Y-%m-%d"),
                  who=who,
                  # TODO: Should use hyperlinks on references 
                  message=change.message(object_wrapper), 
                  icon='<img src=\"'+url("img/"+icon)+'\">') 
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
