#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
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


progname = __file__.split("/")[-1]
__doc__="""This script overrides display name for a specific user.

usage:: %s [arguments] [options]

arguments (all required):
    --firstname name      : persons first name
    --lastname name       : persons last name
    --account name        : account name. The owner of this account is changed

options is
    --help                : show this
    -d | --dryrun         : do not change DB
    --logger-name name    : log name to use
    --logger-level level  : log level to use
""" % ( progname, )


import getopt
import sys
import os

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory


db=Factory.get('Database')()
db.cl_init(change_program=progname)
const=Factory.get('Constants')(db)
account=Factory.get('Account')(db)
person=Factory.get('Person')(db)

logger=Factory.get_logger('console')

def change_person_name(accountname,firstname,lastname):
    try:
        account.find_by_name(accountname)
    except Errors.NotFoundError:
        logger.error("Account %s not found, cannot set new display name" % \
                   (accountname,))
        sys.exit(1)

    try:
        person.find(account.owner_id)
    except Errors.NotFoundError:
           logger.error("Account %s owner %d not found, cannot set new display "
                        "name" % (account,account.owner_id))
           sys.exit(1)


    fullname = " ".join((firstname,lastname))
    print "Firstname: Old:%s, New:%s" % (person.get_name(const.system_cached, const.name_first), firstname)
    print "Lastname:  Old:%s, New:%s" % (person.get_name(const.system_cached, const.name_last), lastname)
    print "Fullname:  Old:%s, New:%s" % (person.get_name(const.system_cached, const.name_full), fullname)

    resp = raw_input("Do you want to store new name(s) in DB? y/[N]:")
    resp = resp.capitalize()
    while ((resp !='Y') and (resp !='N')):
        resp = raw_input("Please answer Y or N: ")
    if (resp == 'Y'):
        source_system = const.system_override
        person.affect_names(source_system,
                            const.name_first,
                            const.name_last,
                            const.name_full)
        person.populate_name(const.name_first, firstname)
        person.populate_name(const.name_last, lastname)
        person.populate_name(const.name_full, fullname)
        person._update_cached_names()
        try:
            person.write_db()
        except db.DatabaseError, m:
            logger.error("Database error, name not updated: %s" % m)
            sys.exit(1)
        return True
    else:
         logger.info("Change cancelled by user request")
         return False

def main():
    global persons,accounts

    try:
        opts,args = getopt.getopt(sys.argv[1:],'d',
            ['firstname=','lastname=','account=','dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    firstname=lastname=account=None
    dryrun = False
    for opt,val in opts:
        if opt in('-d','--dryrun'):
            dryrun = True
        elif opt in('--firstname',):
            firstname=val
        elif opt in('--lastname',):
            lastname=val
        elif opt in('--account',):
            account=val
        elif opt in ('-h','--help'):
            usage()

    if lastname in (None,""):
      usage(1,"A last name is required")
    if firstname in (None,""):
      usage(1,"A first name is required")
    if account in (None,""):
      usage(1,"Accountname is required")

    if not change_person_name(account,firstname,lastname):
       sys.exit(0)

    if (dryrun):
      db.rollback()
      logger.info("Dryrun, rollback changes")
    else:
      db.commit()
      logger.info("Committed changes to DB")


def usage(exitcode=0,msg=None):
    if msg: print msg
    print __doc__
    sys.exit(exitcode)


if __name__=='__main__':
    main()
