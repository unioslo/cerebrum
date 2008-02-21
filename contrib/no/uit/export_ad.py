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
## Create a export file from Cerebrum to be imported into our Ansatte Active Directory.
##
## Fileformat:
## userid;ou;Firstname;lastname;title;department;email;expire;acc_disabled;can_change_pass;sko
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
## sko = Stedkode where person is employed

ITEMLIST = ('userid','name_first','name_last', 'title','sko','skoname',
            'company','expire','acc_disabled')

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

max_nmbr_users = 10000
logger_name = cereconf.DEFAULT_LOGGER_TARGET
logger = Factory.get_logger(logger_name)
        
default_user_file = cereconf.AD['DEFAULT_USER_FILE']
default_group_file = cereconf.AD['DEFAULT_GROUP_FILE']


class ad_export:

    def __init__(self, userfile,groupfile):
        self.userfile = userfile
        self.groupfile = groupfile        
        self.userlist = {}
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ent_name = Entity.EntityName(self.db)
        self.ent_sprd = Entity.EntitySpread(self.db)
        self.group = Factory.get('Group')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.posixuser = pu = PosixUser.PosixUser(self.db)


        self.dont_touch_filter = ['users']
        self.OU2name = dict()

        logger.info("Start caching of names")
        self.name_cache = self.person.getdict_persons_names( name_types=(self.co.name_first,self.co.name_last,self.co.name_work_title))
        logger.info("Finished caching of names done")
        logger.info("Start caching of OU id's to SKO's")
        self.OU2Stedkodemap = self.make_ou_to_stedkode_map(self.db)
        logger.info("Finished caching of OU id's to SKO's")

        
    def make_ou_to_stedkode_map(self,db):
        """
        Returns a dictionary mapping ou_ids to (fak,inst,avd) triplets
        (stedkoder).
        """

        ou = Factory.get("OU")(db)
        result = dict()
    
        for row in ou.get_stedkoder():
            result[int(row["ou_id"])] = ("%02d%02d%02d" % ( int(row["fakultet"]),
                                                        int(row["institutt"]),
                                                        int(row["avdeling"])))
            ou.clear()
            ou.find(int(int(row["ou_id"])))
            self.OU2name[int(row["ou_id"])] =   ou.display_name

        logger.debug("%d ou -> stedkode mappings", len(result))
        return result

    def write_steder(self,stedfile):
        
        koder = {}
        for ou in self.OU2Stedkodemap:
            koder[self.OU2Stedkodemap[ou]] = self.OU2name[ou]
            
        sorted = koder.keys()
        sorted.sort()
        try:
            fh = open(stedfile,'w+')
        except IOError,m:
            print "Cannot create userfile %s" % (stedfile)
            sys.exit(1)
        for i in sorted:
            fh.write("%s;%s\n" % (i,koder[i]))
        fh.close()
        
        
    def get_group(self,id):
        gr = PosixGroup.PosixGroup(self.db)
        if isinstance(id, int):
            gr.find(id)
        else:
            gr.find_by_name(id)
        return gr

    def calculate_homepath(self,username):
        server = cereconf.AD['FILESERVER']
        path = "\\\\%s\\%s" % (server,username)
        return path

    def calculate_profilepath(self,username):
        server = cereconf.AD['FILESERVER']
        profile_share = "allprofs"
        path = "\\\\%s\\%s\\%s" % (server,profile_share,username)
        return path
    
    def calculate_tsprofilepath(self,username):
        server = cereconf.AD['FILESERVER']
        profile_share = "allprofs"
        path = "\\\\%s\\%s\\%smf" % (server,profile_share,username)
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
        dellist = []
        for uname in self.userlist[type]:
            count +=1
            if (count%500 == 0):
                logger.info("Processed %d accounts" % count)
            entry = self.userlist[type][uname]
            acc_id = entry['entity_id']
            ad_ou = entry['ou']
            self.account.clear()
            try:
                self.account.find(acc_id)
            except Errors.NotFoundError:
                logger.error("User %s not a posixuser, skipping from Active Dir export" % (uname))
                dellist.append(uname)
                continue

            if self.account.is_expired():
                dellist.append(uname)                
                continue

            expire_date = self.account.expire_date.Format('%Y-%m-%d')
            try:
                email = self.account.get_primary_mailaddress()
            except Errors.NotFoundError,m:
                logger.warn("Failed to get primary email for %s" % (self.account.account_name))
                email = ""
            homedrive = cereconf.AD.get('HOME_DRIVE')
            homepath = self.calculate_homepath(uname)
            profilepath = self.calculate_profilepath(uname)
            tsprofilepath = self.calculate_tsprofilepath(uname)

#            acc_affs = 
            sko = '000000'
            skoname='Unknown'
            for aff in self.account.get_account_types(filter_expired=False):
                if aff['affiliation'] == int(self.co.affiliation_student):
                    logger.info("skipping student aff for %s" % (uname,))
                    continue
                else:
                    try:
                        sko = self.OU2Stedkodemap[aff['ou_id']]
                        skoname=self.OU2name[aff['ou_id']]
                    except KeyError:
                        logger.warn("Affiliation skipped for: %s. Invalid OU: %s (Is person affiliation on OU not deleted because of grace?)" % (uname, aff['ou_id']))
                        continue
                    break            
            logger.debug("Aff sko exported is %s %s" % (sko,skoname))                           
#            if len(acc_affs)>0:
#                sko = self.OU2Stedkodemap[acc_affs[0]['ou_id']]
#                skoname=self.OU2name[acc_affs[0]['ou_id']]

            
            namelist = self.name_cache.get(self.account.owner_id)
            #print "Namecache for account=%s, owner=%s :%s" % (self.posixuser.account_name,self.posixuser.owner_id,namelist)
            first_name = namelist.get(int(self.co.name_first))
            last_name = namelist.get(int(self.co.name_last))
            worktitle = namelist.get(int(self.co.name_work_title))
            if not worktitle:
                worktitle=""
            #print "WorkTitle: %s, %d" % (self.co.name_work_title,int(self.co.name_work_title))
            #print "names for for account=%s, owner=%s:: first=%s, last=%s, title=%s" % (self.posixuser.account_name,self.posixuser.owner_id,
            #                                                                             first_name,last_name,worktitle)

            # Check quarantines, and set to True if exists
            qu = self.account.get_entity_quarantine()
            if (qu):
                acc_disabled=1
            else:
                acc_disabled=0
            
            # hardcode until we get an updated stedkoder with correct names

            # Got all info... Build final dict for user
            entry['userid'] = self.account.account_name
            entry['name_first'] = first_name
            entry['name_last'] = last_name            
            entry['title'] = worktitle
            entry['ou'] = ad_ou
            entry['sko'] = sko
            entry['company'] = "UiT"
            entry['skoname'] = skoname
            entry['email'] = email            
            entry['expire'] = expire_date
            entry['homepath'] = homepath
            entry['homedrive'] = homedrive
            entry['profilepath'] = profilepath
            entry['tsprofilepath'] = tsprofilepath
            entry['acc_disabled'] = acc_disabled
            entry['cant_change_password'] = cereconf.AD_CANT_CHANGE_PW

        for delitem in dellist:
            del(self.userlist[type][delitem])



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
            print "Cannot create userfile %s" % (self.userfile)
            sys.exit(1)

        try:
            group_fh = open(self.groupfile,'w+')
        except IOError,m:
            print "Cannot create groupfile %s" % (self.groupfile)
            sys.exit(1)

        topkeys = self.userlist.keys()
        for type in topkeys:
            if type in ['user','adminuser']:
                fileobj = user_fh
                #write headers
                fileobj.write("#%s%s" % (';'.join(["%s" % x for x in ITEMLIST]),'\r\n')) # want a dos crlf !
            elif type in ['group','admingroup']:
                fileobj = group_fh
            myUserlist = self.userlist[type]
            line = None
            keys = myUserlist.keys()
            keys.sort()            
            for name in keys:
                entry = myUserlist[name]
                if type in ['user','adminuser']:
                    values=[]
                    for i in ITEMLIST:
                        values.append(str(entry[i]))
                        
                elif type in ['group','admingroup']:
                    values = [name,
                              entry['description'],
                              entry['members'],
                              entry['posixgid'],
                              entry['ou']
                              ]
                line = ";".join(values)
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
            spreadlist = [int(self.co.spread_uit_ad_account )]
            cbou = cereconf.AD['USEROU']
        elif entity_type=='adminuser':
            namespace = int(self.co.account_namespace)
            spreadlist = [int(self.co.spread_uit_ad_lit_admin)]
            cbou = cereconf.AD['ADMINOU']
        elif entity_type=='group':
            namespace = int(self.co.group_namespace)
            spreadlist = [int(self.co.spread_uit_ad_group)]
            cbou = cereconf.AD['GROUPOU']
        elif entity_type=='admingroup':
            namespace = int(self.co.group_namespace)
            spreadlist = [int(self.co.spread_uit_ad_lit_admingroup)]
            cbou = cereconf.AD['ADMINOU']
        else:
            logger.error("Invalid type to get_objects(): %s" % (entity_type))
            sys.exit(1)
            
        ulist = {}
        count = 0
        pattern = re.compile('^[a-z]{3}[0-9]{3}$')

        for spread in spreadlist:
            for row in self.ent_sprd.list_all_with_spread(spread):
                count = count+1
                if count > max_nmbr_users: break
                self.ent_name.clear()
                self.ent_name.find(row['entity_id'])
                name = self.ent_name.get_name(namespace)
                if entity_type == 'user':
                    if pattern.match(name):                    
                        ulist[name]={'entity_id': int(row['entity_id']), 
                                     'ou': cbou}   
                    else:
                        logger.error("User %s has spread %s, but name is in wrong format" % (name, spread))
                elif entity_type == 'adminuser':
                    #logger.debug("Retreived id %d from spread list" % (row['entity_id']))
                    ulist[name]={'entity_id': int(row['entity_id']), 'ou': cbou}   
                elif entity_type=='group':
                    ulist['%s%s' % (name,cereconf.AD_GROUP_POSTFIX)]={ 'entity_id': int(row['entity_id']), 'ou': cbou}
                elif entity_type=='admingroup':
                    if name.startswith('role:'):
                        name=name[5:]
                    ulist['%s%s' % (name,cereconf.AD_GROUP_POSTFIX)]={ 'entity_id': int(row['entity_id']), 'ou': cbou}
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
    -l | --logger_name: logger target
    -w | --what:  one or more of these: user,adminuser,group and admingroup
    --disk_spread spread (not used)
    """
    sys.exit(exitcode)



def main():
    global default_user_file
    global default_group_file
    
    sted_file = None

    #what = 'user,adminuser,group,admingroup'
    what = 'user,group'    
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'u:g:w:s:h',
                                   ['disk_spread=','user_file=', 'group_file=','what=','help'])
    except getopt.GetoptError:
        usage(1)
    disk_spread = None
    outfile = None
    for opt, val in opts:
        if opt in ['-u', '--user_file']:
            default_user_file = val
        elif opt in ['-g', '--group_file']:
            default_group_file = val
        elif opt in ['-s','--sted-file']:
            sted_file = val        
        elif opt in ['-h', '--help']:
            usage(0)
        elif opt in ['-w', '--what']:
            what=val
        


    what = what.split(',')
    worker = ad_export(default_user_file,default_group_file)
    if sted_file:
        worker.write_steder(sted_file)
        sys.exit()
    
    

    for item in what:
        worker.get_objects(item)
        worker.build_export(item)
    worker.write_export()
    


if __name__ == '__main__':
    main()
