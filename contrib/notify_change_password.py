#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2008-2016 University of Oslo, Norway
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

from __future__ import unicode_literals
import argparse

from Cerebrum import Utils
from Cerebrum.modules.password_notifier.notifier import PasswordNotifier

logger = Utils.Factory.get_logger("cronjob")
db = Utils.Factory.get('Database')()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='The following options are available')
    parser.add_argument(
        '-d', '--dryrun',
        action='store_true',
        dest='dryrun',
        default=False,
        help='Run in "dryrun" mode')
    parser.add_argument(
        '-f', '--config-file',
        metavar='<filename>',
        type=str,
        default=None,
        dest='alternative_config',
        help='Alternative configuration file for %(prog)s')
    args = parser.parse_args()
    notifier = PasswordNotifier.get_notifier(args.alternative_config)(
        db=db,
        logger=logger,
        dryrun=args.dryrun)
    notifier.process_accounts()
