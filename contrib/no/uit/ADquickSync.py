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

import argparse
import json
import logging
import socket
import ssl

import six
from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
from Cerebrum.modules.no.uio import ADutils
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)

# Set SSL to ignore certificate checks
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context


class ADquickSync(ADutils.ADuserUtil):

    def __init__(self, *args, **kwargs):
        super(ADquickSync, self).__init__(*args, **kwargs)
        self.cl = CLHandler.CLHandler(self.db)

    def quick_sync(self, spread, dry_run):

        self.logger.info('Retreiving changelog entries')
        answer = self.cl.get_events('AD', (self.co.account_password,))
        self.logger.info('Found %s changes to process' % len(answer))
        retval = True
        for ans in answer:
            if ans['change_type_id'] == self.co.account_password:
                try:
                    pw = json.loads(ans['change_params'])['password']
                except KeyError:
                    logger.warn(
                        "Password probably wiped already for change_id %s",
                        ans['change_id'], )
                else:
                    retval = self.change_pw(ans['subject_entity'], spread,
                                            pw.encode("iso-8859-1"), dry_run)
            else:
                self.logger.debug(
                    "unknown change_type_id %i" % ans['change_type_id'])
            # We always confirm event, but only if it was successfull
            if retval:
                self.cl.confirm_event(ans)
            else:
                self.logger.warn(
                    'password change for account id:%s was not completed',
                    ans['subject_entity'])
        self.cl.commit_confirmations()

    def change_pw(self, account_id, spread, pw, dry_run):

        self.ac.clear()
        try:
            self.ac.find(account_id)
        except Errors.NotFoundError:
            self.logger.warn(
                "Account id %s had password change, but account not found" % (
                    account_id))
            return True

        if self.ac.has_spread(spread):
            dn = self.server.findObject(self.ac.account_name)
            ret = self.run_cmd('bindObject', dry_run, dn)

            pwUnicode = six.text_type(pw, 'iso-8859-1')
            ret = self.run_cmd('setPassword', dry_run, pwUnicode)
            if ret[0]:
                self.logger.debug(
                    'Changed password: %s' % self.ac.account_name)
                return True
        else:
            # Account without ADspread, do nothing and return.
            self.logger.info("Account %s does not have spread %s",
                             self.ac.account_name, spread)
            return True

        # Something went wrong.
        self.logger.error('Failed change password: %s' % self.ac.account_name)
        return False


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user_spread')
    parser.add_argument('--url',
                        required=True)
    parser = add_commit_args(parser, default=True)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    if args.user_spread:
        user_spread = getattr(co, args.user_spread)
    else:
        user_spread = co.spread_uit_ad_account

    logger.info("Trying to connect to %s", args.url)
    ADquickUser = ADquickSync(db, co, logger, url=args.url)
    try:
        ADquickUser.quick_sync(user_spread, args.dry_run)
    except socket.error as m:
        if m[0] == 111:
            logger.critical(
                "'%s' while connecting to %s, sync service stopped?",
                m[1], args.url)
        else:
            logger.error("ADquicksync failed with socket error: %s", m)
    except Exception as m:
        logger.error("ADquicksync failed: %s", m)


if __name__ == '__main__':
    main()
