# -*- coding: iso-8859-1 -*-
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
 
"""
 
"""

import time, string
import cerebrum_path
import cereconf
 
from Cerebrum.extlib import logging
from Cerebrum.Database import Errors
from Cerebrum.modules import LDIFutils
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory, latin1_to_iso646_60, auto_super
 
 
logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("console")
 


class PosixLDIF(object):
    """
    Generates posix-user, -filegroups and -netgroups. Do not support hosts
    in netgroups. 
    """

    __metaclass__ = auto_super
 
    def __init__(self, db, u_sprd = None, g_sprd = None, n_sprd = None):
	"""
	Initiate database and import modules. Spreads are given in initiation 
	and general constants which is used in more than one method.
	"""
	super(PosixLDIF, self).__init__(db)
	from Cerebrum.modules import PosixUser, PosixGroup
	from Cerebrum.QuarantineHandler import QuarantineHandler
        self.db		= db
        self.logger	= logger
        self.const	= Factory.get('Constants')(self.db)
        self.base_dn	= getattr(cereconf, 'LDAP_BASE_DN', None)
	self.posuser	= PosixUser.PosixUser(self.db)
	self.posgrp	= PosixGroup.PosixGroup(self.db)
        self.user_dn	= LDIFutils.get_tree_dn('USER', None)
	self.get_name 	= True
	
	self.spread_d = {}
	# Validate spread from arg or from cereconf
	for x,y in zip(['USER','FILEGROUP','NETGROUP'],[u_sprd,g_sprd,n_sprd]):
	    conf_str = 'LDAP' + '_' + x
	    if y or getattr(cereconf,conf_str).has_key('spread'):
		spread = y or getattr(cereconf,conf_str)['spread']
		# Chech input format
		if isinstance(spread,(list,tuple)):
		    self.spread_d[x.lower()] = [int(getattr(self.const,z)) \
							for z in spread if z]
		elif isinstance(spread,str):
		    self.spread_d[x.lower()] = [int(getattr(self.const,spread)),]
		elif isinstance(spread,int):
		    self.spread_d[x.lower()] = [spread,]
		else:
		    raise ValueError,'Not a valid spread: %s' % spread
	if not self.spread_d:
	    raise ProgrammingError, "Must specify spread-value as 'arg' or in cereconf"
        self.id2uname	= {} 	   

	ior row in test1:

    def user_ldif(self, f, auth_meth = None):
	"""
	Generate posix-user. 
	"""
	self.init_user(auth_meth)
	f.write(LDIFutils.container_entry_string('USER'))
	for row in self.posuser.list_extended_posix_users(
	    			self.user_auth ,
				spread = self.spread_d['user'],
				include_quarantines = False):
	    dn,entry = self.user_object(row)
	    if dn:
		f.write(LDIFutils.entry_string(dn, entry, False))
	

    def init_user(self, auth_meth=None):
	self.get_name = False
	from Cerebrum.modules import PosixUser
	self.posuser = PosixUser.PosixUser(self.db)
	self.load_disk_tab()
        self.load_shell_tab()
	self.load_quaratines()
	self.load_auth_tab(auth_meth)

    def auth_methods(self, auth_meth=None):
	"""
	Which authentication methods to fetch. Mixin-support.
	If all only one entry, it will prefect any in auth_table.
	If 'none', it will use default API authentication (crypt3des).
	"""
	auth_meth_l = []
	self.user_auth = None
	# Priority is arg, else cereconf default value
	auth = auth_meth or cereconf.LDAP_AUTH_METHOD
	if isinstance(auth,(list,tuple)):
	     self.user_auth = int(getattr(self.const,auth[:1][0]))
	     for entry in auth[1:]:
		auth_meth_l.append(int(getattr(self.const,entry)))
	elif isinstance(auth,str):
	    self.user_auth = int(getattr(self.const,auth))
	return auth_meth_l

    def load_auth_tab(self,auth_meth=None):
	self.auth_data = {}
	method = self.auth_methods(auth_meth)
	if method:
	    for x in self.posuser.list_account_authentication(auth_type=method):
		if not x['account_id'] or not  x['method']:
		    continue
		acc_id, meth = int(x['account_id']), int(x['method']) 
		if not self.auth_data.has_key(acc_id):
		    self.auth_data[acc_id] = {meth : x['auth_data']}
		else:
		    self.auth_data[acc_id][meth] = x['auth_data']
	

    def load_disk_tab(self):
	from Cerebrum import Disk
	self.disk = Factory.get('Disk')(self.db)
	self.disk_tab = {}
	for hd in self.disk.list():
	    self.disk_tab[int(hd['disk_id'])] = hd['path']

    def load_shell_tab(self):
	self.shell_tab = {}
    	for sh in self.posuser.list_shells():
	    self.shell_tab[int(sh['code'])] = sh['shell']

    def load_quaratines(self):
	self.quarantines = {}
	now = self.db.DateFromTicks(time.time())
	for row in self.posuser.list_entity_quarantines(
            		entity_types = self.const.entity_account):
            if (row['start_date'] <= now and (row['end_date'] is None \
					or row['end_date'] >= now) \
					and (row['disable_until'] is None \
					or row['disable_until'] < now)):
		# The quarantine in this row is currently active.
            	self.quarantines.setdefault(int(row['entity_id']), []).append(
                		int(row['quarantine_type']))


    def user_object(self,row):
	account_id = int(row['account_id'])
	uname = row['entity_name']
	passwd = '{crypt}*Invalid'
	if row['auth_data']:
	    passwd = "{crypt}" + row['auth_data']
	else:
	    method = int(self.const.auth_type_crypt3_des)
	    try:
		passwd = '{crypt}' + self.auth_data[account_id][method]
	    except KeyError:
		pass
	if not row['shell']:
	    self.logger.warn("User % have no posix-shell!" % uname)
	    return None, None
	else:
	    shell = self.shell_tab[int(row['shell'])] 
	if self.quarantines.has_key(account_id):
	    qh = QuarantineHandler(self.db, self.quarantines[account_id])
	    if qh.should_skip():
		return None, None
	    if qh.is_locked():
		passwd = '{crypt}' + '*Locked'
	    qshell = qh.get_shell()
	    if qshell is not None:
		shell = qshell
	if row['disk_id']:
	    home = "%s/%s" % (self.disk_tab[int(row['disk_id'])],uname)
	elif row['home']:
	    home = row['home']
	else:
	    self-logger.warn("User % has no home-directory!" % uname)
	    return None,None
	cn = row['name'] or row['gecos'] or uname
	gecos = latin1_to_iso646_60(row['gecos'] or cn)
	entry = {'objectClass':['top','account','posixAccount'],
			'cn':(LDIFutils.iso2utf(cn),),
			'uid':(uname,),
			'uidNumber':(str(int(row['posix_uid'])),),
			'gidNumber':(str(int(row['posix_gid'])),),
			'homeDirectory':(home,),      
			'userPassword':(passwd,),
			'loginShell': (shell,),
			'gecos':(gecos,)}     
	self.update_user_entry(account_id, entry, row)
	if not self.id2uname.has_key(account_id):
	    self.id2uname[account_id] = uname
	else:
	    self.logger.warn('Duplicate user-entry: (%s,%s)!' % (account_id,uname)) 
	    return None,None
	dn = ','.join((('uid=' + uname),self.user_dn))
	return dn,entry

    def update_user_entry(self,account_id,entry,row):
	"""
	To call Mixin-class. (Should consider support for multiple mixin.) 
	"""
	pass



    def filegroup_ldif(self,f):
	"""
	Generate filegroup. Groups without group and expanded  members 
	from both external and internal groups.
	"""
        self.init_filegroup()
        f.write(LDIFutils.container_entry_string('FILEGROUP'))
	for row in self.posgrp.list_all_grp(self.spread_d['filegroup']):
	    dn,entry = self.filegroup_object(row)
	    if dn:
		f.write(LDIFutils.entry_string(dn, entry, False))
	    
	    
	
    def init_filegroup(self):
	""" Initiate modules and constants for posixgroup"""
	from Cerebrum.modules import PosixGroup
	self.posgrp = PosixGroup.PosixGroup(self.db)
	self.fgrp_dn = LDIFutils.get_tree_dn('FILEGROUP')

    def filegroup_object(self,row):
	""" Create the group-entry attributes"""
	self.posgrp.clear()
        self.posgrp.find(row.group_id)
	gname = LDIFutils.iso2utf(self.posgrp.group_name)
	if not self.id2uname.has_key(int(row.group_id)):
	    self.id2uname[int(row.group_id)] = gname
        members = []
        entry = {'objectClass': ('top', 'posixGroup'),
                 'cn':          (gname,),
                 'gidNumber':   (str(int(self.posgrp.posix_gid)),)}
        if self.posgrp.description:
            # latin1_to_iso646_60 later
            entry['description'] = (LDIFutils.iso2utf(self.posgrp.description),)
        for id in self.posgrp.get_members(spread=self.spread_d['user'][0], 
						get_entity_name=self.get_name):
	    if self.get_name:
		uname_id = int(id[0])
		uname = id[1]
	    else:
		uname_id = int(id)
            #if self.get_name and not self.id2uname.has_key(uname_id):
            #    self.id2uname[uname_id] = id[1]
	    if not self.id2uname.has_key(uname_id) or self.get_name:
		# Have find a way to resolve this problem later
		self.logger.warn("Could not resolve name on account-id: %s" % uname_id)
		continue
	    members.append(self.id2uname[uname_id])
	    #members.append(uname)		
	entry['memberUid'] = members
	self.update_filegroup_entry(entry, row)
	dn = ','.join((('cn=' + gname), self.fgrp_dn))
	return dn,entry

    def update_filegroup_entry(self, entry, row):
	""" Future use of mixin-classes"""
	pass


    def netgroup_ldif(self, f):
	"""
	Generate netgroup with only users.
	"""
	self.init_netgroup()
	f.write(LDIFutils.container_entry_string('NETGROUP'))
	for row in self.grp.list_all_grp(self.spread_d['netgroup']):
		dn,entry = self.netgroup_object(row)
		if dn:
		    f.write(LDIFutils.entry_string(dn, entry, False))
	
    def init_netgroup(self):
	"""
	Initiate modules and constants.
	"""
	self.ngrp_dn = LDIFutils.get_tree_dn('NETGROUP')
	# Sjekk om det ikke holder med posgrp
	from Cerebrum import Group
	self.grp = Factory.get('Group')(self.db)
	
    def netgroup_object(self, row):
	"""
	Generate netgroup objects. 
	"""
        self._gmemb = {}
        self.grp.clear()
        self.grp.find(row.group_id)
        netgrp_name = LDIFutils.iso2utf(self.grp.group_name)
        entry = {'objectClass':       ('top', 'nisNetGroup'),
                 'cn':                (netgrp_name,),
                 'nisNetgroupTriple': [],
                 'memberNisNetgroup': []}
        if not self.id2uname.has_key(int(row.group_id)):
            self.id2uname[int(row.group_id)] = netgrp_name
        if self.grp.description:
            entry['description'] = (\
                latin1_to_iso646_60(self.grp.description).rstrip(),)
        self.get_netgrp(entry['nisNetgroupTriple'], entry['memberNisNetgroup'])
	dn = ','.join((('cn=' + netgrp_name), self.ngrp_dn))
	return dn, entry


    def get_netgrp(self, triples, memgrp):
	"""
	Recursive method to get members and groups in netgroup.
	"""
	for union  in self.grp.list_members(self.spread_d['user'][0],\
					int(self.const.entity_account),\
                                        get_entity_name= self.get_name)[0]:
	    if self.get_name:
		uname_id,uname = int(union[1]),union[2]
	    else:
		uname_id = int(union[1])
		try:
		    uname = self.id2uname[uname_id]
		except:
		    self.logger.warn('Cache enabled but user:%s not found' % \
								uname_id)
		    self._gmemb[uname_id] = True
	    if ("_" not in uname) and not self._gmemb.has_key(uname_id):
		triples.append("(,%s,)" % uname)
		self._gmemb[uname_id] = True
	for union in self.grp.list_members(None,\
						int(self.const.entity_group),\
                                                get_entity_name=True)[0]:
	    self.grp.clear()
	    self.grp.entity_id = int(union[1])
	    if filter(self.grp.has_spread,self.spread_d['netgroup']):
		memgrp.append(LDIFutils.iso2utf(union[2]))
	    else:
		self.get_netgrp(triples, memgrp)


