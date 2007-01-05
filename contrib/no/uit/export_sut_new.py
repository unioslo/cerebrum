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
import time
import sys
import time
import re
import getopt
import cerebrum_path
import cereconf
#import adutils
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum.Utils import Factory

    

def main():
    logger_name = cereconf.DEFAULT_LOGGER_TARGET
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    entries = []
    

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
    if(help ==1) or (sut_file==0):
        usage()
        sys.exit(1)

    logger = Factory.get_logger(logger_name)
    file_handle = open(sut_file,"w")


    date = time.localtime()
    year=date[0]
    month=date[1]
    day=date[2]
    today="%s-%02d-%02d" %(year,month,day)

    # query = """
#     SELECT DISTINCT en.entity_name, aa.auth_data, pu.posix_uid,pn.name
#     FROM entity_name en
#     LEFT JOIN entity_quarantine eq
#     ON en.entity_id=eq.entity_id,
#     entity_spread es, account_authentication aa, posix_user pu, account_home ah, account_info ai,person_name pn
#     WHERE eq.entity_id IS NULL
#     AND es.spread=%s
#     AND es.entity_id = en.entity_id
#     AND aa.account_id=en.entity_id
#     AND aa.method=%s
#     AND pu.account_id = en.entity_id
#     AND ah.account_id=en.entity_id
#     AND ah.spread=%s
#     AND ai.account_id = en.entity_id
#     AND ai.expire_date >'%s'
#     AND ai.owner_id = pn.person_id
#     AND pn.name_variant=%s
#     AND pn.source_system=%s
#     """ % (int(co.spread_uit_sut_user),int(co.auth_type_md5_crypt),int(co.spread_uit_sut_user),today,int(co.name_full),int(co.system_cached))
    query = """
    SELECT DISTINCT en.entity_name, aa.auth_data, pu.posix_uid,pn.name, eq.quarantine_type
    FROM entity_name en
    LEFT JOIN entity_quarantine eq
    ON en.entity_id=eq.entity_id,
    entity_spread es, account_authentication aa, posix_user pu, account_home ah, account_info ai,person_name pn
    WHERE ( es.spread=%s OR es.spread=%s)
    AND es.entity_id = en.entity_id
    AND aa.account_id=en.entity_id
    AND aa.method=%s
    AND pu.account_id = en.entity_id
    AND ah.account_id=en.entity_id
    AND (ah.spread=%s OR ah.spread=%s)
    AND ai.account_id = en.entity_id
    AND ai.expire_date >'%s'
    AND ai.owner_id = pn.person_id
    AND pn.name_variant=%s
    AND pn.source_system=%s
    UNION
    select entity_name.entity_name,aa.auth_data,pu.posix_uid,entity_name.entity_name, eq.quarantine_type
    from group_info gi,account_authentication aa, posix_user pu LEFT JOIN entity_quarantine eq ON pu.account_id=eq.entity_id, entity_name AS en_alias, group_member gm
    where en_alias.entity_name ='gjeste-brukere'
    and en_alias.entity_id = gi.group_id
    and gi.group_id=gm.group_id
    and gm.member_id=entity_name.entity_id
    and aa.account_id=gm.member_id
    and aa.method=%s
    and pu.account_id = gm.member_id;
    """ % (int(co.spread_uit_sut_user),int(co.spread_uit_fd),int(co.auth_type_md5_crypt),int(co.spread_uit_sut_user),int(co.spread_uit_fd),today,int(co.name_full),int(co.system_cached),int(co.auth_type_md5_crypt))

    #print "startin query...%s" % query
    db.row = db.query(query)
    for row in db.row:
        #print "quarantine_type=%s" % row['quarantine_type']
        if row['quarantine_type']==None:
            quarantine='False'
        else:
            quarantine='True'
        #print "quarantine=%s" % quarantine
        entries.append({'name' : row['entity_name'],'password' : row['auth_data'],'uid' : row['posix_uid'],'gecos' : row['name'],'quarantine' : quarantine})
    for entry in entries:
        file_path="/its/home/%s/%s/%s" % (entry['name'][0],entry['name'][0:2],entry['name'])
        
        file_handle.writelines("%s:%s:%s:%s:%s:%s:/bin/bash:%s\n" % (entry['name'],entry['password'],entry['uid'],entry['uid'],account.simplify_name(entry['gecos'],as_gecos=1),file_path,entry['quarantine']))
    file_handle.close()
    #print "done"
def usage():
    print """This program exports SUT account to a file
    Data should be copied to the SUT servers for distributuion.

    Usage: [options]
    -s | --sut-file : export file
    -l | --logger-name : name of logger target
    -h | --help : this text """

if __name__ =='__main__':
    main()



