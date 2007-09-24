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
import zipfile
import win32file, win32security

from ADobject import ADObject

const = ADconstants.Constants()


class AccountDir(ADObject):
	"""Class for manipulating directories related to an attribute in AD.
	   The default is homeDirectory."""	

	def __init__(self, *args, **kwargs):		
		super(AccountDir, self).__init__(*args, **kwargs)
		self.attribute = 'homeDirectory'

	def setAccDirAttrib(self, attrib):
		#Setting the current attribute field in AD to work with.
		self.attribute = attrib
		logging.debug("Setting AccDirAttribute to: %s" % self.attribute)
		return True

	def createDir(self, field = None):
		"""Creates the directory specified in the field 
			variable. Must bind to account."""
		
		retur = self.checkObject('createDir')
		if not retur[0]: 
			return retur

		if field == None:
			field = self.attribute

		dir = self.Object.Get(field)

		try:
			os.mkdir(dir)
		except:
			return self._log_exception('warn','createDir failed for:%s' % 
										dir)
			
		#Set rights on object.
		ret = self._setFullControl(dir, self.Object.Get('sAMAccountName'))
		if ret:
			return [True, 'createDir']
		else:
			return [False, 'CreateDir']
		

	def _setFullControl(self, path, uname):
		"""Sets "full control" access on path for an user in AD"""
 
		fileRights = win32file.FILE_ALL_ACCESS
		propagation = win32security.CONTAINER_INHERIT_ACE|win32security.OBJECT_INHERIT_ACE
		security_information = win32security.DACL_SECURITY_INFORMATION|win32security.OWNER_SECURITY_INFORMATION 

		try:
			pySD = win32security.GetNamedSecurityInfo(path, 
								win32security.SE_FILE_OBJECT, 
								security_information)

			Dacls = pySD.GetSecurityDescriptorDacl()
			SID = win32security.LookupAccountName(None, uname)[0]

			Dacls.AddAccessAllowedAceEx(win32security.ACL_REVISION_DS, 
									propagation, fileRights, SID)

			win32security.SetNamedSecurityInfo(path, 
							win32security.SE_FILE_OBJECT, 
							security_information,
							SID, None, Dacls, None)

			return True
		except:
			return self._log_exception('warn','setFullControl failed:%s' % homedir)

	def checkDir(self, field = None):
		"""Check if account physical directory described in field exists. 
		Must bind to object."""
		if field == None:
			field = self.attribute

		return os.path.exists(self.Object.Get(field))


	def renameDir(self, newpath, field = None):
 		"""rename a directory with a given new name, must bind. Remember 
		to escape the slashes in newpath."""
		if field == None:
			field = self.attribute

		os.rename(self.Object.Get(field), newpath)
		return os.path.exists(newpath)


	def deleteDir(self, field = None):
		"""Deletes a directory structure"""

		if field == None:
			field = self.attribute

		dirThree = self.Object.Get(field)
		function = getattr(self, '_rmgeneric')
		self._traverseDirRecursive(dirThree, function)

		#Managing to delete the last directory should indicate success.
		if self._rmgeneric(dirThree, False):
			return True
		else:
			return False


	def _rmgeneric(self, path, delfile=True):
		"""A generic remove function with errorchecking and logging"""
		try:
			if delfile:
				os.remove(path)
			else:
				os.rmdir(path)
			logging.debug("Deleted %s" % path)
		except OSError, (errno, strerror):
			logging.warning("Failed delete %s error %s" % 
				(path, strerror))
			return False
		return True


	def _traverseDirRecursive(self, path, __func__):
		"""Traveres a directory structure doing action specified in the function 
			__func__"""

		if not os.path.isdir(path):
			logging.warning("Path not a directory %s" % path)
			return False

		files=os.listdir(path)

		for x in files:
			fullpath=os.path.join(path, x)
 			if os.path.isfile(fullpath):
				__func__(fullpath)
			elif os.path.isdir(fullpath):
				self._traverseDirRecursive(fullpath, __func__)
				__func__(fullpath, False)



