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

##from Cerebrum.web.templates.HistoryLogTemplate import HistoryLogTemplate
from Cerebrum.web.templates.ActivityLogTemplate import ActivityLogTemplate
from Cerebrum.web.TableView import TableView
from Cerebrum.web.HistoryLog import object_wrapper
from Cerebrum.web.utils import url
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
#from Cerebrum.web.Main import Main
import types
#import forgetHTML as html
                                                                                                                                                                            
def view_operator_history(session, limit=10):
    template = ActivityLogTemplate()
    server = session['server']
    events = session.get('operator_events')
    if not events:
        # get all  (TODO: Only one week or younger)
        events = ClientAPI.operator_history(server, )
    else:
        last_event = events[-1]
        # just get the new ones
        events.extend(ClientAPI.operator_history(server, last_event))
                                                                                                                                                                            
    # chop of the limit last events (if limit is 0 - all events)
    events = events[-limit:]
    session['operator_events'] = events
    table = _activity_tableview(events)
    return template.viewActivityLog(table)
                                                                                                                                                                            
def _activity_tableview(events):
    table = TableView("icon", "message")
    for change in events:
        icon = get_icon_by_change_type(change.type.type)
        #server = req.session['server']
        #ent = ClientAPI.fetch_object_by_id(server, change.change_by)
        #who = ent.name
        table.add(message=change.message(object_wrapper),
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
            

# arch-tag: ed8a9388-5b3e-4650-96bf-add0ba181744
