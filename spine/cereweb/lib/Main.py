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

import time
import cherrypy

from utils import get_messages
from SideMenu import SideMenu
from WorkList import WorkList
from ActivityLog import ActivityLog
from templates.FramesTemplate import FramesTemplate

class Main(FramesTemplate):
    """Creates the main page without any content.
    
    Creates the "static" part of all the webpages like: menu, transaction-box,
    worklist with links and activitylog. The design of the page comes from css
    and from the FramesTemplate, wich is a cheetah-template.
    """
    
    def __init__(self):
        """Creates all parts of the page beside the content."""
        cherrypy.response.headerMap['Content-Type'] = 'text/html; charset=iso-8859-1'
        cherrypy.response.headerMap['Pragma'] = 'no-cache'
        cherrypy.response.headerMap['Cache-Control'] = 'max-age=0'

        FramesTemplate.__init__(self)
        self.jscripts = []
        self.prepare_page()
        self.prepare_messages()

    def prepare_page(self):
        """Makes sure parts of the page is created only once.
        
        Creates worklist, and activitylog.
        """
        self.menu = SideMenu()
        self.worklist = WorkList()
        self.activitylog = ActivityLog()

    def prepare_messages(self):
        """Prepares messages for display.
        
        Displays and removes queued messages from the session queue.
        Adds them to the list over old messages.
        """
        self.messages = get_messages()
        
    def setFocus(self, *args):
        """Wraps the setFocus-method on the menu."""
        self.menu.setFocus(*args)

    def add_jscript(self, jscript):
        self.jscripts.append(jscript)

    def __iter__(self):
        return iter(str(self))

# arch-tag: 3f246425-25b1-4e28-a969-3f04c31264c7
