#!/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

import os
import sys
import getopt


__filename__=os.path.basename(sys.argv[0])
__doc__ = """

Usage %s options
options is

   -d | --dryrun         : Dryrun, do not change db, nor send e-mails
   --logger-name <name>  : Which logger to use
   --logger-level <name  : Which loglevel to use

""" % (__filename__)


import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.modules.no.uit.MailQ import MailQ
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")

def usage(exit_code=0,m=None):
    if m:
        print m
    print __doc__
    sys.exit(exit_code)
    

def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'dh',
                                  ['dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    dryrun = False
    for opt,val in opts:
        if opt in('-d','--dryrun'):
            dryrun = True
        if opt in('-h','--help'):
            usage()

    logger.info("Starting to process MailQ")
    mailq = MailQ(db, logger)
    mailq.process(dryrun=dryrun, master_template="Master_Spread")
    logger.info("Finished processing MailQ")

    if dryrun:
        db.rollback()
        logger.info("Dryrun, do not change database")
    else:
        db.commit()
        logger.info("Committed all changes")


if __name__=='__main__':
    main()
