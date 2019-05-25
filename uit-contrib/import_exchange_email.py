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

import getopt
import sys
import os
import re
import csv

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit import Email
#from Cerebrum.modules import Email


logger=Factory.get_logger('cronjob')

progname = __file__.split("/")[-1]
db = Factory.get('Database')()
db.cl_init(change_program=progname)

ac = Factory.get('Account')(db)
co = Factory.get('Constants')(db)
em = Email.email_address(db, logger=logger)
#em = Email.EmailAddress(db)

valid_exchange_domains = cereconf.EXCHANGE_CONTROLLED_DOMAINS
default_import_file = os.path.join(cereconf.CB_SOURCEDATA_PATH, 'ad', 'AD_Emaildump.cvs')

def set_mail(account, localpart, domain, is_primary):

   # Validate localpart
   validate = re.compile('(^[A-Za-z])([A-Za-z0-9\.\-_]*)([A-Za-z0-9]$)')
   if not validate.match(localpart):
       logger.error('Invalid localpart %s for user %s' , (localpart, account))
       return False

   # Validate domain part
   if domain not in valid_exchange_domains:
       if domain == 'uit.no':
          logger.warn('Invalid domain (%s) for user %s. BAS controls this domain.' % (domain, account))
       else:
          logger.error('Email address for user %s not in valid domain: %s' % (account, domain))
       return False

   # Find account
   ac.clear()
   try:
      ac.find_by_name(account)
   except:
      logger.error('Account %s not found' % (account))
      return False

   # Re-build email address
   email = '%s@%s' % (localpart, domain)

   # Set email address in ad email table
   ac.set_ad_email(localpart, domain)

   # Update email tables immediately
   logger.info('Running email processing for %s' % account)
   em.process_mail(ac.entity_id, email, is_primary)

   return True


def process_exchange_mail(import_file):
    processed_ok = 0
    processed_failed = 0
    primary = True
    file = open(import_file, 'r')

    ACCOUNT =0
    EMAIL =1
    for line in csv.reader(file, delimiter=','):
        account = line[ACCOUNT]
        email = line[EMAIL]

        try:
            [local, domain] = email.split('@')
        except:
            logger.error('Invalid email address: %s' % email)
            continue

        if set_mail(account, local, domain, primary):
            processed_ok = processed_ok + 1
        else:
            processed_failed = processed_failed + 1

    file.close()

    logger.info("%d emails processed. %d were ok. %d failed" % (processed_ok + processed_failed, processed_ok, processed_failed))


def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'i:d', ['importfile=', 'dryrun', 'help'])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    import_file = default_import_file
    for opt,val in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in('-d','--dryrun'):
            dryrun = True
        elif opt in ('-i', '--importfile='):
            import_file = val
        else:
            usage(1)
 
    process_exchange_mail(import_file)

    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


def usage(exit_status = 0):
    print """This script import primary email account from a nightly Exchange dump.

The options for running this script are:
 -h --help        Displays this help text
 -d --dryrun      Will not commit changes to the database. Default is committing.
 -i --importfile  File to read dump from. Default is %s""" % default_import_file
    sys.exit(exit_status)


if __name__=='__main__':
    main()
    
