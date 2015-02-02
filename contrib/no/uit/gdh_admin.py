#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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


#
# This file generetes the neccesary default groups that we need in cerebrum.
# Script should be run prior to populating cerebrum for the first time
#

import string
import sys
import getopt
import os.path
import cerebrum_path
import exceptions
import time

from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixGroup



class worker:
    
    def __init__(self):
        # lets initialize some objects
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='gdh_admin')
        self.account = Factory.get('Account')(self.db)
        self.const = Factory.get('Constants')(self.db)
        

    def groupCreate(self,newgroup,newgroup_desc,posix):
        
        visibility = self.const.group_visibility_all
        self.account.find_by_name('bootstrap_account')
        creator = self.account.entity_id
#        print "group.new(db, %s, %s, %s, %s)" %(creator, visibility, newgroup, newgroup_desc)
        group = Factory.get('Group')(self.db)
        group.clear()
        try:
            group.find_by_name(newgroup)            
        except Exception,msg:
            group.new( creator, visibility, newgroup, description=newgroup_desc)
            print "New group %s (%s) created" % (newgroup,newgroup_desc)
        
        if posix:
            pg = PosixGroup.PosixGroup(self.db)
            pg.populate(parent=group)
            print "Group upgraded to posixgroup"
            pg.write_db()
            
        self.db.commit()
        print "Created group: '%s' (%s). Group ID = %d" % (newgroup,newgroup_desc,group.entity_id)
        return 0

    def diskCreate(self,host_id,disk_path,disk_desc):
        
        if (host_id.isdigit()):
            host_textname = host_id
            host_id = int(host_id)
        else:
            print "Got host_id as a name, finding its database id"
            host = Factory.get('Host')(self.db)
            host.clear()
            try:
                host_textname = host_id
                host.find_by_name(host_id)                
                host_id = host.entity_id
                print "Host '%s' has host_id=%d" % (host_textname,host_id)
            except Exception,msg:
                print msg
                return 2
        disk = Factory.get('Disk')(self.db)
        disk.clear()
        print "Trying to create disk with path='%s' on host_id=%d" % (disk_path,host_id)
        try:
            disk.populate(host_id,disk_path,disk_desc)
            disk.write_db()
            self.db.commit()
        except Exception,msg:
            print msg
            return 3
 
        # all ok.
        print "New disk at %s with path='%s' created. DiskID=%d" %(host_textname,disk_path,disk.entity_id)
        return 0
        
    def hostCreate(self,host_name,host_desc):
        
        host = Factory.get('Host')(self.db)
        try:
            host.populate(host_name,host_desc)
            host.write_db()
            self.db.commit()
        except Exception,msg:
            print msg
            return 4
            
        print "New host %s (%s) with HostID %d created" % (host_name,host_desc,host.entity_id)
        return 0
        
            
def usage():
    print """
    This scripts creates one of the following:
        - a new group
        - a new host in host_info table
        - a new disk in disk_info table
    
    Usage: 
        gdh_admin.py -g name --desc="groupname description" [-P] 
    or  gdh_admin.py -h name --desc="hostname description" 
    or  gdh_admin.py -d --path=/some/path --desc="disk info description" --host=hostname

    You can only give one of the -g,-h or -d parameters at one time!

    Descripton:
        -g groupname  : Creates a new group with name=groupname
            -P        : Upgrades the group to a Posix group 
        -h hostname   : Creates a new host in host_info table
        -d            : Creates a new disk in disk_info table. 
                          Requires a --host parameter with hostname or a host_id
                          Reguires a --path paramater with path location on given host
                       
        All parameters must have a --desc with a sensible description of what you are creating.
       
    """
    sys.exit(-1)
            



def main():
    
    disk = False
    host = False
    group = False 
    posix = False
    desc = ''
    path = ''
    host = ''
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'g:h:dP',['desc=','path=','host='])
    except getopt.GetoptError:
        usage()

    
    for opt,val in opts:
        print "checking opt='%s' val='%s'" % (opt,val)
        if (opt in '-d'):
            disk = True
            diskname = val
        elif (opt in '-h'):
            host = True
            hostname = val
        elif (opt in '-g'):
            group = True
            groupname = val
        elif (opt in '--desc'):
            desc = val
        elif (opt in '--path'):
            path = val
        elif (opt in '--host'):
            host_id = val
        elif (opt in '-P'):
            posix = True
            

    if (disk):
        if (host or group or path=='' or host_id == ''):
            usage()
        x = worker()
        x.diskCreate(host_id,path,desc)
    elif (host):
        if (disk or group or desc == ''):
            usage()
        x = worker()
        x.hostCreate(hostname,desc)
    elif (group):
        if (disk or host or desc == ''):
            usage()
        x = worker()
        x.groupCreate(groupname,desc,posix)
    else:
        print "No valid options given"
        usage()
    print "Finished"
        
if __name__ == "__main__":
    main()

