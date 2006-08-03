#!/usr/bin/python
# -*- coding: iso8859-1 -*-
#
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
This script is a UiT specific export script for exporting data to our 
SUT system.
The data is written to a file given from command line on the following
format:
fodtdato,pnr,name,username

"""


"""
New format as of july 2006
shoud be of unix passwd format
update: 20060721: crypt should be in md5 

uid:crypt:uid:gid:gecos:home:shell
eks:
paalde:xySfdaS3aS2:500:500:Paal D. Ekran:/its/home/p/pa/paalde:/bin/bash

"""

import sys
import time
import re
import getopt


import cerebrum_path
import cereconf
#import adutils
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser


logger_name = cereconf.DEFAULT_LOGGER_TARGET


class export:

    def __init__(self):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ent_name = Entity.EntityName(self.db)
        self.group = Factory.get('Group')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.pu = PosixUser.PosixUser(self.db)
        self.logger = Factory.get_logger("console")
        self.spread_list = [self.co.spread_uit_sut_user, self.co.spread_uit_ad_account]
        self.sut_spread = self.co.spread_uit_sut_user
        self.db.cl_init(change_program='export_sut')
        self.intExpired = 0
        self.intQuarantined = 0

    def get_entities(self):
        e_list = []
        e_list = self.ent_name.list_all_with_spread(self.sut_spread)

        # lets remove any account entities which has active quarantines.
        for element in e_list:
            quarantine=''
            self.account.clear()
            self.account.find(element['entity_id'])
            quarantine = self.account.get_entity_quarantine(only_active=True)
            if(len(quarantine)!=0):
                self.logger.info("%s has quarantine set. removed from sut export" % element['entity_id'])
                self.intQuarantined +=1
                e_list.remove(element)

        # return the resulting list.
        return e_list


    def build_sut_export(self,sut_entities):

        sut_data = {}
        for item in sut_entities:
            en_id = item['entity_id']
            self.pu.clear()
            try:
                #print "Finding %d" % (en_id)
                self.pu.find(en_id)
                if self.pu.is_expired():
                    self.logger.info("Account %s (acc_id=%d) is expired!" % (self.pu.account_name,en_id))
                    self.intExpired += 1
                    continue
                else:
                    username = self.pu.account_name
                    crypt = self.pu.get_account_authentication(self.co.auth_type_md5_crypt)
                    uid = self.pu.posix_uid
                    gid = self.pu.posix_uid # uit policy
                    gecos = self.pu.get_gecos()
                    #home = self.pu.get_posix_home(self.sut_spread)  # sut_spread has wrong home set!! check process_students!
                    home = "/its/home/%s/%s/%s" % (self.pu.account_name[:1], self.pu.account_name[:2],self.pu.account_name)
                    shell = '/bin/bash'   ### fetch from CB!!
            except Errors.NotFoundError,m:
                self.logger.error("Entity_ID %s has SUT spread, but is not a POSIX account: %s!" % (item,m))
                continue

            # write a dict
            line = "%s:%s:%s:%s:%s:%s:%s" % (username,crypt,uid,gid,gecos,home,shell)
            sut_data[uid] = line
            
        return sut_data

    
    def write_export(self,sut_file,data):

        try:
            fh = open(sut_file,'w')
        except Exception,m:
            self.logger.critical("Failed to open SUT export file='%s' for writing. Error was %s" % (sut_file,m))
            sys.exit(1)
        self.logger.info("SUT export: Start writing export file")
        keys = data.keys()
        keys.sort()
        for k in keys:
            line = data[k]
            fh.write("%s\n" % line)   
        fh.close()
        self.logger.info("SUT export finished, wrote %d accounts to file,Not exported: %d (expired: %d, quarantined:%d)" % (len(keys),
                                                                                                                            self.intExpired+self.intQuarantined,self.intExpired,self.intQuarantined))


def main():

    global logger
    global logger_name

    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:l:h',['sut-file=','logger-name', 'help'])
    except getopt.GetoptError:
        usage()

    sut_file = 0
    help = 0
    for opt,val in opts:
        if opt in ('-s','--sut-file'):
            sut_file = val
        if opt in ('-l','--logger-name'):
            logger_name = val
        if opt in('-h','--help'):
            help = 1


    logger = Factory.get_logger(logger_name)


    if (help == 1 or sut_file==0):
        usage()
        sys.exit(2)
        
#    if ((sut_file != 0) and (help ==0)):
        #logger.info("Starting SUT export")        
        #retval = export_sut(sut_file)
        #logger.info("SUT export finished, processed %i students" % retval)

    if ((sut_file != 0) and (help ==0)):
        sut = export()
        sut_entities = sut.get_entities()
        export_data = sut.build_sut_export(sut_entities)
        sut.write_export(sut_file,export_data)
        


        


        
def usage():
    print """This program exports SUT account to a file
    Data should be copied to the SUT servers for distributuion.

    Usage: [options]
    -s | --sut-file : export file
    -l | --logger-name : name of logger target
    -h | --help : this text """


if __name__ == '__main__':
    main()

# arch-tag: aefeea42-b426-11da-9867-a1e6d2eba8de
