#
# Copyright 2003 University of Oslo, Norway
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

import win32com.client
import pythoncom
import logging
import ADconstants


const = ADconstants.Constants()

from ADobject import ADObject


class Exchange(ADObject):
    """Class for manipulating mailboxes in exchange. IMPORTANT: Exchange 
       System Manager tools must be installed for this class to work"""  

    def __init__(self, *args, **kwargs):
        super(Exchange, self).__init__(*args, **kwargs)


    def createMDB(self):
        """Creates a mailbox. Must bing to object, remember setinfo 
           afterwords."""
	MDB = self.Object.Get('HomeMDB') 
        if MDB == None:
            return [False, 'No Mailbox registered in AD']
	else:		
            ret = self.Object.CreateMailbox(MDB)
	    return [ret, 'createMDB']


    def deleteMDB(self):
	"""Deletes a mailbox. Must bing to object, remember setinfo 
           afterwords.""" 
	MDB = self.Object.Get('HomeMDB')
        if MDB == None: 
            return [False, 'No Mailbox registered in AD']
	else:		
            ret = self.Object.DeleteMailbox(MDB)
            return [ret, 'deleteMDB']


    def checkMDB(self):
        """Returns True/False if HomeMDB attribute is registered in AD.""" 
        if self.Object.Get('HomeMDB') == None:
            return False
	else:
            return True 


    def moveMDB(self, MDB):
	"""Must bind to object. Moves a mailbox from one location to another, 
           also used for renaming of a mailbox."""

	CurrentMDB = self.Object.Get('HomeMDB')
	if CurrentMDB == None:
            return [False, 'No mailbox to move']
	else:
            ret = self.Object.MoveMailBox(MDB)
	    return [ret, 'moveMDB']	