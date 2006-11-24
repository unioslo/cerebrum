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


import cerebrum_path
import cereconf
import string
import getopt
import sys

from Cerebrum.Utils import Factory
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
          ((eei.id_type=%i) OR (eei.id_type=%i)) AND \
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
        AND ((p.id_type = 96) OR(p.id_type=%i))  " % (value_domain,
                                                      id_type,
                                                      const.externalid_sys_x_id,
                                                      sys_fs,sys_x,
                                                      name_variant,
                                                      affiliation,
                                                      const.externalid_sys_x_id)
          
    #logger.debug(query)
          
    query_new = "SELECT ......"
          
    db_row = db.query(query)
    i = 0
    for row in db_row:
        full_name = row['name']
        ssn = row['external_id']
        if((len(ssn)!=11)and(row['id_type'==const.externalid_sys_x_id])):
            #print "foreigner"
            fodt="010170"
            pnr="%i" % (10000+int(ssn))
        else:
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



class export_new:

    def __init__(self,logger_name):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ent_name = Entity.EntityName(self.db)
        self.group = Factory.get('Group')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.pu = PosixUser.PosixUser(self.db)
        self.logger = Factory.get_logger(logger_name)
        self.sut_spread = self.co.spread_uit_sut_user
        self.db.cl_init(change_program='export_sut')
        self.intCnt = 0
        self.intRej = 0
        self.intExp = 0
        self.intQnt = 0

        self.cache = {}
             # account_id => 'userid' => bto001
             #              'birth_date => 1968-01-01
             #              'fullname' => Bjorn Torsteinsen
             #              'owner_id' => 1241  # person id thath owns bto001


    def check_account(self):
        if self.account.is_expired():
            self.intExp +=1
            self.logger.info("%s(%s) is expired. removed from sut export" % (self.account.account_name,
                                                                             self.account.entity_id ))
            return False
        quarantine = self.account.get_entity_quarantine(only_active=True)
        if(len(quarantine)!=0):
            self.intQnt += 1
            self.logger.info("%s(%s) has quarantine set. removed from sut export" % (self.account.account_name,
                                                                                     self.account.entity_id))
            return False
        return True


    def cache_info(self,acc_id):
        #self.logger.info("Appending %s" % element['entity_id'])
        self.person.clear()
        self.person.find(self.account.owner_id)
        name = self.account.get_fullname()
        pnrs = self.person.get_external_id(id_type=self.co.externalid_fodselsnr)
        pnr = 0
        if (len(pnrs)>0):
            fnr = pnrs[0]['external_id']
            pnr = fnr[-5:]
        else:
            # does not have no_birthno. Try systemX id
            pnrs = self.person.get_external_id(id_type=self.co.externalid_sys_x_id)
            if (len(pnrs)>0):
                # the resulting pnr must be 11 digits long. In the case of system-X persons
                # the pnr is a combination of birth date and cerebrums internal id
                # the internal ID in cerebrum does not neccesarry have 5 digits so the
                # next line padds the internal ID with trailing zeros to generate a 5 digit number.
                # The resulting ssn is then 11 digits long.
                pnr_len = len(pnrs[0]['external_id'])
                missing_pnr_len = 5 - pnr_len
                trailing_zeros = string.zfill("",missing_pnr_len)
                pnr="%s%s" % (pnrs[0]['external_id'],trailing_zeros)
            else:
                self.logger.error("ERROR RETRIVING external_id for %s" % (acc_id))
                sys.exit(1)
        self.cache[acc_id] = { 'userid': self.account.account_name,
                               'pnr': pnr,
                               'fullname': name,
                               'birth': self.person.birth_date.Format("%d%m%y")
                               }
                

    def get_entities(self):
        entityList = []
        e_list = []
        self.logger.info("Retriving sut spread")
        e_list = self.ent_name.list_all_with_spread(self.sut_spread)
        self.logger.info("Ready...")
        # lets remove any account entities which has active quarantines.
        for element in e_list:
            self.intCnt += 1
            self.account.clear()
            self.account.find(element['entity_id'])
            if (self.check_account()):
                self.cache_info(element['entity_id'])
                entityList.append(element['entity_id'])
                              
        a_list = []
        self.logger.info("Retriving ad_account spread")
        a_list = self.ent_name.list_all_with_spread(self.co.spread_uit_ad_account)
        self.logger.info("Ready...")
        for element in a_list:
            if (element['entity_id'] not in entityList):
                self.intCnt += 1
                self.account.clear()
                try:
                    self.account.find(element['entity_id'])
                except Errors.NotFoundError:
                    self.logger.error("Unknown Account ID %d found in ad_spread!" % element['entity_id'])
                    continue
                if (self.check_account()):
                    self.cache_info(element['entity_id'])
                    entityList.append(element['entity_id'])
                    
        # return the resulting list.
        self.logger.info("Retrived %d accounts, rejected=%d, is_exp=%d, quarantined=%d" % (self.intCnt,
                                                                                           (self.intExp+self.intQnt),
                                                                                           self.intExp,
                                                                                           self.intQnt))
        return entityList


    def build_sut_exportdata(self,entityList,out_file):
        #         sut_line = "%s:%s:%s:%s\n" % (fodt,pnr,full_name,user_name)
        
        lines=[]
        for a_id in entityList:
            line = "%s:%s:%s:%s\n" % (self.cache[a_id]['birth'],
                                       self.cache[a_id]['pnr'],
                                       self.cache[a_id]['fullname'],
                                       self.cache[a_id]['userid']
                                       )
            lines.append(line)
        #print lines
        file_handle = open(out_file,"w")
        for l in lines:
            file_handle.write(l)
        file_handle.close()


def main():

    global logger
    logger_name = cereconf.DEFAULT_LOGGER_TARGET
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:l:h',['sut-file=','help','logger-name='])
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


    if (help == 1 or sut_file==0):
        usage()
        sys.exit(2)

    if ((sut_file != 0) and (help ==0)):
        #logger = Factory.get_logger(logger_name)
        #logger.info("Starting SUT export")        
        #retval = export_sut(sut_file)
        #logger.info("SUT export finished, processed %i students" % retval)

        x = export_new(logger_name)
        ents = x.get_entities()
        x.build_sut_exportdata(ents,sut_file)
        
def usage():
    print """This program creates data for export to sut.

    Usage: [options]
    -s | --sut-file : stillingskode file
    -h | --help : this text """


if __name__ == '__main__':
    main()

# arch-tag: aefeea42-b426-11da-9867-a1e6d2eba8de
