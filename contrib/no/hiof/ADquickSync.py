#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003-2010 University of Oslo, Norway
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


import getopt, sys, pickle
import xmlrpclib
import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules import ADutilMixIn
from Cerebrum.modules import CLHandler

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")


class ADquiSync(ADutilMixIn.ADuserUtil):
    def __init__(self, *args, **kwargs):
        super(ADquiSync, self).__init__(*args, **kwargs)
        self.cl = CLHandler.CLHandler(db)

    def quick_sync(self, spread, dry_run, commit_changes=False):
        # We reverse the set of events, so that if the same account
        # has multiple password changes, only the last will be updated.
        # If we didn't reverse, and if the first password update fails,
        # then this would be retried in the next run, and the next password
        # update(s) will not be rerun afterwards, leaving the user with
        # an older password than the last.
        handled = set()
        answer = reversed(self.cl.get_events('ad', (self.co.account_password,)))
        for ans in answer:
            confirm = True
            if ans['change_type_id'] == self.co.account_password:
                if not ans['subject_entity'] in handled:
                    handled.add(ans['subject_entity'])
                    pw = pickle.loads(ans['change_params'])['password']
                    try: 
                        confirm = self.change_pw(ans['subject_entity'],
                                                 spread, pw, dry_run)
                    except xmlrpclib.ProtocolError, xpe:
                        self.logger.warn("Caught ProtocolError: %s %s" %
                                         (xpe.errcode, xpe.errmsg))
                        self.logger.warn("Couldn't change password for %s" %
                                         ans['subject_entity'])
                        confirm = False
                else:
                    self.logger.debug("user %s already updated" %
                                      ans['subject_entity'])
            else:
                self.logger.debug("unknown change_type_id %i" %
                                  ans['change_type_id'])
            if confirm:
                self.cl.confirm_event(ans)
        if commit_changes:                
            self.cl.commit_confirmations()
            self.logger.info("Commited all changes, updated c_l_handler.")
            
    def change_pw(self, account_id, spread, pw, dry_run):
        self.ac.clear()
        self.ac.find(account_id)
        if self.ac.has_spread(spread):
            dn = self.server.findObject(self.ac.account_name)
            self.logger.debug("DN: %s", dn)
            ret = self.run_cmd('bindObject', dry_run, dn)
            self.logger.debug("BIND: %s", ret[0])
            pwUnicode = unicode(pw, 'iso-8859-1')
            ret = self.run_cmd('setPassword', dry_run, pwUnicode)
            if ret[0]:
                self.logger.info('Changed password for %s in domain %s' %
                                 (self.ac.account_name, self.ad_ldap))
                return True
            else:
                #Something went wrong.
                self.logger.warn('Failed change password for %s in domain %s.' % (
                    self.ac.account_name, self.ad_ldap))
                return False
        else:
            #Account without ADspread, do nothing and return.
            self.logger.debug('Account %s does not have spread %s, not updating', 
                              self.ac.account_name, spread)
            return True


def usage():
    print """Usage: ADquickSync.py [options]
            --url url
            --user_spread spread
            --dryrun
            --commit-changes
            --ad-ldap domain_dn (overrides cereconf.AD_LDAP)
  
            Example:
            ADquickSync.py --url https://158.39.170.197:8000 \\
                           --user_spread 'account@ad_adm' \\
                           --ad-ldap 'DC=adm,DC=hiof2,DC=no'
                           --commit-changes
            """
    sys.exit(1)
                           
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'sua:dhc',
                                   ['help',
                                    'user-spread=',
                                    'url=',
                                    'ad-ldap=',
                                    'commit-changes',
                                    'dry_run'])
    except getopt.GetoptError:
        usage()

    delete_objects = False
    dry_run = False	
    ad_ldap = cereconf.AD_LDAP
    user_spread = None
    commit_changes = False
    
    for opt, val in opts:
        if opt in ('-s', '--user-spread'):
            user_spread = getattr(co, val)
        elif opt in ('-a', '--ad-ldap'):
            ad_ldap = val
        elif opt in ('-u', '--url'):
            url = val
        elif opt in ('-c', '--commit-changes'):
            commit_changes = True
        elif opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dry_run'):
            dry_run = True

    ADquickUser = ADquiSync(db,
                            co,
                            logger,
                            url=url,
                            ad_ldap=ad_ldap)
    
    try:
        ADquickUser.quick_sync(user_spread,
                               dry_run,
                               commit_changes=commit_changes)
    except xmlrpclib.ProtocolError, xpe:
        logger.critical("Error connecting to AD service. Giving up!: %s %s" %
                        (xpe.errcode, xpe.errmsg))
        

if __name__ == '__main__':
    main()
