#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
r"""Usage: ADquickSync.py [options]

--url URL               The URL to the AD server, e.g.
                        https://ad.example.com:8000

--user-spread SPREAD    Only users with the given spreads are updated. Can
                        be a comma separated list of spreads.

--cl-key KEY            What key from the change logger the sync should
                        find unsynced accounts from. Default: ad

--dryrun                When set, the AD server is not updated.

--commit-changes        Must be set if Cerebrum's counter should be
                        updated.

--ad-ldap DOMAIN_DN     Overrides cereconf.AD_LDAP.

Example:

ADquickSync.py --url https://158.39.170.197:8000 \
               --user_spread 'account@ad_adm' \
               --ad-ldap 'DC=adm,DC=hiof2,DC=no'
               --commit-changes
"""

import getopt
import pickle
import sys
import xmlrpclib

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules import ADutilMixIn
from Cerebrum.modules import CLHandler

logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
co = Factory.get('Constants')(db)


class ADquickSync(ADutilMixIn.ADuserUtil):

    def __init__(self, *args, **kwargs):
        super(ADquickSync, self).__init__(*args, **kwargs)
        self.cl = CLHandler.CLHandler(db)

    def quick_sync(self, spreads, dry_run, cl_key, commit_changes=False):
        # We reverse the set of events, so that if the same account
        # has multiple password changes, only the last will be updated.
        # If we didn't reverse, and if the first password update fails,
        # then this would be retried in the next run, and the next password
        # update(s) will not be rerun afterwards, leaving the user with
        # an older password than the last.
        handled = set()
        answer = reversed(self.cl.get_events(cl_key,
                                             (self.co.account_password,)))
        for ans in answer:
            confirm = True
            if ans['change_type_id'] == self.co.account_password:
                if not ans['subject_entity'] in handled:
                    handled.add(ans['subject_entity'])
                    pw = pickle.loads(ans['change_params'])['password']
                    try:
                        confirm = self.change_pw(ans['subject_entity'],
                                                 spreads, pw, dry_run)
                    except xmlrpclib.ProtocolError, xpe:
                        self.logger.warn("Caught ProtocolError: %s %s" %
                                         (xpe.errcode, xpe.errmsg))
                        self.logger.warn("Couldn't change password for %s" %
                                         ans['subject_entity'])
                        confirm = False
                    except Exception:
                        self.logger.warn("Unexpected exception", exc_info=1)
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

    def change_pw(self, account_id, spreads, pw, dry_run):
        self.ac.clear()
        self.ac.find(account_id)
        if any(self.ac.has_spread(s) for s in spreads):
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
                # Something went wrong.
                self.logger.warn(
                    'Failed change password for %s in domain %s: %s' % (
                        self.ac.account_name, self.ad_ldap, ret))
                return False
        else:
            # Account without ADspread, do nothing and return.
            self.logger.debug(
                'Account %s does not have spread %s, not updating',
                self.ac.account_name, spreads)
            return True


def usage():
    print __doc__
    sys.exit(1)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   's:ua:dhc',
                                   ['help',
                                    'user-spread=',
                                    'cl-key=',
                                    'url=',
                                    'ad-ldap=',
                                    'commit-changes',
                                    'dryrun'])
    except getopt.GetoptError, e:
        print e
        usage()

    dry_run = False
    ad_ldap = cereconf.AD_LDAP
    user_spreads = []
    url = None
    cl_key = 'ad'
    commit_changes = False

    for opt, val in opts:
        if opt in ('-s', '--user-spread'):
            user_spreads = [getattr(co, v) for v in val.split(',')]
        elif opt in ('-a', '--ad-ldap'):
            ad_ldap = val
        elif opt in ('-k', '--cl-key'):
            cl_key = val
        elif opt in ('-u', '--url'):
            url = val
        elif opt in ('-c', '--commit-changes'):
            commit_changes = True
        elif opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            dry_run = True
        else:
            print "Unknown argument: %s" % opt
            usage()

    if not user_spreads:
        raise Exception('No spreads given, no account will be synced')

    ADquickUser = ADquickSync(db, co, logger, url=url, ad_ldap=ad_ldap)

    try:
        ADquickUser.quick_sync(user_spreads,
                               dry_run,
                               cl_key=cl_key,
                               commit_changes=commit_changes)
    except xmlrpclib.ProtocolError, xpe:
        logger.critical("Error connecting to AD service. Giving up!: %s %s" %
                        (xpe.errcode, xpe.errmsg))


if __name__ == '__main__':
    main()
