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

from Cerebrum.web.templates.WorkListTemplate import WorkListTemplate

import forgetHTML as html

# subclass Division to be included in a division..
class WorkList(html.Division):
    def __init__(self):
        self.remembered = []
        self.selected = []
    def addEntity(self, id):
        object = APImannen.getEntity(id)
        self.remembered.append(object)
    def output(self):
        template = WorkListTemplate()
        objects = []
        for object in self.remembered:
            view = str(object)
            key = object.getEntityID()
            objects.append( (key, view) )
        selected = [object.getEntityID() for object in self.selected]       
        actions = self.getActions()
        return template.worklist(objects, actions, selected)
    def getActions(self):
        actions = []
        actions.append(("view", "View"))
        actions.append(("edit", "Edit"))
        actions.append(("delete", "Delete"))
        actions.append(("fix", "Fix it"))
        return actions
            

# arch-tag: 3b1978e7-aca9-4641-ad12-1e7361a158d9
