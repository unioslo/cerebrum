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
New format as of may 2006
shoud be of unix passwd format

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
import adutils
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser

def export_sut(out_file):
    db = Factory.get('Database')()
    const = Factory.get('Constants')(db)
    
    file_handle = open(out_file,"w")

    # Change these to constants!!!
    value_domain = const.account_namespace  # powq: 77
    id_type = const.externalid_fodselsnr   # powq: 96
    name_variant = const.name_full   # powq: 162
    affiliation = const.affiliation_student  # powq: 190
    sys_fs = const.system_fs
    sys_x  = const.system_x

    # Rewrite to portable query!

    query = "select distinct e.entity_name, eei.external_id, pn.name \
    FROM person_affiliation pa, entity_name e, entity_external_id eei, person_name pn, account_info a \
    WHERE e.entity_id=a.account_id AND \
          a.owner_id = eei.entity_id AND \
          pn.person_id = a.owner_id AND \
          eei.entity_id = pa.person_id AND \
          e.value_domain=%i AND \
          eei.id_type=%i AND \
          (eei.source_system=%i OR eei.source_system=%i) AND \
          pn.name_variant=%i AND \
          pa.affiliation=%i \
    UNION \
        SELECT e.entity_name, p.external_id, s.name \
        FROM account_info ai, entity_name e, entity_external_id p, person_name s,entity_spread es \
        WHERE es.spread=493 \
        AND es.entity_id = e.entity_id \
        AND es.entity_id = ai.account_id \
        AND ai.owner_id = p.entity_id \
        AND ai.owner_id = s.person_id \
        AND s.name_variant=162 \
        AND s.source_system = 69 \
        AND p.id_type = 96  " % (value_domain,id_type,sys_fs,sys_x,name_variant,affiliation)
          
    #logger.debug(query)
          
    query_new = "SELECT ......"
          
    db_row = db.query(query)
    i = 0
    for row in db_row:
        full_name = row['name']
        ssn = row['external_id']
        fodt = ssn[0:6]
        pnr = ssn[6:11]
        dag = fodt[0:1]
        mnd = fodt[2:4]
        aar = fodt[4:6]

        # unfortunately we have some fake ssn. these cannot be inserted into the export
        # file to SUT. We need to convert these by issuing the following
        # any months which have the first number = 5 or 6 must be changed to 0 or 1 respectively
        try:
            if(fodt[2] == "5"):
               #logger.debug("before:%s" % (fodt))
               fodt = "%s%s%s" % (fodt[0:2],"0",fodt[3:6])
               #logger.debug("after:%s" % (fodt))
            elif(fodt[2] == "6"):
               #logger.debug("before:%s" % (fodt))
               fodt = "%s%s%s" % (fodt[0:2],"1",fodt[3:6])
               #logger.debug("after:%s" % (fodt))
        except Exception,msg:
            print "SUT ERR: db_row=%s, error:%s" %(db_row, msg)
            sys.exit(1)
            
        user_name = row['entity_name']
        
        sut_line = "%s:%s:%s:%s\n" % (fodt,pnr,full_name,user_name)
        #logger.debug(sut_line.rstrip())
        file_handle.writelines(sut_line)
        i += 1
    file_handle.close()
    #print "copying file now"
    #ret = os.system("/usr/bin/scp %s root@flam.student.uit.no:/its/apache/data/sliste.dta" % out_file)
    #self.global_ret +=ret
    #message +="   scp %s to sut %s\n" %(out_file,ret) 
    # lets write any outputs from the system command to our log file
    #for message in get.readlines():
    #    log_handle.writelines("%s\n" % message)
    return i



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
        self.sut_spread = self.co.spread_uit_sut_user
        self.db.cl_init(change_program='export_sut')

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
                e_list.remove(element)

        # return the resulting list.
        return e_list


    def build_sut_export(self,sut_entities):

        sut_data = {}
        for item in sut_entities:
            en_id = item['entity_id']
            self.pu.clear()
            try:
                print "Finding %d" % (en_id)
                self.pu.find(en_id)
                if self.pu.is_expired():
                    self.logger.info("Account %s (acc_id=%d) is expired!" % (self.pu.account_name,en_id))
                    continue
                else:
                    username = self.pu.account_name
                    crypt = self.pu.get_account_authentication(self.co.auth_type_crypt3_des) 
                    uid = self.pu.posix_uid
                    gid = self.pu.posix_uid # uit policy
                    gecos = self.pu.get_gecos()
                    home = self.pu.get_posix_home(self.sut_spread)
                    shell = '/bin/bash'
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
        self.logger.info("SUT export finished, wrote %d accounts to file" % (len(keys)))


def main():

    global logger
    #logger = Factory.get_logger("console")
    logger = Factory.get_logger("cronjob")
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:h',['sut-file=','help'])
    except getopt.GetoptError:
        usage()

    sut_file = 0
    help = 0
    for opt,val in opts:
        if opt in ('-s','--sut-file'):
            sut_file = val
        if opt in('-h','--help'):
            help = 1


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
    -h | --help : this text """


if __name__ == '__main__':
    main()

# arch-tag: aefeea42-b426-11da-9867-a1e6d2eba8de
