#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2009 University of Oslo, Norway
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

progname = __file__.split("/")[-1]
__doc__="""
    Reads a list of usernames and each users owner is given ephorte spread
    Files is supplied to us by ePhorte system owner.
    
    Usage:
    %s [options]
    
    options is:
    -h | --help             : Show this.
    -f | --file  filename   : Read usernames from this file
    -u | --username userid  : Give this account's owner ephorte spread
    --hitos                 : Filename given is from HiTos
    --wipe                  : Remove all ePhorte spreads from DB
    --dryrun                : Dryrun. Do not change DB.
    --logger-name name      : Use 'name' as logger target
    --logger-level level    : Use 'level' as logger level
   
    """ % (progname,)

import getopt
import sys
import os
import mx

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program=progname)
account=Factory.get('Account')(db)
person=Factory.get('Person')(db)
co=Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")
CHARSEP=';'

def parse_inputfile(filename,hitos=False):
    # file format is NTLOGIN;DL_LOGIN;FULLNAME
    # Ntlogin is in uppercase. need to lower it.
    dl_users = list()
    import csv
    if hitos:
        fh=open(filename,'r')
        lines=fh.readlines()
        fh.close()
        for line in lines:
            dl_users.append(line.strip())
        
    else:
        for detail in csv.reader(open(filename,'r'),delimiter=CHARSEP):
            
            ntlogin=detail[7].lower()
            dllogin=detail[6]
            fullname=detail[0]
            logger.debug("Read ->%s-%s-%s<-" % (ntlogin,dllogin,fullname))
            if ntlogin:
                dl_users.append(ntlogin)
    
    return dl_users

def populate_ephorte(user_name_list):
    

    logger.info("Work on %s" % (user_name_list))
    for user in user_name_list:
        logger.info("Working on %s" % user)
        account.clear()
        try:
            account.find_by_name(user)
        except Errors.NotFoundError:
            logger.info("Username %s not found in cerebrum" % (user,))
            continue
    
        if account.expire_date < mx.DateTime.today():
            logger.warn("Account %s has DL access, but is expired in BAS" % (user,))
    
    
        person.clear()
        try:
            person.find(account.owner_id)
        except Errors.NotFoundError:
            logger.info("Owner for account %s not found. Owner_id=%d" % (user,account.owner_id))
            continue
            
        if not person.has_spread(co.spread_ephorte_person):
            person.add_spread(co.spread_ephorte_person)
            person.write_db()
            logger.info("Added ePhorte spread for person_id=%d" % (person.entity_id,))
        else:   
            logger.info("Person %s already has ePhorte spread" % (person.entity_id))


def wipe_ephorte_spreads():
    """ Remove all instanses of ePhorte person spread"""
    logger.info("Removing all ePhorte spreads")
    for row in person.list_all_with_spread(co.spread_ephorte_person):
        person.clear()
        person.find(int(row['entity_id']))
        person.delete_spread(co.spread_ephorte_person)
        person.write_db()
        logger.info("Removed ePhorte spread for %d" % (person.entity_id,))


def usage(exit_code=0,msg=''):
    if msg: print msg
    
    print __doc__
    sys.exit(exit_code)


def main():
    username=None
    ephorte_usersfile=None
    dryrun=False
    wipe=False
    hitos_file=False
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:u:dh',
            ['file=','username=','dryrun','wipe','help','hitos'])
    except getopt.GetoptError,m:
        usage(1,m)
   
    for opt,val in opts:
        if opt in('-u','--username'):
            username = val
        elif opt in('-d','--dryrun'):
            dryrun = True
        elif opt in('-f','--file'):
            ephorte_usersfile = val
        elif opt in ('--hitos',):
            hitos_file=True
        elif opt in ('--wipe',):
            wipe=True  
        elif opt in ['-h','--help']:
            usage()
    
    if username is None and ephorte_usersfile is None and wipe is False:
        usage(1,"No command given, supply username, filename or wipe command")
    
    if not wipe:
        ephorte_userlist=list()
        if ephorte_usersfile:
            logger.info("reading file %s" % (ephorte_usersfile))
            users_from_file=parse_inputfile(ephorte_usersfile,hitos=hitos_file)
            ephorte_userlist=users_from_file
        if username:
            ephorte_userlist.append(username)
        populate_ephorte(ephorte_userlist)
    else:
        wipe_ephorte_spreads()
        
    if dryrun:
        db.rollback()
        logger.info("Dryrun. No changes saved to dababase")
    else:
        db.commit()
        logger.info("All changes saved to database")
    
if __name__=="__main__":
    main()
    
logger.info("Fini")
