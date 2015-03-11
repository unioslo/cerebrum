#! /usr/bin/env python
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

import cerebrum_path
import cereconf
import sys
import getopt
import datetime
from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum.modules.no.uit import DiskQuota
from Cerebrum import Errors

class sut:

    def __init__(self,user,service,host):
        self.db = Factory.get('Database')()
        self.account = Factory.get('Account')(self.db)
        self.constants = Factory.get('Constants')(self.db)
        self.db.cl_init(change_program='disk_quota')
        self.logger = Factory.get_logger("cronjob")
        self.today = datetime.datetime.now() 
        self.quarantine_date= "%s" % self.today.date()
        self.account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.default_creator_id = self.account.entity_id
 
        #self.sut_db = Factory.get('Database')(user=user,service=service,host=host,DB_driver='PsycoPG')
        self.sut_db = Database.connect(user=user,service=service,host=host,DB_driver='PsycoPG')

    def get_quota(self):
        #get disk quota from sut database.
        #return username,disk_usage

        db_row = self.sut_db.query("select username,usage from disc_usage")
        for row in db_row:
            #These SUT users have used too much disk_quota. qurantine account.
            self.account.clear()
            try:
                self.account.find_by_name(row['username'])
                quarantines=''
                quarantines = self.account.get_entity_quarantine(qtype=self.constants.quarantine_sut_disk_usage)
                if len(quarantines==0):
                    self.account.add_entity_quarantine(self.constants.quarantine_sut_disk_usage,self.default_creator_id,start=self.quarantine_date)
                #print "row=%s" % row
            except:
                self.logger.warn("unable to set disk quarantine for user %s in BAS." % (row['username']))
                
        self.db.commit()
    
    
def main():
    logger_name = cereconf.DEFAULT_LOGGER_TARGET

    try:
        opts,args = getopt.getopt(sys.argv[1:],'d:D:h:',['db-user','db-service','host'])
    except getopt.GetoptError:
        usage()
    
    user = None
    service = None
    host = None
    for opt,val in opts:
        if opt in('-d','--db-user'):
            user = val
        if opt in('-D','--db-service'):
            service = val
        if opt in('-h','--host'):
            host = val
    system = sut(user,service,host)
    system.get_quota()
    

def usage():

    print """
    python disk_quota.py -h <host> -d <database> -p <password>

    The script reads disk quota from an (external?) database and sets quarantine
    flags based on the the disk usage on each account.
    
    
    -d | --db-user      : database user
    -D | --db-service   : database name
    -h | --host         :host machine

    """

if __name__=='__main__':
    main()
