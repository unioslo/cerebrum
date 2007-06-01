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
import sys, os
import ADconstants

const = ADconstants.Constants()

	
class ADObject(object):

	def __init__(self, *args, **kwargs):
		super(ADObject, self).__init__(*args, **kwargs)
		self.Object = None	
		self.distinguishedName = None
		self.type = None


	def _log_exception(self, ltype, function, name=None):
		logtype = getattr(logging, ltype)
		if name == None:
			name = self.distinguishedName

		logtype("%s %s %s failed: %s" % \
			(function, self.type, name, sys.exc_info()[1]))	
		return (False,"%s %s %s failed: %s" % \
			(function, self.type, name ,sys.exc_info()[1][1]))



	def checkObject(self, func='check_object'):
		if self.Object == None:
			logging.warn("Object is None in %s" % func)
			return (False, "Object is None in %s" % func)
		else:
			return (True, "checkObject")


	def bindObject(self, LDAPAccount):
		try:
			self.Object=win32com.client.GetObject('LDAP://%s' \
				% LDAPAccount)
			self.distinguishedName = self.Object.Get("distinguishedName")
			objectClass = self.Object.Get("objectClass")

			if 'group' in objectClass:
				self.type = 'Group'
			elif 'user' in objectClass:
				self.type = 'User'
			elif 'container' in objectClass:
				self.type = 'container'
			elif 'organizationalUnit' in objectClass \
				or 'domain' in objectClass:
				self.type = 'organizationalUnit'
			else:
				logging.fatal("Unknown objectClass %s for %s" % \
						(objectClass, LDAPAccount))
				return (False,"Unknown objectClass %s for %s" % \
						(objectClass, LDAPAccount))


		except pythoncom.com_error:
			self.clearObject()
			return self._log_exception('warn', 'bindObject', LDAPAccount)

		logging.debug("Binded to %s" % self.distinguishedName)
		return (True, "Binded to %s" % self.distinguishedName)


	def rebindObject(self):
		return self.bindObject(self.distinguishedName)


	def clearObject(self):
		logging.debug("Clear: %s" % self.distinguishedName)
		self.Object = None
		self.distinguishedName = None
		self.type = None
		return (True,"Object cleared.")


	def setObject(self):
		retur = self.checkObject('setObject')
		if not retur[0]: 
			return retur

		try:
			self.Object.SetInfo()
		except pythoncom.com_error:
			return self._log_exception('warn','setObject')

		logging.debug("Setinfo performed on %s" % self.distinguishedName)
		return (True,'SetInfo %s done.' % self.distinguishedName)


	def deleteObject(self):
		#Delete, must bind to object first. OU must be empty before deletion.
 
		retur = self.checkObject('deleteObject')
		if not retur[0]: 
			return retur
		
		#We must find and bind to the container the object resides in.
		OUparts = self.distinguishedName.split(',')
		OU = ",".join(OUparts[1:])
		name = OUparts[0] 
		type = self.type

		retur = self.bindObject(OU)

		if not retur[0]: 
			return retur

		try:
			self.Object.Delete(type, name)
			logging.debug('deleteObject %s' % name)

		except pythoncom.com_error:
			self.clearObject()
			return self._log_exception('warn','deleteObject', \
				'%s,%s' % (name,OU))

		self.clearObject()		
		return (True,'deleteObject %s %s,%s' % (type, name,OU))


	def moveObject(self, OU, Name=None):

		#If Name is specified explicit a rename is performed. 
		#must have a LDAP objecttype prefix (cn=<Name>)

		dName = self.distinguishedName
		dType = self.type
		retur = self.checkObject('moveObject')
		if not retur[0]: 
			return retur
			
		retur = self.bindObject(OU)
		if not retur[0]: 
			return retur
		
		if Name == None:
			Name = dName.split(',')[0]

		
		try:
			AccountObject = self.Object.moveHere('LDAP://%s' % dName, Name)
			logging.debug('moveObject %s to LDAP://%s' % (Name, OU))

		except pythoncom.com_error:
			self.clearObject()
			return self._log_exception('warn','moveObject', dName)

							
		#Setting Object as current working object.
		self.Object = AccountObject
		self.type = dType
		AccountObject = None		
		self.distinguishedName = self.Object.Get("distinguishedName")
		return (True,'moveObject %s' % self.distinguishedName)
				


	def createObject(self, objType, OU, Name):

	#Function that creates a new account in AD. And set the Account as 
	#the working object. Type is Group, User or organizationalUnit. Binds to 
	#the created object if successfully created.

		retur = self.bindObject(OU)
		if not retur[0]: 
			return (retur,'createObject')
		
		if objType == 'organizationalUnit':
			typePrefix = 'OU='
		else:
			typePrefix = 'CN='			

		try:
			AccountObject = self.Object.Create(objType,'%s%s' \
				% (typePrefix, Name))
			if objType != 'organizationalUnit':
				AccountObject.Put("sAMAccountName", Name)
			AccountObject.SetInfo()
			logging.debug('createObject %s%s,%s' % (typePrefix, Name, OU))

		except pythoncom.com_error:
			self.clearObject()
			return self._log_exception('warn','createObject', \
				'%s%s,%s' % (typePrefix, Name, OU))

							
		#Setting User as current working object.
		self.Object = AccountObject
		AccountObject = None		
		self.distinguishedName = self.Object.Get("distinguishedName")
		self.type = objType
		return (True,'createObject %s%s,%s' % (typePrefix, Name, OU))


	def getObjectProperties(self, properties):
		"""Fetch a list of specified properties from a AD Object"""

		retur = self.checkObject('getObjectProperties')
		if not retur[0]: 
			return retur

		accprop = {}

		for attr in properties:
			try:
				accprop[attr] = self.Object.Get(attr)
			except pythoncom.com_error:
				accprop[attr] = False

 		logging.debug("getObjectProperties:\n%s" % accprop)
		return (True, accprop)


	def setObjectProperties(self, accprop):
		"""Sets a dict of properties on an ADobject"""

		ADS_PROPERTY_CLEAR = 1
		ADS_PROPERTY_UPDATE = 2
		ADS_PROPERTY_APPEND = 3
		ADS_PROPERTY_DELETE = 4

		retur = self.checkObject('putObjectProperties')
		if not retur[0]: 
			return retur

		for attr in accprop:
			try:
				logging.debug('putProperty %s %s for %s' % \
					(attr, accprop[attr], self.distinguishedName))
				if accprop[attr] == "":
					self.Object.PutEx(ADS_PROPERTY_CLEAR, prop, 0)
				elif type(accprop[attr]) == list:
					self.Object.PutEx(ADS_PROPERTY_UPDATE,\
					attr, accprop[attr])
				else:
					self.Object.Put(attr, accprop[attr])
			except pythoncom.com_error:
				return self._log_exception('warn','setProperty %s=%s' % \
				(attr,accprop[attr]))

			logging.debug('putObjectProperty %s=%s for %s' % \
					(attr,accprop[attr],self.distinguishedName))
						
		return (True, "putObjectProperty %s" % self.distinguishedName)



class Account(ADObject):

	#UserAccountControlFlags also called UserFlags in WinNT 
	#support.microsoft.com/default.aspx?scid=kb;en-us;Q305144
	SCRIPT=1	
	ACCOUNTDISABLE=2	
	HOMEDIR_REQUIRED=8	
	LOCKOUT=16	
	PASSWD_NOTREQD=32	
	PASSWD_CANT_CHANGE=64
	ENCRYPTED_TEXT_PWD_ALLOWED=128	
	TEMP_DUPLICATE_ACCOUNT=256	
	NORMAL_ACCOUNT=512	
	INTERDOMAIN_TRUST_ACCOUNT=2048	
	WORKSTATION_TRUST_ACCOUNT=4096	
	SERVER_TRUST_ACCOUNT=8192	
	DONT_EXPIRE_PASSWORD=65536	
	MNS_LOGON_ACCOUNT=131072	
	SMARTCARD_REQUIRED=262144	
	TRUSTED_FOR_DELEGATION=524288	
	NOT_DELEGATED=1048576	
	USE_DES_KEY_ONLY=2097152	
	DONT_REQ_PREAUTH=4194304	
	PASSWORD_EXPIRED=8388608	
	TRUSTED_TO_AUTH_FOR_DELEGATION=16777216

	def __init__(self, *args, **kwargs):
		super(Account, self).__init__(*args, **kwargs)
		self.userAttributes = None
		self.userAccountControl = None


	def setUserAttributes(self,Attributes = None, AccountControl = None):
		#Takes a tuple with userFields
		self.userAttributes = Attributes
		self.userAccountControl = AccountControl
		logging.info('Registered UserAttributes:\n%s\n%s' % \
			(Attributes,AccountControl))
		return (True, "setUserAttributes")


	def getProperties(self):
	#Function that finds and returns values of the account object.

		retur = self.checkObject('getProperties')
		if not retur[0]: 
			return retur
		
		accprop = {}
		accprop["sAMAccountName"] = self.Object.Get("sAMAccountName")
		UAC = self.Object.Get("userAccountControl")

		for attr in self.userAttributes:

			try:
				accprop[attr] = self.Object.Get(attr)
			except pythoncom.com_error:
				accprop[attr] = False

		for attr in self.userAccountControl:
			#Cant read the PASSWD_CANT_CHANGE flag this way.
			Flag = getattr(self,attr)
			if UAC & Flag:		
				accprop[attr] = True
			else:
				accprop[attr] = False


 		logging.debug("getProp:\n%s" % accprop)
		return accprop


	def putProperties(self,accprop = {}):
		#sets properties on account. Rember to call SetObject afterwards.

		ADS_PROPERTY_CLEAR = 1
		ADS_PROPERTY_UPDATE = 2
		ADS_PROPERTY_APPEND = 3
		ADS_PROPERTY_DELETE = 4

		retur = self.checkObject('putProperties')
		if not retur[0]: 
			return retur

		UAC = self.Object.Get("userAccountControl")
		chgUAC = False

		for prop in accprop:

	 		if prop in self.userAttributes:
				try:
					logging.debug('putProperty %s %s for %s' % \
						(prop, accprop[prop], self.distinguishedName))
					if accprop[prop] == "":
						self.Object.PutEx(ADS_PROPERTY_CLEAR, prop, 0)
					elif type(accprop[prop]) == list:
						self.Object.PutEx(ADS_PROPERTY_UPDATE, \
											prop, accprop[prop])
					else:
						self.Object.Put(prop, accprop[prop])
				except pythoncom.com_error:
					return self._log_exception('warn','setProperty %s=%s' % \
					(prop,accprop[prop]))

			elif self.userAccountControl.has_key(prop):
				chgUAC = True
				Flag = getattr(self,prop)
				if accprop[prop]:
					if not UAC & Flag:
						UAC = UAC | Flag
				else:
					if UAC & Flag:
						UAC = UAC - Flag				

				logging.debug('putProperty %s=%s for %s' % \
					(prop,accprop[prop],self.distinguishedName))
			else:
				logging.warn("Undefined attribute %s" % prop)
				
		if chgUAC:
			try:
				self.Object.Put("userAccountControl",UAC)
				logging.debug('putProperty UAC %s for %s' % \
					(UAC, self.distinguishedName))
			except pythoncom.com_error:
				return self._log_exception('warn','putProperty UAC %s' % (UAC))
		
		return (True, "putProperty %s" % self.distinguishedName)


	def setPassword(self, password):
	#Change Password on an Account.
		retur = self.checkObject('setPassword')
		if not retur[0]: 
			return retur

		try:
			self.Object.setPassword(password)
			logging.debug('setPassword for %s OK' % \
				(self.distinguishedName))
		except pythoncom.com_error:
			return self._log_exception('warn','setPassword')
		return (True, 'setPassword')



class Group(ADObject):

	def __init__(self, *args, **kwargs):
		super(Group, self).__init__(*args, **kwargs)

	def addremoveMembers(self, memberList, LDAPPath, remove):
		#Takes a list of users and add/remove to group.
			
		errors = []		

		for memb in memberList:			
			inError = False
			if not LDAPPath:
				#We only got the sAMAccountname and search for the rest.
				tmpmemb = None
				tmpmemb = self.findObject(memb)
				if not tmpmemb:
					errors.append(memb)
					logging.debug('addremoveMembers: User %s to Group %s user do not exist' % (memb, self.distinguishedName))			
					inError=True
				else:
					memb = tmpmemb

			if not inError:
				try:
					if remove:
						if self.Object.isMember('LDAP://%s' % memb):
							self.Object.Remove('LDAP://%s' % memb)
							logging.debug('addremovemembers User %s removed from %s' % (memb, self.distinguishedName))		
						else:	
							logging.debug('addremoveMembers: User %s not member of %s' % (memb, self.distinguishedName))
					else:
						if not self.Object.isMember('LDAP://%s' % memb):
							self.Object.Add('LDAP://%s' % memb)
							logging.debug('addremovemembers User %s added to %s' % (memb, self.distinguishedName))		
						else:
							logging.debug('addremovemembers User %s already member of %s' % (memb, self.distinguishedName))		
				except pythoncom.com_error:
					logging.warn("addremoveMembers %s failed %s: %s" % \
						(self.distinguishedName, memb, sys.exc_info()[1]))
					errors.append(memb)

		if errors:			
			return (False, errors)
		else:
			return (True,'')
		
	def addMembers(self, memberList, LDAPPath=True):
		#wrapper for the addremoveMembers function.
		err = self.addremoveMembers(memberList, LDAPPath, False)		
		if err[0]:
			return (err[0],'addMembers')
		else:
			logging.warn('addMembers: failed for %s' % err[1])
			return (False, 'addMembers failed for %s' % err[1])


	def removeMembers(self, memberList, LDAPPath=True):
		#wrapper for the addremoveMembers function.
		err = self.addremoveMembers(memberList, LDAPPath, True)		
		if err[0]:
			return (err[0],'removeMembers')
		else:
			logging.warn('removeMembers: failed for %s' % err[1])
			return (False, 'removeMembers failed for %s' % err[1])


	def syncMembers(self, memberlist, LDAPPath = True, reportmissing = True):
		#Syncronice memberslist with group in AD. If LDAPPath is true
		#memberlist is given as a list with the full LDAPPath of object as a 
		#unicode string. 		

		#print self.distinguishedName
		#print "memberlist:%r" % memberlist
		logging.debug('Memberlist: %r' % memberlist)

		errors = ""
		error = False
		admemb = []		
		cerememb = []
		
		try:
			#Todo: Seems like it only returns a certain number of memebers  
			#when group is very large(1000+).
			members = self.Object.Member
			#Object.Member function delivers a tuple, but a unicode string if
			#single value.
			if members: 
				if type(members) == unicode:
					admemb.append(members)
				else:
					admemb = list(members)

		except pythoncom.com_error:
			return self._log_exception('warn','syncMembers')
	
		#print "admemb:%s" % admemb 
		logging.debug('admemb: %r' % admemb)

		if memberlist:
			if not LDAPPath:
				for memb in memberlist:
					# Find distinguishedName.
					tmpmemb = self.findObject(memb)
					if tmpmemb:
						cerememb.append(tmpmemb)						
					else:
						#Do not report missing users in AD. This is quarantined
						#in cerebrum. And therefore not created.
						if reportmissing: 
							errors = '%s%s' % (errors, memb)
							error = True
						logging.debug('syncMembers User %s to %s do not exist' % (memb, self.distinguishedName))			
			else:
				cerememb = memberlist	
		

			#print "cerememb:%r" % cerememb
			logging.debug('cerememb: %r' % cerememb)

			#Syncing group members.		
			for mem in cerememb:
				if mem in admemb:
					admemb.remove(mem)
				else:
					#Adding member to group in AD.
					if not self.Object.isMember('LDAP://%s' % mem):
						try:
							self.Object.Add('LDAP://%s' % mem)
							logging.debug('syncMember User %s Added to %s' % (mem, self.distinguishedName))		
						except pythoncom.com_error:
							logging.warn("syncMember Add %s failed %s: %s" % \
							(self.distinguishedName, mem, sys.exc_info()[1]))
							errors = '%s%s' % (errors, mem)
							error = True
					else:
						logging.debug('syncMember User %s already member of %s' % (mem, self.distinguishedName))		

		if admemb:
			#The remaining members in admemb is removed.
			logging.debug('Marked for deletion in admemb: %r' % admemb)
			for membrs in admemb:		
				if self.Object.isMember('LDAP://%s' % membrs):
					try:
						self.Object.Remove('LDAP://%s' % membrs)
						logging.debug('syncMember User %s removed from %s' % (membrs, self.distinguishedName))		
					except pythoncom.com_error:
						logging.warn("syncMember %s failed Remove %s: %s" % (self.distinguishedName, membrs, sys.exc_info()[1]))
						errors = '%s%s' % (errors, membrs)
						error = True
				else:
					logging.debug('syncMember User %s not a member of %s' % (membrs, self.distinguishedName))		



		if error:
			return [False, errors]
		else:
			return [True, 'syncMembers'] 
		


	def listMembers(self):
		#Return groupmembers. 
		#Todo: Seems like it only returns a certain number of memebers when 
		#group is very large.

		try:
			members = self.Object.Member
		except pythoncom.com_error:
			return self._log_exception('warn','listMembers')

		if members:
			return members
		else:
			return True


class Search(ADObject):

	def __init__(self, *args, **kwargs):
		super(Search, self).__init__(*args, **kwargs)
		self.objConnection=win32com.client.Dispatch('ADODB.Connection')
		self.objConnection.Provider = 'ADsDSOObject'
		self.objConnection.Open('Active Directory provider')
		self.objCom=win32com.client.Dispatch('ADODB.Command')
		self.objCom.ActiveConnection = self.objConnection
		self.objCom.Properties["Cache results"] = True
		self.objCom.Properties["Page Size"] = 1000		
		return True


	def listObjects(self, type, prop = False, OU = const.AD_LDAP_ROOT):

	#List all objects of a specific type. user, group or organizationalUnit
	#Builds a list. The properties flag will only work with type=user.

		listofobjects = []

		fields = 'distinguishedName'
		objecttype = ''

		if type == 'user':
				objecttype = "objectclass='user' AND objectcategory='Person'"
		elif type == 'group':
				objecttype = "objectclass='group' AND objectcategory='group'"
		elif type == 'organizationalUnit':
				objecttype = "objectclass='organizationalunit' AND objectcategory='OrganizationalUnit'"
		else:
				logging.critical('listObjects unknown type %s' % type )

		if prop:
			dictofobjects = {}
			if type == 'user':
				fields = '%s,sAMAccountName' % fields
				if self.userAttributes != None:
					for uAtt in self.userAttributes:
						fields = '%s,%s' % (fields,uAtt)
				if self.userAccountControl != None:
					fields = '%s,userAccountControl' % fields
			
		self.objCom.CommandText = ("SELECT '%s' FROM 'LDAP://%s' where %s" % (fields, OU, objecttype))

		try:
			(objRS, success) = self.objCom.Execute()
		except pythoncom.com_error, (hr, exc_msg, exc, arg_err):
			logging.critical('listObjects (%s)' % str(exc))
			return False		
	
		if prop and type == 'user':
			while not objRS.EOF:
				properties = {}
				properties['distinguishedName'] = objRS.Fields('distinguishedName').Value
				if self.userAttributes != None:
					for uAtt in self.userAttributes:
						if objRS.Fields(uAtt).Value !=  None:
							properties[uAtt] = objRS.Fields(uAtt).Value
	
				if self.userAccountControl != None:
									
					for uAC in self.userAccountControl:
						#Cant read the PASSWD_CANT_CHANGE flag this way.
						Flag = getattr(self,uAC)
						if objRS.Fields('userAccountControl').Value & Flag:		
							properties[uAC] = True
						else:
							properties[uAC] = False
 

				dictofobjects[objRS.Fields('sAMAccountName').Value] = properties
				objRS.MoveNext()

			logging.debug("dictObject:\n%s" % dictofobjects)
			return dictofobjects		
			
		else:		
			while not objRS.EOF:
				listofobjects.append(objRS.Fields("distinguishedName").Value)
				objRS.MoveNext()			
	
			logging.debug("listObject:\n%s" % listofobjects)
			return listofobjects


	def findObject(self,account,OU=False):
	#Search for an users or Group sAMAccountName and return the LDAP path.
	#Must be exact match, will not work for OUs.

		if OU:
			self.objCom.CommandText = ("SELECT Name,distinguishedName  \
			FROM 'LDAP://%s' WHERE objectClass='OrganizationalUnit' AND \
			Name = '%s'" % (const.AD_LDAP_ROOT,account))
		else:
			self.objCom.CommandText = ("SELECT distinguishedName, \
			sAMAccountName FROM 'LDAP://%s' where sAMAccountName='%s'" % \
			(const.AD_LDAP_ROOT,account))

		try:
			(objRS, success) = self.objCom.Execute()
			logging.debug("findObject:\n%s" %  \
					 objRS.Fields("distinguishedName").Value)
			return objRS.Fields("distinguishedName").Value
		except pythoncom.com_error, (hr, exc_msg, exc, arg_err):
			logging.warn('findObject on %s (%s)' % \
				(account, exc))
			return False

