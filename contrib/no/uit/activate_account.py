#! /usr/bin/env python
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


'''
This script activates expired accounts and makes sure they wont break export scritps later on.
'''


import cerebrum_path
import cereconf
import getopt
import sys

from mx import DateTime
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email
from Cerebrum import Errors


logger = None
default_logger = "cronjob"
db = Factory.get('Database')()
db.cl_init(change_program='activate_account')



def activate_account(account, expire_date=None, spreads=None):
    pe = Factory.get('Person')(db)
    gr = Factory.get('Group')(db)
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    pu = PosixUser.PosixUser(db)

    # Assure account and person are ok (must be!)
    try:
        logger.info("Resolving given account name: %s" % account)
        ac.find_by_name(account)
        pe.find(ac.owner_id)
    except Exception, msg:
        logger.error("Given account name is invalid. Error message follows: %s" % msg)

    # Assure that expire_date is valid
    right_now = DateTime.now()
    if expire_date is None:
        # If no expire date is given, default to two weeks from now
        expire_date = right_now + DateTime.oneWeek * 2
    else:
        try:
            expire_date = DateTime.Parser.DateFromString(expire_date)
        except Exception, msg:
            logger.error("Date not correctly formatted. Error message follows: %s" % msg)
            sys.exit(1)

    if expire_date < right_now:
        logger.error("Cannot set expire_date to the past. Date given: %s" % expire_date)
        sys.exit(1)
    

    # Assure that spreads are valid
    if spreads is None:
        spreads = ['fd@uit', 'ldap@uit']
    for spread in spreads:
        try:
            spread_id = int(co.Spread(spread))
        except Exception, msg:
            logger.error("Invalid spread encountered. Error message follows: %s" % msg)
            sys.exit(1)


    # Assure posix user is ok
    try:
        logger.info("Resolving posix user")
        pu.find(ac.entity_id)
    except Errors.NotFoundError:
        logger.warn("Posix account not found. Trying to promote....")
        uid = pu.get_free_uid()
        shell = co.posix_shell_bash
        grp_name = "posixgroup"
        gr.find_by_name(grp_name, domain=co.group_namespace)
        try:
            pu.clear()
            pu.populate(uid, gr.entity_id, None, shell, parent=ac)
            pu.write_db()
            logger.info("...promotion ok!")
        except Exception,msg:
            logger.error("Error promoting. Error message follows: %s" % msg)
            sys.exit(1)

    # Gecos treatment - What is gecos???
    old_gecos = pu.get_gecos()
    full_name = "%s %s" % (pe.get_name(co.system_cached, co.name_first) ,
                           pe.get_name(co.system_cached, co.name_last))
    new_gecos = pu.simplify_name(full_name, as_gecos=1)
    if (new_gecos != old_gecos):
        logger.info( "Updating gecos. Old name: %s, new name: %s" % (old_gecos, new_gecos))
        pu.gecos = new_gecos
        pu.write_db()

    # Update expire date
    logger.info("Updating expire date to %s" % expire_date)
    pu.expire_date = "%s" % expire_date
    pu.write_db()

    # Updating homedir for existing spreads
    logger.info("Updating homedirs for current spreads")
    cur_spreads = pu.get_spread()
    for spread in cur_spreads:
        pu.set_home_dir(spread['spread'])
        
    # Adding spreads
    for spread in spreads:
        spread_id = int(co.Spread(spread))
        if ( not pu.has_spread(spread_id)):
            logger.info("Adding spread %s and setting homedir for it" % spread)
            pu.add_spread(spread_id)
            pu.set_home_dir(spread_id)

    # Updating Email:
    em = Email.email_address(db)
    ad_email = em.get_employee_email(ac.entity_id, db)
    if (len(ad_email)>0):
        ad_email = ad_email[ac.account_name]
    else:
        ad_email = "%s@%s" % (ac.account_name, "mailbox.uit.no")
        
    current_email = ""
    try:
        current_email = ac.get_primary_mailaddress()
    except Errors.NotFoundError:
        # no current primary mail.
        pass
    
    if (current_email.lower() != ad_email.lower()) and len(current_email) >= 5:
        # update email!
        logger.info("Email update needed old='%s', new='%s'" % (current_email, ad_email))
        try:
            em.process_mail(ac.entity_id, "defaultmail", ad_email)
        except Exception:
            logger.critical("Email update failed: account_id=%s , email=%s" % (ac.entity_id, ad_email))
            sys.exit(2)
    else:
        logger.info("Email update not needed (%s)" % current_email)


        
def main():
    global logger, default_logger, db

    logger = Factory.get_logger(default_logger)


    try:
        opts,args = getopt.getopt(sys.argv[1:],'a:e:s:d',['account_name','expire_date','spreads','dryrun'])
    except getopt.GetoptError:
        usage()

    ret = 0
    account = ''
    expire_date = None
    spreads = None
    dryrun = 0
    for opt,val in opts:
        if opt in('-a','--account_name'):
            account = val
        if opt in('-e','--expire_date'):
            expire_date = val
        if opt in('-s','--spreads'):
            spreads = val
        if opt in('-d','--dryrun'):
            dryrun = 1

    if not spreads is None:
        tmp_spreads = []
        for spread in spreads.split(','):
            tmp_spreads.append(spread.lstrip().rstrip())
        spreads = tmp_spreads


    activate_account(account, expire_date, spreads)
    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rolling back changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")
            
                               
def usage():
    print """
    usage:: python activate_account.py -a rmi000 -e 20101230 -s 'fd@uit, ldap@uit'
    -a | --account_name : account to activate
    -e | --expire_date: new expire date for account. Default is now() + 2 weeks
    -s | --spreads: quoted, comma delimited list of spreads. Defaults are fd@uit + ldap@uit
    -d | --dryrun : dryrun

    
    """
    sys.exit(1)


if __name__=='__main__':
    main()
