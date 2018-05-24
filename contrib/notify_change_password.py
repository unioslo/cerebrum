#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2008-2018 University of Oslo, Norway
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
Send password change notifications and quarantine accounts.

This script sends password notifications for accounts that are due for a
new password.  It will also quarantine accounts where the password is not
changed within the deadline.
"""
from __future__ import unicode_literals

import argparse
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Utils
from Cerebrum.modules.password_notifier.notifier import PasswordNotifier

logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(__doc__ or '').strip())
    parser.add_argument(
        '-d', '--dryrun',
        action='store_true',
        dest='dryrun',
        default=False,
        help='Run in "dryrun" mode')
    parser.add_argument(
        '-f', '--config-file',
        metavar='<filename>',
        type=six.text_type,
        default=None,
        dest='alternative_config',
        help='Alternative configuration file for %(prog)s')
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Utils.Factory.get('Database')()

    notifier = PasswordNotifier.get_notifier(args.alternative_config)(
        db=db,
        dryrun=args.dryrun)
    notifier.process_accounts()

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
