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

from Cerebrum.web.templates.MainTemplate import MainTemplate
from Cerebrum.web import ActivityLog
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.SideMenu import SideMenu

class Main(MainTemplate):
    def __init__(self, req):
        MainTemplate.__init__(self)
        self.session = req.session
        self.prepare_session()
        self.menu = SideMenu()
        self.worklist = self.session['worklist']
        #self.activitylog = self.session['activitylog']
        #self.activitylog = lambda: ActivityLog.view_operator_history(self.session)

    def add_message(self, message, error=False):
        """Adds a message on top of page. If error is true, the 
        message will be highlighted as an error"""
        self.messages.append((message, error))

    def prepare_session(self):    
        #if not self.session.has_key("activitylog"):
        #    self.session['activitylog'] = ActivityLog() 
        if not self.session.has_key("worklist"):
            self.session['worklist'] = WorkList() 
        self.prepare_messages()
    
    def prepare_messages(self):        
        self.messages = []
        queued_messages = self.session.get("messages")
        if not queued_messages:
            return
        for (message, error) in queued_messages:
            self.add_message(message, error)
        # We've moved them from the queue to be shown on the page    
        del self.session['messages']    
        
    def setFocus(self, *args):
        self.menu.setFocus(*args)    
        


# arch-tag: 3f246425-25b1-4e28-a969-3f04c31264c7
