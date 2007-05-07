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
uid:crypt:uid:gid:gecos:home:shell:quarntine,affs
eks:
paalde:xySfdaS3aS2:500:500:Paal D. Ekran:/its/home/p/pa/paalde:/bin/bash:true,STUDENT\aktiv
"""

import sys
import re
import os
import mx
import getopt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.modules import PosixUser
from Cerebrum.Utils import Factory

db=Factory.get('Database')()
co=Factory.get('Constants')(db)
logger_name = cereconf.DEFAULT_LOGGER_TARGET

def build_data_cache():   
    ac = Factory.get('Account')(db)
    p = Factory.get('Person')(db)
    posix = PosixUser.PosixUser(db)

    exp_spread=[co.spread_uit_fd, co.spread_uit_sut_user]
    accounts=dict()
    for spread in exp_spread:
        logger.info("Retreiving accounts with spread = %s" % spread)
        for acc in ac.list_account_home(home_spread=spread,account_spread=spread):
            acc_id=acc['account_id']
            if not accounts.has_key(acc_id):           
                accounts[acc_id] = (acc['entity_name'],acc['owner_id'],acc['home'])


    logger.info("Retreiving auth strings")
    auth_list=dict()
    auth_type=co.auth_type_md5_crypt
    for auth in ac.list_account_authentication(auth_type=auth_type,filter_expired=True):
        auth_list[auth['account_id']]=auth['auth_data']
            
    person_names = dict()
    logger.info("Retreiving person names strings")
    for pers in p.list_persons_name(source_system=co.system_cached):
        p_id = int(pers['person_id'])
        p_name=pers['name']        
        if person_names.has_key(p_id):
            logger.warn("Person id %s seen before. current=%s, this=%s" % (p_id,person_names[p_id],p_name))
        else:       
            person_names[p_id] = p_name
  
    person_affs = dict()
    logger.info("Retreiving person affiliations")
    for pers in p.list_affiliations(include_deleted=False):
        p_id = int(pers['person_id'])
        data = (pers['affiliation'],pers['status'])
        if person_affs.has_key(p_id):
            current = person_affs[p_id]
            current.append(data)
            person_affs[p_id] = current
        else:
            person_affs[p_id] = [data]     
        
    posix_info=dict()
    for pu in posix.list_posix_users():
        if accounts.has_key(pu['account_id']):
            posix_info[pu['account_id']] = (pu['posix_uid'],pu['gid'])
     
    quarantines=dict()
    logger.info("Retreiving quarantines")
    for q in ac.list_entity_quarantines(only_active=True):
        if accounts.has_key(q['entity_id']):
            quarantines[q['entity_id']]=True
    
    logger.info("DataCaching finished")
    return (accounts,posix_info,quarantines,auth_list,person_names,person_affs)

def usage():
    print """This program exports SUT account to a file
    Data should be copied to the SUT servers for distributuion.

    Usage: [options]
    -s | --sut-file : export file
    -l | --logger-name : name of logger target
    -h | --help : this text """   
    sys.exit(1)


def main():
    global logger, logger_name
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:l:h',
                                ['sut-file=','logger-name', 'help'])
    except getopt.GetoptError:
        usage()

    sut_file = None
    help = 0
    for opt,val in opts:
        if opt in ('-s','--sut-file'):
            sut_file = val
        if opt in ('-l','--logger-name'):
            logger_name = val
        if opt in('-h','--help'):
            usage()
    if not sut_file:
        usage()

    logger = Factory.get_logger(logger_name)
  
    start_time=mx.DateTime.now()
    accounts, posix, quarantines, auth, names, affs =  build_data_cache()
    export = []
    logger.info("Building export data from cache")
    for acc_id in accounts.keys():
        acc_data=accounts[acc_id]
        acc_name=acc_data[0]
        acc_owner=acc_data[1]
        acc_home=acc_data[2]
        acc_auth=auth[acc_id]
        try:
            person_name=names[acc_owner]
        except KeyError:
            person_name=acc_name
#        acc_home = os.path.sep + os.path.join('its','home',acc_name[:1],acc_name[:2],acc_name)
        aff_str=[]
        try:
            active_affs=affs[acc_owner]
            for a in active_affs:
                aff_str.append("%s" % (co.PersonAffStatus(a[1])))            
        except KeyError:
            logger.warn("no active person affs for account=%s, owner_id=%s" % 
                        (acc_name,acc_owner))
        aff_str=",".join(aff_str)
        pos_uid,pos_gid=posix[acc_id]
        shell='/bin/bash'
        try :
            quarantine=quarantines[acc_id]
        except KeyError:
            quarantine=False
        
        entry = [acc_name,acc_auth,
                str(pos_uid),str(pos_gid),
                person_name,acc_home,shell,
                str(quarantine),aff_str,'\n']
        export.append(":".join(entry))
    fh=open(sut_file,'w')
    fh.writelines(export)
    fh.close()
    end_time=mx.DateTime.now()
    logger.info("Started: %s" % (start_time))
    logger.info("Ended %s" % (end_time))
    logger.info("Entries exported: %d" % (len(export)))
    logger.info("Exceution time %s" % (end_time-start_time))

if __name__ == '__main__':
    main()

