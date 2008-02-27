#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003-2008 University of Oslo, Norway
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
        answer = self.cl.get_events('ad', (self.co.account_password,))
        for ans in answer:
            if ans['change_type_id'] == self.co.account_password:
                pw = pickle.loads(ans['change_params'])['password']
                self.change_pw(ans['subject_entity'],spread, pw, dry_run)
            else:
                self.logger.debug("unknown change_type_id %i",
                                  ans['change_type_id'])
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
    ad_ldap = None
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
    
    ADquickUser.quick_sync(user_spread,
                           dry_run,
                           commit_changes=commit_changes)

if __name__ == '__main__':
    main()
