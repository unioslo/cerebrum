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


progname = __file__.split("/")[-1]
__doc__="""This script creates/updates email addresses for all accounts
in cerebrum that has a email spread

usage:: %s [options] 

options is    
    -h | --help     : show this
    -d | --dryrun   : do not change DB
    --logger-name name   : log name to use 
    --logger-level level : log level to use
""" % ( progname, )


import getopt
import sys
import os


import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email


db = Factory.get('Database')()
ac = Factory.get('Account')(db)
p = Factory.get('Person')(db)
co = Factory.get('Constants')(db)
db.cl_init(change_program=progname)

logger=Factory.get_logger('cronjob')

em=Email.email_address(db,logger=logger)



def process_mail():
    
    logger.info("Get all accounts with exchange@uit spread")
    exch_users=dict()
    for a in ac.search(spread=co.spread_uit_exchange):
        exch_users[a['account_id']]= a['name']
    logger.info("got %d accounts" % len(exch_users))

    logger.info("Get all account with post@uit spread")
    nonexch_users=dict()
    for a in ac.search(spread=co.spread_uit_sutmail):
        nonexch_users[a['account_id']]= a['name']
    logger.info("got %d accounts" % len(nonexch_users))    

    all_emails = dict()
    primary=dict()
            
    for account_id,uname in nonexch_users.iteritems():
        uid_addr="@".join((uname,cereconf.NO_MAILBOX_DOMAIN))
        all_emails.setdefault(account_id,list()).append(uid_addr)
        primary[account_id]=uid_addr

    for account_id,uname in exch_users.iteritems():
        uid_addr="@".join((uname,cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES))
        all_emails.setdefault(account_id,list()).append(uid_addr)
        primary[account_id]=uid_addr

        cn_addr=get_cn_mailaddr(account_id)
        if cn_addr:
            logger.debug("Got %s as mailaddres for %s" % (cn_addr,uname))
            all_emails.setdefault(account_id,list()).append(cn_addr)
            primary[account_id]=cn_addr
        
    # update all email addresses
    for acc_id,emaillist in all_emails.iteritems():
        for addr in emaillist:
            is_primary =  addr == primary.get(acc_id,None)
            logger.info("Set mailaddr: %s/%s, primary=%s" % (acc_id,addr,is_primary))
            em.process_mail(acc_id,addr, is_primary=is_primary)


def get_cn_mailaddr(a_id):

    #les fra ad_email tabellen
    cn=em.get_employee_email(a_id,db)
    try:
        return cn.items()[0][1]
    except Exception:
        return None
    

def main():
    global persons,accounts
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'dh',
                                  ['dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)
        
    dryrun = False 
    for opt,val in opts:
        if opt in('-d','--dryrun'):
            dryrun = True
        elif opt in ('-h','--help'):
            usage()

    process_mail()
    
    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


def usage(exitcode=0,msg=None):
    if msg: print msg        
    print __doc__
    sys.exit(exitcode)


if __name__=='__main__':
    main()
    
