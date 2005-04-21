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
from utils import url
from templates.WorkListTemplate import WorkListTemplate

def remember_url(object):
    import SpineIDL
    
    id = object.get_id()
    type = object.get_type().get_name()
    
    #create a string representing the object to the user
    name_str = None
    
    if type == 'person':
        for name in object.get_names():
            if name.get_name_variant().get_name() == "FULL":
                name_str = name.get_name()
                break
            
        if not name_str:
            name_str = 'Not available'
    
    else:
        name_str = object.get_name()

    name_str = "%s: %s" % (type.capitalize(), name_str)
    
    #store the obj in the session
    #if not req.session.has_key('worklist'):
    #    req.session['worklist'] = {}

    #req.session['worklist'][id] = (type, name_str)
    
    #return the code to call the method to remember the object
    js_url = "javascript:worklist_remember(%i, '%s', '%s');" % (id, type, name_str)
    return js_url

def remember_link(object, **vargs):
    return html.Anchor("remember", href=remember_url(object),
                       id="wrkElement%i" % object.get_id(), **vargs)

def select_selected():
    return ""

def forget_selected():
    return "javascript:worklist_forget();"

def all():
    return "javascript:worklist_select_all();"

def none():
    return "javascript:worklist_select_none();"

def invert():
    return "javascript:worklist_invert_selected();"


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
        buttons.append(("select", "Select", select_selected()))
        buttons.append(("forget", "Forget", forget_selected()))
        buttons.append(("all", "All", all()))
        buttons.append(("none", "None", none()))
        buttons.append(("invert", "Invert", invert()))
        return buttons
        

    def getActions(self):
        """Actions should return the links for the selected object.

        Should return list of list with link and label for each action.
        """
        actions = []
        actions.append(("view", "View"))
        return actions
 
# arch-tag: 3b1978e7-aca9-4641-ad12-1e7361a158d9
