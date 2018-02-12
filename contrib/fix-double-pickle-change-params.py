#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2018 University of Oslo, Norway
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
from argparse import ArgumentParser
try:
    import cPickle as pickle
except ImportError:
    import pickle
from Cerebrum.Utils import Factory


"""
We have, by error, some change log entries with double-pickled arguments.
This script tries to unpickle twice, and then insert back into change.
"""


def main():
    parser = ArgumentParser()
    parser.add_argument('-c', '--commit', action='store_true',
                        help='Do commit')
    commit = parser.parse_args().commit
    db = Factory.get('Database')(client_encoding='UTF-8')
    loads = pickle.loads
    logger = Factory.get_logger('console')
    changes = {}
    for row in db.get_log_events():
        cp = row['change_params']
        if cp is None:
            continue
        try:
            val = loads(loads(cp.encode('ISO-8859-1')))
            changes[row['change_id']] = val
            logger.info('Fixing row %s: %s', row['change_id'], val)
        except TypeError:
            pass
    # Do this last, because it will lock change log for others
    for change, params in changes.items():
        db.update_log_event(change, params)
    if commit:
        logger.info('Done. Committing changes')
        db.commit()
    else:
        logger.info('Done. Rolling back changes')
        db.rollback()

if __name__ == '__main__':
    main()
