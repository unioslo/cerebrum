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
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.no.uit import Email

#from Cerebrum.modules import ADAccount
#from Cerebrum.modules import ADObject



max_nmbr_users = 20000
logger_name = cereconf.DEFAULT_LOGGER_TARGET
logger = Factory.get_logger('console')

default_user_file = cereconf.OMNI_DEFAULT_USER_FILE
default_group_file = cereconf.OMNI_DEFAULT_GROUP_FILE


class ad_export:

    def __init__(self, userfile,groupfile):
        self.userfile = userfile
        self.groupfile = groupfile        
        self.userlist = {}
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ent_name = Entity.EntityName(self.db)
        self.group = Factory.get('Group')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.posixuser = pu = PosixUser.PosixUser(self.db)
        self.dont_touch_filter = ['users']

        logger.info("Start caching of names")
        self.name_cache = self.person.getdict_persons_names( name_types=(self.co.name_first,self.co.name_last,self.co.name_work_title))
        logger.info("Start caching of names done")

    def get_group(self,id):
        gr = PosixGroup.PosixGroup(self.db)
        if isinstance(id, int):
            gr.find(id)
        else:
            gr.find_by_name(id)
        return gr

    def calculate_homepath(self,username):
        server = cereconf.OMNI_FILESERVER
        path = "\\\\%s\\%s" % (server,username)
        return path

    def calculate_profilepath(self,username):
        server = cereconf.OMNI_FILESERVER
        profile_share = "profiles"
        path = "\\\\%s\\%s\\%s\\%s\\%s" % (server,profile_share,username[:1],username[:2],username)
        return path
    
    def calculate_tsprofilepath(self,username):
        server = cereconf.OMNI_FILESERVER
        profile_share = "ts_profiles"
        path = "\\\\%s\\%s\\%s\\%s\\%s" % (server,profile_share,username[:1],username[:2],username)
        return path
 
    def build_export(self,type):

        logger.info("Dispatch retreivers for %s info..." % (type))
        count = 0
        if type in ['user','adminuser']:
            self.build_user_export(type)
        elif type in ['group','admingroup']:
            self.build_group_export(type)
        else:
            logger.critical("invalid buildtype to build_export: %s" % (type))
            sys.exit(1)


    def build_user_export(self,type):

        #retreive info from cerebrum
        logger.info("Retreiving %s info..." % (type))
        count = 0
        for uname in self.userlist[type]:
            count +=1
            if (count%500 == 0):
                logger.info("Processed %d accounts" % count)
            entry = self.userlist[type][uname]
            acc_id = entry['entity_id']
            ad_ou = entry['ou']
            try:
                self.posixuser.clear()
                self.posixuser.find(acc_id)
            except Errors.NotFoundError:
                logger.error("User %s not a posixuser, skipping" % (uname))
                continue

            expire_date = self.posixuser.expire_date.Format('%Y-%m-%d')
            try:
                email = self.posixuser.get_primary_mailaddress()
            except Errors.NotFoundError,m:
                logger.warn("Failed to get primary email for %s" % (self.posixuser.account_name))
                email = ""
            posix_uid = self.posixuser.posix_uid
            posix_gid = self.posixuser.gid_id
            homedrive = cereconf.OMNI_HOME_DRIVE
            homepath = self.calculate_homepath(uname)
            profilepath = self.calculate_profilepath(uname)
            tsprofilepath = self.calculate_tsprofilepath(uname)

            namelist = self.name_cache.get(self.posixuser.owner_id,None)
            if namelist:
                first_name = namelist.get(int(self.co.name_first),"")
                last_name = namelist.get(int(self.co.name_last),"")
                worktitle = namelist.get(int(self.co.name_work_title),"")
            else:
                # fall back to username
                logger.debug("No names in cache for account=%s, owner=%s :%s" %\
                    (self.posixuser.account_name,self.posixuser.owner_id,namelist))
                last_name = uname
                first_name = worktitle = ""               

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
            entry['cant_change_password'] = cereconf.OMNI_CANT_CHANGE_PW
            entry['posixuid'] = posix_uid
            entry['posixgid'] = posix_gid
            entry['ou'] = ad_ou


    def build_group_export(self,type):

        logger.info("Retreiving %s info..." % (type))
        count = 0
        dellist = []
        for gname in self.userlist[type]:
            if gname in self.dont_touch_filter:
                logger.error("Reserved AD group name '%s', skip" % (gname))
                dellist.append((type,gname))
                continue
            entry = self.userlist[type][gname]
            gid = entry['entity_id']
            try:
                gr = self.get_group(entry['entity_id'])
            except AttributeError:                
                logger.error("Group %s is not a posix group!")
                dellist.append((type,gname))
                continue
            except Errors.NotFoundError:
                dellist.append((type,gname))
                logger.error("Group %s (id=%s) not found, not a posixgroup?" % (gname,gid))
                continue
            count +=1
            if (count%500 == 0):
                logger.info("Processed %d %s" % (count,type))
            ou = entry['ou']
            logger.info("Get %s info: %s -> %s:: %s" % (type,gid,ou,gr.group_name))
            member_tuple_list = gr.get_members(get_entity_name=True)
            members=[]
            for item in member_tuple_list:
                members.append(item[1])
            memberstr = ','.join(members)
            entry['description']= gr.description
            entry['members']=memberstr
            entry['posixgid']=str(gr.posix_gid)

        for delitem in dellist:
            type,gname = delitem
            del(self.userlist[type][gname])
            

    def write_export(self):

        try:
            user_fh = open(self.userfile,'w+')
        except IOError,m:
            logger.critical("Cannot create userfile %s" % (self.userfile))
            sys.exit(1)

        try:
            group_fh = open(self.groupfile,'w+')
        except IOError,m:
            logger.critical("Cannot create groupfile %s" % (self.groupfile))
            sys.exit(1)

        topkeys = self.userlist.keys()
        for type in topkeys:
            if type in ['user','adminuser']:
                fileobj = user_fh
            elif type in ['group','admingroup']:
                fileobj = group_fh
            myUserlist = self.userlist[type]
            line = None
            keys = myUserlist.keys()
            keys.sort()            
            for name in keys:
                entry = myUserlist[name]
                try:
                  if type in ['user','adminuser']:
                      values = [ name,
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
                               str(entry['ou']),
                               ]
                  elif type in ['group','admingroup']:
                      values = [name,
                              entry['description'],
                              entry['members'],
                              entry['posixgid'],
                              entry['ou']
                              ]
                except KeyError:
                   logger.error("Person without posix user detected!")
                   continue                

                try:
                    line = ";".join(values)
                except Exception,m:
                    logger.error("Failed to write: type=%s, values=%s, reason: %s" % (type,values,m))
                fileobj.write("%s%s" % (line,'\r\n')) # want a dos crlf !

        user_fh.close()
        group_fh.close()
        
    def get_objects(self,entity_type):
        #Get all objects with spread ad, in a hash identified 
        #by name with the cerebrum id and ou.
        global max_nmbr_users
        grp_postfix = ''
        logger.info("Start retrival of %s objects from Cerebrum" % (entity_type))
        if entity_type == 'user':
            namespace = int(self.co.account_namespace)
            spreadlist = [int(self.co.spread_uit_fd)]
            cbou = cereconf.OMNI_USEROU
        elif entity_type=='adminuser':
            namespace = int(self.co.account_namespace)
            spreadlist = [int(self.co.spread_uit_ad_lit_admin)]
            cbou = cereconf.OMNI_ADMINOU
        elif entity_type=='group':
            namespace = int(self.co.group_namespace)
            spreadlist = [int(self.co.spread_uit_ad_group)]
            cbou = cereconf.OMNI_GROUPOU
        elif entity_type=='admingroup':
            namespace = int(self.co.group_namespace)
            spreadlist = [int(self.co.spread_uit_ad_lit_admingroup)]
            cbou = cereconf.OMNI_ADMINOU
        else:
            logger.error("Invalid type to get_objects(): %s" % (entity_type))
            sys.exit(1)
            
        ulist = {}
        count = 0

        for spread in spreadlist:
            for row in self.ent_name.list_all_with_spread(spread):
                count = count+1
                if count > max_nmbr_users: break
                self.ent_name.clear()
                self.ent_name.find(row['entity_id'])
                name = self.ent_name.get_name(namespace)
                if entity_type == 'user':
                    #logger.debug("Retreived id %d from spread list" % (row['entity_id']))
                    ulist[name]={'entity_id': int(row['entity_id']), 'ou': cbou}   
                elif entity_type == 'adminuser':
                    #logger.debug("Retreived id %d from spread list" % (row['entity_id']))
                    ulist[name]={'entity_id': int(row['entity_id']), 'ou': cbou}   
                elif entity_type=='group':
                    ulist['%s%s' % (name,cereconf.OMNI_GROUP_POSTFIX)]={ 'entity_id': int(row['entity_id']), 'ou': cbou}
                elif entity_type=='admingroup':
                    if name.startswith('role:'):
                        name=name[5:]
                    ulist['%s%s' % (name,cereconf.OMNI_GROUP_POSTFIX)]={ 'entity_id': int(row['entity_id']), 'ou': cbou}
                else:
                    logger.critical("Unknown type in get_objects(): %s" % (entity_type))
                    sys.exit(1)
        logger.info("Found %s %s objects in Cerebrum" % (count,entity_type))
        self.userlist[entity_type] = ulist
        return



def usage(exitcode=0):
    print """Usage: [options]
    -h | --help show this message
    -u | --user_file : filename to write userinfo to
    -g | --group_file: filename to write groupinfo to
    -w | --what:  one or more of these: admin,adminuser,group and admingroup
    """
    sys.exit(exitcode)



def main():
    global default_user_file
    global default_group_file

    what = 'user,adminuser,group,admingroup'    
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'u:g:w:h',
                                   ['user_file=', 'group_file=', 'what=','help'])
    except getopt.GetoptError:
        usage(1)
    disk_spread = None
    outfile = None
    for opt, val in opts:
        if opt in ['-u', '--user_file']:
            default_user_file = val
        elif opt in ['-g', '--group_file']:
            default_group_file = val
        elif opt in ['-h', '--help']:
            usage(0)
        elif opt in ['-w', '--what']:
            what=val

    what = what.split(',')
    worker = ad_export(default_user_file,default_group_file)
    for item in what:
        worker.get_objects(item)
        worker.build_export(item)

    worker.write_export()


if __name__ == '__main__':
    main()
