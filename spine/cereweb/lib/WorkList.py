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

import cherrypy

import forgetHTML as html
import utils
from templates.WorkListTemplate import WorkListTemplate

def remember_args(object):
    import SpineIDL
    
    id = object.get_id()
    type = utils._spine_type(object).capitalize()
    
    if type == 'Person':
        name_str = None
        for name in object.get_names():
            if name.get_name_variant().get_name() == "FULL":
                name_str = name.get_name()
                break
        if not name_str:
            name_str = 'Not available'
    elif type == 'Disk':
        name_str = object.get_path()
    elif type == 'Project':
        name_str = object.get_title()
    elif type == 'Allocation':
        # XXX often not unique
        name_str = object.get_allocation_name().get_name()
    else:
        name_str = object.get_name()

    return id, type, name_str, "%s: %s" % (type, name_str)

def remember_link(object, text='remember', _class=None):
    id, type, name, display_name = remember_args(object)
    url = "javascript:WL_remember(%i, '%s', '%s');" % (id, type, name)
    id = 'WL_link_%i' % id
    _class = _class and ' class="%s"' % _class or ''
    return '<a href="%s" id="%s" %s>%s</a>' % (url, id, _class, text)

class WorkListElement:
    
    def __init__(self, id=None, cls=None, name=None, object=None):
        if object:
            id, cls, name, display_name = remember_args(object)
        elif id and cls and name:
            cls = cls.capitalize()
            display_name = "%s: %s" % (cls, name)
        else:
            raise AttributError, "Either set object or id, cls, name"

        self.id = id
        self.cls = cls
        self.name = name
        self.display_name = display_name

    def __repr__(self):
        return "WorklistElement: %s" % self.display_name

class WorkList(html.Division):
    
    def __init__(self):
        if 'wl_remembered' not in cherrypy.session:
            cherrypy.session['wl_remembered'] = []
        if 'wl_selected' not in cherrypy.session:
            cherrypy.session['wl_selected'] = []
        if 'wl_actions' not in cherrypy.session:
            cherrypy.session['wl_actions'] = []
        self.remembered = cherrypy.session['wl_remembered']
        self.selected = cherrypy.session['wl_selected']
        self.actions = cherrypy.session['wl_actions']
     
    def __call__(self,*args):
        return self.output()
    
    def add(self, element):
        self.remembered.append(element)

    def remove(self, id=None, element=None):
        if element is None:
            element, = [i for i in self.remembered if i.id == id]
        self.remembered.remove(element)

    def output(self):
        template = WorkListTemplate()
        objects = [(i.id, i.display_name) for i in self.remembered]
        selected = [i.id for i in self.selected]
        return template.worklist(objects, selected, self.getButtons())

    def getButtons(self):
        """Returns a list with all buttons for the worklist.
        
        buttons contains a list of lists, where each sublist contains the 
        key and label for the button. The buttons are placed on the left
        side of the work list.
        """
        buttons = []
        buttons.append(("all", "All"))
        buttons.append(("none", "None"))
        buttons.append(("invert", "Invert"))
        buttons.append(("forget", "Forget"))
        return buttons
        
# arch-tag: 3b1978e7-aca9-4641-ad12-1e7361a158d9
