#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
r"""Active Directory sync client for the Cerberum AD-Service

This sync uses the Cerebrum.modules.ad and
Cerebrum.modules.no.uio.ADSync modules to sync users and groups to an XML-RPC
service.


Example Usage:

  ad_fullsync.py --user-sync --store-sid

  ad_fullsync.py --user-sync --password-sync --group-sync \
    --user_spread 'AD_account' --group_spread 'AD_group' \
    --delete --store-sid --logger-level DEBUG --logger-name console

"""
import argparse
import logging
import xmlrpclib

import cereconf

from Cerebrum import Utils
from Cerebrum.logutils import autoconf
from Cerebrum.logutils.options import install_subparser
from Cerebrum.modules.no.uio import ADsync


logger = logging.getLogger('ad_fullsync')


def user_sync(db, args):
    co = Utils.Factory.get('Constants')(db)
    sync = ADsync.ADFullUserSync(db, co, logger, mock=args.mock)

    try:
        sync.full_sync(
            delete=args.delete,
            spread=args.user_spread,
            dry_run=args.dryrun,
            store_sid=args.store_sid,
            pwd_sync=args.password_sync)
    except xmlrpclib.ProtocolError as xpe:
        logger.critical("Error connecting to AD service, giving up: %s %s",
                        xpe.errcode, xpe.errmsg)


def group_sync(db, args):
    co = Utils.Factory.get('Constants')(db)
    sync = ADsync.ADFullGroupSync(db, co, logger, mock=args.mock)
    try:
        # instantiate sync_class and call full_sync
        sync.full_sync(
            delete=args.delete,
            dry_run=args.dryrun,
            store_sid=args.store_sid,
            user_spread=args.user_spread,
            group_spread=args.group_spread,
            sendDN_boost=args.sendDN_boost,
            full_membersync=args.full_membersync)
    except xmlrpclib.ProtocolError as xpe:
        logger.critical("Error connecting to AD service, giving up: %s %s",
                        xpe.errcode, xpe.errmsg)


def make_parser():
    doc = __doc__.strip().splitlines()

    parser = argparse.ArgumentParser(
        description=doc[0],
        epilog='\n'.join(doc[1:]),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '--mock',
        action='store_true',
        default=False,
        help="use mock service",
    )
    parser.add_argument(
        '--dryrun',
        action='store_true',
        default=False,
        help="report changes that would have been performed",
    )
    parser.add_argument(
        '--store-sid',
        action='store_true',
        default=False,
        help='write the Object-SID of new objects to Cerebrum (external id)',
    )

    parser.add_argument(
        '--delete',
        action='store_true',
        default=False,
        help='delete superfluous objects (users or groups not in Cerebrum)',
    )

    #
    # user sync args
    #
    user_sync = parser.add_argument_group('User-sync',
                                          'Options for syncing users to'
                                          ' Active Directory')
    user_sync.add_argument(
        '-u', '--user-sync',
        action='store_true',
        default=False,
        help='run the user sync',
    )
    user_sync.add_argument(
        '-p', '--password-sync',
        action='store_true',
        default=False,
        help='include passwords in the user sync',
    )
    user_sync.add_argument(
        '--user_spread',
        metavar='NAME',
        default=getattr(cereconf, 'AD_ACCOUNT_SPREAD', None),
        help='select users with spread %(metavar)s (default: %(default)s)',
    )

    #
    # group sync args
    #
    group_sync = parser.add_argument_group('Group-sync',
                                           'Options for syncing groups to'
                                           ' Active Directory')
    group_sync.add_argument(
        '-g', '--group-sync',
        action='store_true',
        default=False,
        help='run the group sync',
    )
    group_sync.add_argument(
        '--full_membersync',
        action='store_true',
        default=False,
        help='write all group memberships with no regards to current'
             ' status',
    )
    group_sync.add_argument(
        '--group_spread',
        metavar='NAME',
        default=getattr(cereconf, 'AD_GROUP_SPREAD', None),
        help='select groups with spread %(metavar)s (default: %(default)s)',
    )
    group_sync.add_argument(
        '--sendDN_boost',
        action='store_true',
        default=False,
        help='send the distinguishedName attribute of group memebers to the AD'
             ' service to save time on user lookups',
    )

    return parser


def main(inargs=None):
    parser = make_parser()
    install_subparser(parser)
    args = parser.parse_args(inargs)
    autoconf('cronjob', args)
    logger.debug("args: %r", args)

    if not any((args.user_sync, args.group_sync)):
        raise RuntimeError("nothing to do")

    db = Utils.Factory.get('Database')()
    db.cl_init(change_program="uio_ad_sync")

    if args.user_sync:
        user_sync(db, args)

    if args.group_sync:
        group_sync(db, args)


if __name__ == '__main__':
    main()
