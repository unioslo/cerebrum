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
from Cereweb.templates.WorkListTemplate import WorkListTemplate

# subclass Division to be included in a division..
class WorkList(html.Division):

    def __init__(self, req):
        if 'remembered' not in req.session:
            req.session['remembered'] = []
        if 'selected' not in req.session:
            req.session['selected'] = []
        self.remembered = req.session['remembered']
        self.selected = req.session['selected']

    def addEntity(self, id):
        self.remembered.append(id)

    def output(self):
        template = WorkListTemplate()
        objects = []
        for type, view, key in self.remembered:
            objects.append( (key, view) )
        selected = [str(object) for object in self.selected]
        buttons = self.getButtons()
        actions = self.getActions()
        return template.worklist(objects, buttons, actions, selected)

    def getButtons(self):
        """Returns a list with all buttons for the worklist.
        
        buttons contains a list of lists, where each sublist contains the 
        key and label for the button. The buttons are placed on the left
        side of the work list.
        """
        buttons = []
        buttons.append(("select", "Select"))
        buttons.append(("forget", "Forget"))
        buttons.append(("all", "All"))
        buttons.append(("none", "None"))
        buttons.append(("invert", "Invert"))
        return buttons
        

    def getActions(self):
        """Actions should return the links for the selected object.

        Should return list of list with link and label for each action.
        """
        actions = []
        actions.append(("view", "View"))
        return actions
 
# arch-tag: 3b1978e7-aca9-4641-ad12-1e7361a158d9
