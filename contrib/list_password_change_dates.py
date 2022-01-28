#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2015 University of Oslo, Norway
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

u"""Takes a file with account names, lists password change timestamps."""

from __future__ import print_function

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.pwcheck.history import PasswordHistory


def print_change_dates(accounts):
    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)
    logger = Factory.get_logger('console')
    ph = PasswordHistory(db)

    for account_name in accounts:
        ac.clear()

        try:
            ac.find_by_name(account_name)
        except Errors.NotFoundError:
            logger.error("No such account {!r}".format(account_name))
            continue

        history = ph.get_history(ac.entity_id)
        if history:
            history = sorted(history, key=lambda x: x['set_at'])
            last = dict(history[-1])
            print("{}\t{}".format(account_name, str(last['set_at'])))
        else:
            print("{}\t{}".format(account_name, 'NEVER'))


def main():
    """ Script invocation. """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-a', '--account-file', dest='account_file',
                        help='text file with newline separated account names',
                        required=True)
    args = parser.parse_args()

    with open(args.account_file) as af:
        accounts = filter(None, (line.rstrip() for line in af))

    print_change_dates(accounts)

if __name__ == '__main__':
        main()
