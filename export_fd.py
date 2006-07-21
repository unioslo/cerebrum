#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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


## Uit specific extension to Cerebrum
##
## Create a export file from Cerebrum to be imported into our Active Directory.
##
## Fileformat:
## userid;ou;Firstname;lastname;title;department;email;expire;acc_disabled;can_change_pass;homedrive;homepath;profilepath;tshomedrive;tsomepath;tsprofilepath;posixUid;posixGid
##
## userid = the username
## ou = OU placement in Active Dir.
## firstname = self expl
## lastname =  self expl
## title = Work title, may be empty
## dept = Name of departemen where person works,
## email = primary email addr at uit
## expire = expire date
## acc_disable = True/False : True = Account should be disabled.
## cant_change_pass = True/False: True = Account can't change pass
## homedrive = H:
## homepath = \\fileserver.uit.no\userid
## profilepath = Path where roaming profile is stored
## tsprofilepath = Path to roaming profile for Terminal Server
## posixuid = posix uid number for user
## posixgid = posix gid number for user

## assuming TS_homepath = homepath and TS_homedrive = homedrive


import sys
import time
import re
import getopt


import cerebrum_path
import cereconf
import adutils
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email

#from Cerebrum.modules import ADAccount
#from Cerebrum.modules import ADObject



max_nmbr_users = 20000



class ad_export:

    def __init__(self, outfile):
        self.outfile = outfile
        self.userlist = None
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        #ad_object = ADObject.ADObject(self.db)
        #ad_account = ADAccount.ADAccount(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ent_name = Entity.EntityName(self.db)
        self.group = Factory.get('Group')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.posixuser = pu = PosixUser.PosixUser(self.db)
        self.logger = Factory.get_logger("console")



    def calculate_homepath(self,username):
        server = cereconf.AD_FILESERVER
        path = "\\\\%s\\%s" % (server,username)
        return path

    def calculate_profilepath(self,username):
        server = cereconf.AD_FILESERVER
        profile_share = "profiles"
        path = "\\\\%s\\%s\\%s\\%s\\%s" % (server,profile_share,username[:1],username[:2],username)
        return path
    
    def calculate_tsprofilepath(self,username):
        server = cereconf.AD_FILESERVER
        profile_share = "ts_profiles"
        path = "\\\\%s\\%s\\%s\\%s\\%s" % (server,profile_share,username[:1],username[:2],username)
        return path
    



    def build_export(self,type):

        #retreive info from cerebrum

        self.logger.info("Retreiving info...")
        count = 0
        for uname in self.userlist:
            count +=1
            if (count%500 == 0):
                self.logger.info("Processed %d accounts" % count)
            entry = self.userlist[uname]
            acc_id = entry['entity_id']
            try:
                self.posixuser.clear()
                self.posixuser.find(acc_id)
            except Errors.NotFoundError:
                logger.error("User %s not a posixuser, skipping from Active Dir export" % (uname))
                continue

            self.person.clear()
            self.person.find(self.posixuser.owner_id)

            expire_date = self.posixuser.expire_date.Format('%Y-%m-%d')
            try:
                email = self.posixuser.get_primary_mailaddress()
            except Errors.NotFoundError,m:
                self.logger.error("Failed to get primary email for %s" % (self.posixuser.account_name))
                mail = ""
            posix_uid = self.posixuser.posix_uid
            posix_gid = self.posixuser.gid_id
            homedrive = cereconf.AD_HOME_DRIVE
            homepath = self.calculate_homepath(uname)
            profilepath = self.calculate_profilepath(uname)
            tsprofilepath = self.calculate_tsprofilepath(uname)

            first_name = self.person.get_name(self.co.system_cached,self.co.name_first)
            last_name = self.person.get_name(self.co.system_cached,self.co.name_last)

            try:
                worktitle = self.person.get_name(self.co.system_lt,self.co.name_work_title)
            except Errors.NotFoundError:
                worktitle = ''

            # Check quarantines, and set to True if exists
            qu = self.posixuser.get_entity_quarantine()
            if (qu):
                acc_disabled=1
            else:
                acc_disabled=0
            
            # hardcode until we get an updated stedkoder with correct names
            dept = "Uitø"


            # Got all info... Build final dict for user
            entry['name_first'] = first_name
            entry['name_last'] = last_name
            entry['title'] = worktitle
            entry['dept'] = dept
            entry['email'] = email
            entry['expire'] = expire_date
            entry['homepath'] = homepath
            entry['homedrive'] = homedrive
            entry['profilepath'] = profilepath
            entry['tsprofilepath'] = tsprofilepath
            entry['acc_disabled'] = acc_disabled
            entry['cant_change_password'] = cereconf.AD_CANT_CHANGE_PW
            entry['posixuid'] = posix_uid
            entry['posixgid'] = posix_gid



    def write_export(self):

        try:
            fh = open(self.outfile,'w+')
        except IOError,m:
            print "Cannot create %s" % (self.outfile)
            sys.exit(1)
            
        line = None
        keys = self.userlist.keys()
        keys.sort()
        for uname in keys:
            entry = self.userlist[uname]
            
            values = [ uname,
                       entry['name_first'],
                       entry['name_last'],
                       entry['title'],
                       entry['dept'],
                       entry['email'],
                       entry['expire'],
                       entry['homepath'],                       
                       entry['homedrive'],                       
                       entry['profilepath'],
                       entry['tsprofilepath'],
                       str(entry['acc_disabled']),
                       str(entry['cant_change_password']),
                       str(entry['posixuid']),
                       str(entry['posixgid']),
                       ]
            #print "values=%s" % values
            line = ";".join(values)
            #print "line=%s" % line
            fh.write("%s%s" % (line,'\n'))

        fh.close()
        
        
    def get_objects(self,entity_type):
        #Get all objects with spread ad, in a hash identified 
        #by name with the cerebrum id and ou.
        global max_nmbr_users
        grp_postfix = ''
        if entity_type == 'user':
            namespace = int(self.co.account_namespace)
            spread = int(self.co.spread_uit_fd)
        else:
            namespace = int(self.co.group_namespace)
            spread = int(self.co.spread_uit_fd)
        ulist = {}
        count = 0    
    
        for row in self.ent_name.list_all_with_spread(spread):
            count = count+1
            if count > max_nmbr_users: break
            self.ent_name.clear()
            self.ent_name.find(row['entity_id'])
            name = self.ent_name.get_name(namespace)
            if entity_type == 'user':
                cbou = '%s' % cereconf.AD_LDAP
                #self.logger.debug("Retreived id %d from spread list" % (row['entity_id']))
                ulist[name]={'entity_id': int(row['entity_id']), 'ou': cbou}   
            else:
                cbou = 'CN=Users,%s' % cereconf.AD_LDAP            
                ulist['%s%s' % (name,cereconf.AD_GROUP_POSTFIX)]=(int(row['entity_id']), cbou)
        self.logger.info("Found %s %s objects in Cerebrum" % (count,entity_type))
        self.userlist = ulist
        return



def usage(exitcode=0):
    print """Usage: [options]
    -o output file
    --disk_spread spread (mandatory)
    """
    sys.exit(exitcode)



if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:',
                                   ['disk_spread='])
    except getopt.GetoptError:
        usage(1)
    disk_spread = None
    outfile = None
    for opt, val in opts:
        if opt == '-o':
            outfile = val
        elif opt == '--disk_spread':            
            # not used at UiT
            pass
            #disk_spread = getattr(co, val)  # TODO: Need support in Util.py
            
    #    if not disk_spread:
    #       usage(1)

    if (not outfile):
        usage(1)

    worker = ad_export(outfile)
    worker.get_objects('user')
    worker.build_export('user')
    worker.write_export()

