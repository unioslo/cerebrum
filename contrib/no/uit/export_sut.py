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
        
    if ((sut_file != 0) and (help ==0)):
        #logger.info("Starting SUT export")        
        retval = export_sut(sut_file)
        #logger.info("SUT export finished, processed %i students" % retval)

        
def usage():
    print """This program reads a stillingskode file and inserts the data
    into the person_stillingskode table in cerebrum

    Usage: [options]
    -s | --sut-file : stillingskode file
    -h | --help : this text """


if __name__ == '__main__':
    main()

# arch-tag: aefeea42-b426-11da-9867-a1e6d2eba8de
