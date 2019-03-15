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
import mx.DateTime



__filename__=os.path.basename(sys.argv[0])
__doc__ = """

Usage %s options
options is

   -s | --spread <name,[name, .. ,name] : Commaseparated list of spreads to process. Default is ALL spreads.
   -d | --dryrun         : Dryrun, do not change db.
   --logger-name <name>  : Which logger to use
   --logger-level <name  : Which loglevel to use

""" % (__filename__)


import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _SpreadCode

DAYS_TO_WAIT=0
DELETE_FROM=mx.DateTime.today()- mx.DateTime.DateTimeDelta(DAYS_TO_WAIT)

db=Factory.get('Database')()
db.cl_init(change_program=__filename__)
co=Factory.get('Constants')(db)
logger = Factory.get_logger('cronjob')



def process_spread(spread):
    spread_txt = spread
    #print "processing spread:%s" % spread
    try:
        if not isinstance(spread,int):
            spread = int(co.Spread(spread))
    except Exception,m:
        logger.error("Could not understand spread=%s, %" % (spread,m))
        return
    else:
        logger.info("Cleaning spread %s (%s)" % (spread, spread_txt))
        ac=Factory.get('Account')(db)

        #logger.info("Caching spreads to be kept")
        #spreads_to_keep = ac.search_spread_expire(spread=spread, expire_date=CUTOFF_DATE)

        logger.info("Caching spread expire table")
        spread_expire_table = ac.search_spread_expire(spread=spread)

        keep_cache = {}
        for sd in spread_expire_table:
            if mx.DateTime.DateFrom(sd['expire_date']) >= DELETE_FROM:
                keep_cache[(sd['entity_id'], sd['spread'])] = sd['expire_date']
                ac.notify_spread_expire(**dict(sd))

        count=0
        for i in ac.search(spread=spread, expire_start=None):
            ac.clear()

            # Don't clean if the spread has been seen within defined cutoff
            if keep_cache.has_key((i['account_id'], spread)):
                continue

            ac.find(i['account_id'])
            logger.info("Cleaning spread %s (%s) on account %s" % (spread_txt, spread, ac.account_name))
            try:
                ac.clear_home(spread)
            except Errors.NotFoundError:
                # homedir not found, thats ok.
                logger.warn("%s had no homedir on spread %s" % \
                            (ac.account_name,spread_txt))
            ac.delete_spread(spread)
            #ac.write_db()
            count+=1
        logger.info("Finished cleaning spread %s, deleted %d" % (spread,count))


def usage(exit_code=0,m=None):
    if m:
        print m
    print __doc__
    sys.exit(exit_code)
    

def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:dh',
                                  ['spread','dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    dryrun = False
    spread_list=None
    for opt,val in opts:
        if opt in('-s','--spread'):
            spread_list = val
        if opt in('-d','--dryrun'):
            dryrun = True
        if opt in('-h','--help'):
            usage()

    if spread_list is None:
        spread_list = []
        for c in dir(co):
            tmp = getattr(co, c)
            if isinstance(tmp, _SpreadCode):
                spread_list.append(str(tmp))
        spread_list = ','.join(spread_list)

    logger.debug("deleting spreads expired before %s" % (DELETE_FROM,))
    for s in spread_list.split(','):
        if s == 'exchange_mailbox':
            logger.info("Skipping exchange spread")
            continue
        process_spread(s)

    if dryrun:
        db.rollback()
        logger.info("Dryrun, do not change database")
    else:
        db.commit()
        logger.info("Committed all changes")


if __name__=='__main__':
    main()
