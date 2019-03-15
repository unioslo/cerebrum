#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
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




"""
Usage:
ADquickSync.py --url <domain> [options]

--url url to domain to connect to

options is
--help              : show this help
--dryrun            : do not change anything
--logger-name name  : use name as logger target
--logger-level level: use level as log level


This script sync's password changes from Cerebrum to Active Directory.

Example:
ADquickSync.py --url https://mydomain.local:8000 --dryrun

"""

import getopt, sys
import socket

# cerebrum imports
import cerebrum_path
import cereconf
import json
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum.modules import ADutilMixIn
from Cerebrum.modules import CLHandler
    
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")


## Set SSL to ignore certificate checks
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context


class ADquiSync(ADutilMixIn.ADuserUtil):

    def __init__(self, *args, **kwargs):
        super(ADquiSync, self).__init__(*args, **kwargs)
        self.cl = CLHandler.CLHandler(db)


    def quick_sync(self, spread, dry_run):

        self.logger.info('Retreiving changelog entries')
        answer = self.cl.get_events('AD', (self.co.account_password,))
        self.logger.info('Found %s changes to process' % len(answer))        
        retval = True
        for ans in answer:
            if ans['change_type_id'] == self.co.account_password:
                try:
                    pw = json.loads(ans['change_params'])['password']
                except KeyError,m:
                    logger.warn("Password probably wiped already for change_id %s" % (ans['change_id'],))
                else:
                   retval = self.change_pw(ans['subject_entity'],spread, pw.encode("iso-8859-1"), dry_run)
            else:
                self.logger.debug("unknown change_type_id %i" % ans['change_type_id'])
            #We always confirm event, but only if it was successfull
            if retval == True:
                self.cl.confirm_event(ans)
            else:
                self.logger.warn('password change for account id:%s was not completed' % (ans['subject_entity']))
        self.cl.commit_confirmations()


    def change_pw(self, account_id, spread, pw, dry_run):

        self.ac.clear()
        try:
           self.ac.find(account_id)
        except Errors.NotFoundError:
           self.logger.warn("Account id %s had password change, but account not found" % (account_id))
           return True
		
        if self.ac.has_spread(spread):
           dn = self.server.findObject(self.ac.account_name)
           ret = self.run_cmd('bindObject', dry_run, dn)

           pwUnicode = unicode(pw, 'iso-8859-1')
           ret = self.run_cmd('setPassword', dry_run, pwUnicode)
           if ret[0]:
              self.logger.debug('Changed password: %s' % self.ac.account_name)
              return True
	else:
            #Account without ADspread, do nothing and return.
	    self.logger.info("Account %s does not have spread %s" % (self.ac.account_name, spread))
	    return True

        #Something went wrong.
        self.logger.error('Failed change password: %s' % self.ac.account_name)
        return False


def usage(exit_code=0,msg=None):
    if msg:
       print msg
    print __doc__
    sys.exit(exit_code)


def main():

    try:
       opts, args = getopt.getopt(sys.argv[1:],
				  '',
				  ['user_spread=',
				   'url=',
				   'help',
				   'dryrun'])

    except getopt.GetoptError,m:
        usage(1,m)

    delete_objects = False
    dry_run = False
    user_spread=None
    url=None
	
    for opt, val in opts:
       if opt == '--user_spread':
          user_spread = getattr(co, val)  # TODO: Need support in Util.py
       elif opt=='--url':
          url=val
       elif opt == '--help':
          usage(1)
       elif opt == '--dryrun':
          dry_run = True

    if not url:
        usage(1, "Must provide --url")

    if not user_spread:
       user_spread = co.spread_uit_ad_account

    logger.info("Trying to connect to %s" % url)
    ADquickUser = ADquiSync(db, co, logger,url=url)
    try:
        ADquickUser.quick_sync(user_spread, dry_run)
    except socket.error,m:
        if m[0]==111:
            logger.critical("'%s' while connecting to %s, sync service stopped?" % \
                            (m[1],url,))
        else:
            logger.error("ADquicksync failed with socket error: %s" % (m,))
    except Exception,m:
        logger.error("ADquicksync failed: %s" % (m,))

if __name__ == '__main__':
    main()
