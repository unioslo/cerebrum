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
from Cerebrum.web.SideMenu import SideMenu
from Cerebrum.web.Transactions import TransactionBox
from Cerebrum.web.WorkList import WorkList
from Cerebrum.web.ActivityLog import ActivityLog

class Main(MainTemplate):
    """Creates the main page without any content.
    
    Creates the "static" part of all the webpages like: menu, transaction-box,
    worklist with links and activitylog. The design of the page comes from css
    and from the MainTemplate, wich is a cheetah-template.
    """
    
    def __init__(self, req):
        """Creates all parts of the page beside the content."""
        MainTemplate.__init__(self)
        req.content_type="text/html" # With this content-type, æøå works! :)
        self.session = req.session
        self.prepare_session()
        self.menu = SideMenu()
        self.transactionbox = self.session['transactionbox']
        self.worklist = self.session['worklist']
        self.activitylog = self.session['activitylog']

    def prepare_session(self):
        """Makes sure parts of the page is created only once.
        
        Creates the transaction, worklist, and activitylog.
        Also prepares and displays any messages stored in the session.
        """
        if not self.session.has_key("transactionbox"):
           self.session['transactionbox'] = TransactionBox()
        if not self.session.has_key("worklist"):
            self.session['worklist'] = WorkList() 
        if not self.session.has_key("activitylog"):
            self.session['activitylog'] = ActivityLog() 
        self.prepare_messages()
    
    def prepare_messages(self):
        """Displays and removes queued messages from the session qeue."""
        self.messages = []
        queued_messages = self.session.get("messages")
        if not queued_messages:
            return
        for (message, error) in queued_messages:
            self.add_message(message, error)
        # We've moved them from the queue to be shown on the page
        del self.session['messages']
        
    def add_message(self, message, error=False):
        """Adds a message on top of page. If error is true, the 
        message will be highlighted as an error"""
        self.messages.append((message, error))

    def setFocus(self, *args):
        """Wraps the setFocus-method on the menu."""
        self.menu.setFocus(*args)

# arch-tag: 3f246425-25b1-4e28-a969-3f04c31264c7
