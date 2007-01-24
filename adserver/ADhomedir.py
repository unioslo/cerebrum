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
import sys, os, shutil
import ADconstants

const = ADconstants.Constants()

	
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

import os
import win32security
import win32file

from ADobject import ADObject

class Homedir(ADObject):

	def __init__(self, *args, **kwargs):
		super(Homedir, self).__init__(*args, **kwargs)


	def createHomedir(self):
		"""Creates the directory specified in the accounts homeDirectory 
			variable in AD. Must bind to account."""
		
		retur = self.checkObject('createHomedir')
		if not retur[0]: 
			return retur

		homedir = self.Object.Get('homeDirectory')

		try:
			os.mkdir(homedir)
		except:
			return self._log_exception('warn','createHomedir failed:%s' % 
										homedir)
			
		#Set rights on object.
		ret = self._setFullControl(homedir, self.Object.Get('sAMAccountName'))
		
		return [True, 'Homedir']

		
	def _setFullControl(self, path, uname):
		"""Sets "full control" access on path for an user in AD"""
 
		fileRights = win32file.FILE_ALL_ACCESS
		propagation = win32security.CONTAINER_INHERIT_ACE|win32security.OBJECT_INHERIT_ACE

		try:
			pySD = win32security.GetNamedSecurityInfo(path, 
								win32security.SE_FILE_OBJECT, 
								win32security.DACL_SECURITY_INFORMATION)

			Dacls = pySD.GetSecurityDescriptorDacl()
			SID = win32security.LookupAccountName(None, uname)

			Dacls.AddAccessAllowedAceEx(win32security.ACL_REVISION_DS, 
									propagation, fileRights, SID[0])

			ret = win32security.SetNamedSecurityInfo(path, 
							win32security.SE_FILE_OBJECT, 
							win32security.DACL_SECURITY_INFORMATION,
							None,None,Dacls,None)
			return ret
		except:
			return self._log_exception('warn','setFullControl failed:%s' % homedir)


	def copyDir(self):
		"""Copy directory structure in the COPYDIR variable in Constants.py 
			to Homedir. For initialization of a homedir. Must bind."""
		try:
			shutil.copytree(const.COPYDIR, self.Object.Get('homeDirectory'))
		except:
			return self._log_exception('warn','copyDir failed:%s' % 
					self.Object.Get('homeDirectory'))
		return [True, 'copyDir']


	def checkHomeDir(self):
		"""Check if account has a homedir. Must bind to object."""
		return os.path.exists(self.Object.Get('homeDirectory'))


	def renameHomeDir(self, newpath):
 		"""rename a directory with a given new name, must bind. Remember 
		to escape the slashes in newpath."""
		os.rename(self.Object.Get('homeDirectory'), newpath)
		return os.path.exists(newpath)


