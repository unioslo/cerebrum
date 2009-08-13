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
 
"""
 
"""

import time, sys
import mx
 
import cereconf
from Cerebrum.modules import LDIFutils
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory, latin1_to_iso646_60, auto_super
 
 
# logger = Factory.get_logger("cronjob")
 


class PosixLDIF(object):
    """Generates posix-user, -filegroups and -netgroups. 
    Does not support hosts in netgroups.
    """

    __metaclass__ = auto_super
 
    def __init__(self, db, logger, u_sprd = None, g_sprd = None, n_sprd = None, fd=None):
        """Initiate database and import modules. 
        Spreads are given in initiation and general constants which is
        used in more than one method.
        """
        super(PosixLDIF, self).__init__(db)
        from Cerebrum.modules import PosixUser, PosixGroup
        from Cerebrum.QuarantineHandler import QuarantineHandler
        self.db = db
        self.logger = logger
        self.const = Factory.get('Constants')(self.db)
        self.posuser = PosixUser.PosixUser(self.db)
        self.posgrp = PosixGroup.PosixGroup(self.db)
        self.user_dn = LDIFutils.ldapconf('USER', 'dn', None)
        self.get_name = True
        self.fd = fd
        
        self.spread_d = {}
        # Validate spread from arg or from cereconf
        for x,y in zip(['USER','FILEGROUP','NETGROUP'],[u_sprd,g_sprd,n_sprd]):
            spread = LDIFutils.map_spreads(
                y or getattr(cereconf, 'LDAP_' + x).get('spread'), list)
            if spread:
                self.spread_d[x.lower()] = spread
        if not self.spread_d.has_key('user'):
            raise ProgrammingError, "Must specify spread-value as 'arg' or in cereconf"
        self.id2uname        = {}

        # preload id->name mapping for later. This is potentially somewhat
        # memory expensive.
        # FIXME: do id2uname and entity2name have the same content?
        if self.get_name:
            self.entity2name = dict([(x["entity_id"], x["entity_name"]) for x in
                              self.posgrp.list_names(self.const.account_namespace)])
            self.entity2name.update([(x["entity_id"], x["entity_name"]) for x in
                              self.posgrp.list_names(self.const.group_namespace)])
    # end __init__


    def user_ldif(self, filename=None, auth_meth = None):
        """Generate posix-user."""
        f = LDIFutils.ldif_outfile('USER', filename, self.fd)
        self.init_user(auth_meth)
        f.write(LDIFutils.container_entry_string('USER'))
        for row in self.posuser.list_extended_posix_users(
                                    self.user_auth ,
                                spread = self.spread_d['user'],
                                include_quarantines = False):
            dn,entry = self.user_object(row)
            if dn:
                f.write(LDIFutils.entry_string(dn, entry, False))
        LDIFutils.end_ldif_outfile('USER', f, self.fd)
        

    def init_user(self, auth_meth=None):
        self.get_name = False
        from Cerebrum.modules import PosixUser
        self.posuser = PosixUser.PosixUser(self.db)
        self.load_disk_tab()
        self.load_shell_tab()
        self.load_quaratines()
        self.load_auth_tab(auth_meth)

    def auth_methods(self, auth_meth=None):
        """Which authentication methods to fetch. Mixin-support.
        If all only one entry, it will prefect any in auth_table.
        If None, it will use default API authentication (crypt3des).
        """
        self.auth_format = {}
        auth_meth_l = []
        self.user_auth = None
        code = '_AuthenticationCode'
        # Priority is arg, else cereconf default value
        # auth_meth_l is a list sent to load_auth_tab and contains
        # all methods minus primary which is called by 
        auth = auth_meth or cereconf.LDAP['auth_attr']
        if isinstance(auth,dict):
            if not auth.has_key('userPassword'):
                self.logger.warn("Only support 'userPassword'-attribute")
                return None
            default_auth = auth['userPassword'][:1][0]
            self.user_auth = LDIFutils.map_constants(code, default_auth[0])
            if len(default_auth) == 2:
                format = default_auth[1]                                         
            else: 
                format = None
            self.auth_format[int(self.user_auth)] = {'attr':'userPassword',
                                                     'format':format}
            for entry in auth['userPassword'][1:]:
                auth_t = LDIFutils.map_constants(code, entry[0])
                if len(entry) == 2:
                    format = entry[1]
                else:
                    format = None
                auth_meth_l.append(auth_t)
                self.auth_format[int(auth_t)] = {'attr':'userPassword',
                                                 'format':format}
        if isinstance(auth,(list,tuple)):
             self.user_auth = int(getattr(self.const,auth[:1][0]))
             for entry in auth[1:]:
                auth_meth_l.append(int(getattr(self.const,entry)))
        elif isinstance(auth,str):
            self.user_auth = int(getattr(self.const,auth))
        return auth_meth_l

    def load_auth_tab(self,auth_meth=None):
        self.auth_data = {}
        self.a_meth = self.auth_methods(auth_meth)
        if self.a_meth:
            for x in self.posuser.list_account_authentication(auth_type=self.a_meth):
                if not x['account_id'] or not x['method']:
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
        now = mx.DateTime.now()
        for row in self.posuser.list_entity_quarantines(
                            entity_types = self.const.entity_account):
            if (row['start_date'] <= now and (row['end_date'] is None
                                        or row['end_date'] >= now)
                                        and (row['disable_until'] is None
                                        or row['disable_until'] < now)):
                # The quarantine in this row is currently active.
                    self.quarantines.setdefault(int(row['entity_id']), []).append(
                                int(row['quarantine_type']))


    def user_object(self,row):
        account_id = int(row['account_id'])
        uname = row['entity_name']
        passwd = '{crypt}*Invalid'
        if row['auth_data']:
            if self.auth_format[self.user_auth]['format']:
                passwd = self.auth_format[self.user_auth]['format'] % \
                         row['auth_data']
            else:
                passwd = row['auth_data']
            passwd_attr = self.auth_format[self.user_auth]['attr']
        else:
            for uauth in [x for x in self.a_meth if self.auth_format.has_key(x)]:
            #method = int(self.const.auth_type_crypt3_des)
                try:
                    #if uauth in self.auth_format.keys():
                    if self.auth_format[uauth]['format']:
                        passwd = self.auth_format[uauth]['format'] % \
                                 self.auth_data[account_id][uauth]
                        passwd_attr = self.auth_format[uauth]['attr'] 
                    else:         
                        passwd = self.auth_data[account_id][uauth]
                            
                except KeyError:
                    pass
        if not row['shell']:
            self.logger.warn("User %s have no posix-shell!" % uname)
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
        try:
            if row['disk_id']:
                disk_path = self.disk_tab[int(row['disk_id'])]
            else:
                disk_path = None
            home = self.posuser.resolve_homedir(account_name=uname, home=row['home'],
                                                disk_path=disk_path)
        except:
            self.logger.warn("User %s has no home-directory!" % uname)
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
        """To call Mixin-class. 
        (Should consider support for multiple mixin.)
        """
        # FIXME: useless documentation string
        pass



    def filegroup_ldif(self,filename=None):
        """Generate filegroup. 
        Groups without group and expanded members from both external and
        internal groups."""
        f = LDIFutils.ldif_outfile('FILEGROUP', filename, self.fd)
        self.init_filegroup()
        if not self.spread_d.has_key('filegroup'):
            logger.warn("No spread is given for filegroup!")
        else:
            f.write(LDIFutils.container_entry_string('FILEGROUP'))
            for row in self.posgrp.search(spread=self.spread_d['filegroup'],
                                          filter_expired=False):
                dn, entry = self.filegroup_object(row)
                if dn:
                    f.write(LDIFutils.entry_string(dn, entry, False))
        LDIFutils.end_ldif_outfile('FILEGROUP', f, self.fd)
            
            
        
    def init_filegroup(self):
        """Initiate modules and constants for posixgroup"""
        from Cerebrum.modules import PosixGroup
        self.posgrp = PosixGroup.PosixGroup(self.db)
        self.fgrp_dn = LDIFutils.ldapconf('FILEGROUP', 'dn')

    def filegroup_object(self, row):
        """Create the group-entry attributes"""
        self.posgrp.clear()
        self.posgrp.find(row["group_id"])
        gname = LDIFutils.iso2utf(self.posgrp.group_name)
        if not self.id2uname.has_key(int(row["group_id"])):
            self.id2uname[int(row["group_id"])] = gname
        members = []
        entry = {'objectClass': ('top', 'posixGroup'),
                 'cn':          (gname,),
                 'gidNumber':   (str(int(self.posgrp.posix_gid)),)}
        if self.posgrp.description:
            # latin1_to_iso646_60 later
            entry['description'] = (LDIFutils.iso2utf(self.posgrp.description),)

        for member_row in self.posgrp.search_members(
                                        group_id=self.posgrp.entity_id,
                                        indirect_members=True,
                                        member_type=self.const.entity_account,
                                        member_spread=self.spread_d["user"][0]):
            uname_id = int(member_row["member_id"])
            if not self.id2uname.has_key(uname_id) or self.get_name:
                # Have find a way to resolve this problem later
                # Change this to .warn when various _list() functions do
                # not list expired accounts.
                self.logger.info("Could not resolve name on account-id: %s",
                                 uname_id)
                continue
            members.append(self.id2uname[uname_id])
        # There may be duplicates in the resulting sequence
        entry['memberUid'] = list(set(members))
        self.update_filegroup_entry(entry, row)
        dn = ','.join((('cn=' + gname), self.fgrp_dn))
        return dn,entry

    def update_filegroup_entry(self, entry, row):
        """Future use of mixin-classes"""
        pass


    def netgroup_ldif(self, filename=None):
        """Generate netgroup with only users."""
        f = LDIFutils.ldif_outfile('NETGROUP', filename, self.fd)
        self.init_netgroup()
        if not self.spread_d.has_key('netgroup'):
            self.logger.warn("No valid netgroup-spread in cereconf or arg!")
        else:
            f.write(LDIFutils.container_entry_string('NETGROUP'))
            for row in self.grp.search(spread=self.spread_d['netgroup'],
                                       filter_expired=False):
                dn, entry = self.netgroup_object(row)
                if dn:
                    f.write(LDIFutils.entry_string(dn, entry, False))
        LDIFutils.end_ldif_outfile('NETGROUP', f, self.fd)
        
        
    def init_netgroup(self):
        """Initiate modules and constants."""
        self.ngrp_dn = LDIFutils.ldapconf('NETGROUP', 'dn')
        self.grp = Factory.get('Group')(self.db)
        
    def netgroup_object(self, row):
        """Generate netgroup objects."""
        self._gmemb = {}
        self.grp.clear()
        group_id = int(row['group_id'])
        self.grp.find(group_id)
        netgrp_name = LDIFutils.iso2utf(self.grp.group_name)
        entry = {'objectClass':       ('top', 'nisNetGroup'),
                 'cn':                (netgrp_name,),
                 'nisNetgroupTriple': [],
                 'memberNisNetgroup': []}
        if not self.id2uname.has_key(group_id):
            self.id2uname[group_id] = netgrp_name
        if self.grp.description:
            entry['description'] = (
                latin1_to_iso646_60(self.grp.description).rstrip(),)
        self.get_netgrp(entry['nisNetgroupTriple'], entry['memberNisNetgroup'])
        dn = ','.join((('cn=' + netgrp_name), self.ngrp_dn))
        return dn, entry


    def get_netgrp(self, triples, memgrp):
        """Recursive method to get members and groups in netgroup."""
        for row in self.grp.search_members(group_id=self.grp.entity_id,
                                         member_spread=self.spread_d["user"][0],
                                         member_type=self.const.entity_account):
            if self.get_name:
                uname_id, uname = (int(row["member_id"]),
                                   self.entity2name[int(row["member_id"])])
            else:
                uname_id = int(row["member_id"])
                try:
                    uname = self.id2uname[uname_id]
                except:
                    self.logger.warn("Cache enabled but user id=%s not found",
                                     uname_id)
                    continue
        
            if uname_id in self._gmemb or "_" in uname:
                continue
            triples.append("(,%s,)" % uname)
            self._gmemb[uname_id] = True

        for row in self.grp.search_members(group_id=self.grp.entity_id,
                                           member_type=self.const.entity_group):
            self.grp.clear()
            self.grp.entity_id = int(row["member_id"])
            if filter(self.grp.has_spread, self.spread_d['netgroup']):
                name = self.entity2name[int(row["member_id"])]
                memgrp.append(LDIFutils.iso2utf(name))
            else:
                self.get_netgrp(triples, memgrp)


class PosixLDIFRadius(PosixLDIF):
    """General mixin for Radius type attributes."""

    def auth_methods(self, auth_meth= None):
	# Also fetch NT password, for attribute sambaNTPassword.
	meth = self.__super.auth_methods(auth_meth)
	meth.append(int(self.const.auth_type_md4_nt))
	return meth

    def update_user_entry(self, account_id, entry, row):
        # sambaNTPassword (used by FreeRadius)
        try:
            hash = self.auth_data[account_id][int(self.const.auth_type_md4_nt)]
        except KeyError:
            pass
        else:
            skip = False
            if self.quarantines.has_key(account_id):
                qh = QuarantineHandler(self.db, self.quarantines[account_id])
                if qh.should_skip() or qh.is_locked():
                    skip = True
            if not skip:
                entry['sambaNTPassword'] = (hash,)
                # TODO: Remove sambaSamAccount and sambaSID after Radius-testing
                entry['objectClass'].append('sambaSamAccount')
                entry['sambaSID'] = entry['uidNumber']
                added = True
        return self.__super.update_user_entry(account_id,entry, row)
