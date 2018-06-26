#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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
"""Migrate users from one spread, to another spread"""

# TODO: Generalize
# TODO: Multiprocess this. It takes forever for large amounts of users.

import getopt
import sys

import cerebrum_path
import cereconf
from mx.DateTime import now

from Cerebrum.Utils import Factory
from Cerebrum import Errors


def mangle(from_spread, to_spread, file,
           commit=False, log_event=False,
           exclude_events=[], disable_requests=True):
    """Remove and add spreads. Generate events."""
    print('%s: Starting to migrate spreads' % str(now()))

    db = Factory.get('Database')()
    en = Factory.get('Entity')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    db.cl_init(change_program='migrate_spreads')

    # Parse the types to be excluded
    if exclude_events:
        tmp = []
        for x in exclude_events:
            tmp += [int(co.ChangeType(*x.split(':')))]
        exclude_events = tmp

    # Monkeypatch in a function that avoids creating events for certain
    # change types
    log_it = db.log_change

    def filter_out_types(*args, **kwargs):
        if int(args[1]) in exclude_events or not log_event:
            kwargs['skip_event'] = True
            log_it(*args, **kwargs)
        else:
            log_it(*args, **kwargs)
    db.log_change = filter_out_types

    from_spread = co.Spread(from_spread)
    to_spread = co.Spread(to_spread)

    # TODO: You whom are reading this in the future should make this more
    # generic!  You can for example replace 'ac' with 'locals()[object]',
    # where 'object' defines the object to act on. Then you should use
    # __setattr__ to replace the appropriate bofhd_request-generating method.
    # If you dare!
    if disable_requests:
        ac._UiO_order_cyrus_action = lambda *args, **kwargs: True

    # Cache all auto groups ids.
    exclude_gids = []
    # Cache auto_group and meta_auto_group traits.
    for trait in en.list_traits(code=[co.trait_auto_group,
                                      co.trait_auto_meta_group]):
        exclude_gids.append(trait['entity_id'])

    # Import the Exchange-related utils.
    from Cerebrum.modules.exchange.CerebrumUtils import CerebrumUtils
    cu = CerebrumUtils()

    f = open(file, 'r')
    for line in f:
        uname = line.strip()
        if not uname:
            continue
        ac.clear()
        try:
            ac.find_by_name(uname)
        except Errors.NotFoundError:
            print('%s seems to be nuked, skipping..' % uname)
            continue
        # TODO: Is this _entirely_ correct?
        if not ac.get_spread() and ac.expire_date:
            print('%s seems to be deleted, skipping..' % uname)
            continue
        # TODO: We should report if the account does not have the spread
        # we want to remove. We should really raise an error if we try to
        # delete a spread that does not exist on an account...

        # Use savepoints to handle the cases where a user occours two times
        # in a file, or a user is remigrated. A savepoint is kind of like a
        # nested transaction. We do it like this, because it is simpler to
        # implement, than checking the input-file for duplicates and
        # existing spreads...
        try:
            db.execute('SAVEPOINT migrate_spread')
            ac.delete_spread(from_spread)
            ac.add_spread(to_spread)
        except db.IntegrityError:
            db.execute('ROLLBACK TO SAVEPOINT migrate_spread')
            print('%s allready migrated? skipping..' % uname)
            continue
        else:
            db.execute('RELEASE SAVEPOINT migrate_spread')
            ac.write_db()

        # Figure out if we should add this user to an auto_group.
        # We should only do this for primary accounts.
        add_to_auto_group = False
        try:
            pe.clear()
            pe.find(ac.owner_id)
        except Errors.NotFoundError:
            pass
        else:
            if ac.entity_id == pe.get_primary_account():
                add_to_auto_group = True

# TODO: Factor out this and generalize it! This is a BAD hack
# We really need to generate some faux events. For example, when a user is
# migrated from cyrus to exchange, we must generate events for addition of
# the user into groups :S
###
        # Fetch the accounts memberships
        # Fetch the persons memberships IF the account is the primary account
        # Combine the two above
        # Generate events
        for gname, gid in cu.get_account_group_memberships(
                ac.account_name, co.spread_exchange_group):
            # Skip all auto-groups if this is not the primary account.
            if gid in exclude_gids and not add_to_auto_group:
                continue

            ct = co.ChangeType('e_group', 'add')
            db.log_change(gid,
                          int(ct),
                          ac.entity_id,
                          change_params=None,
                          skip_change=True)

            print('Creating e_group:add event for %s -> %s' %
                  (ac.account_name, gname))
###

        print('%-9s: removed %s, added %s' %
              (uname, str(from_spread), str(to_spread)))
    f.close()

    if commit:
        db.commit()
        print 'Committed all changes'
    else:
        db.rollback()
        print 'Rolled back all changes'
    print('%s: Finished migrating spreads' % str(now()))


def usage(code=0):
    """Print usage text."""
    print('Usage: migrate_spreads.py -f IMAP@uio -t exchange_acc@uio -d '
          '-u <name>')
    print('    --from           (-f) spread to migrate from')
    print('    --to             (-t) spread to migrate to')
    print('    --commit         (-c) Commit-mode on')
    print('    --dis-reqs       (-d) Disable bofhd requests?')
    print('    --log-event      (-e) Log events for spread removal and '
          'addition')
    print('    --exclude-events (-x) Events to exclude from logging '
          '(i.e. spread:add,spread;delete)')
    print('    --users          (-u) File containig users to do this on')
    print('    --help           (-h) This help')
    sys.exit(code)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:t:cdeu:hx:',
                                   ['from=',
                                    'to=',
                                    'commit',
                                    'dis-reqs',
                                    'log-event',
                                    'exclude-events=',
                                    'users=',
                                    'help'])
    except getopt.GetoptError:
        usage(3)

    commit = False
    from_spread = None
    to_spread = None
    disable_requests = False
    log_events = False
    exclude_events = []
    users_file = None
    for opt, val in opts:
        if opt in ('-c', '--commit'):
            commit = True
        elif opt in ('-f', '--from'):
            from_spread = val
        elif opt in ('-t', '--to'):
            to_spread = val
        elif opt in ('-c', '--commit', '--let-it-rip'):
            commit = True
        elif opt in ('-d', '--dis-reqs'):
            disable_requests = True
        elif opt in ('-e', '--log-event'):
            log_events = True
        elif opt in ('-x', '--exclude-events'):
            for x in val.split(','):
                if x:
                    exclude_events += [x.strip()]
        elif opt in ('-u', '--users'):
            users_file = val
        elif opt in ('-h', '--help'):
            usage(0)
        else:
            print('Error: Unknown argument')
            usage(3)

    if not from_spread and not to_spread:
        print('Plz define from- and to-spread!!!')
        usage(3)

    if not users_file:
        print('Must have that list of users!')
        usage(3)

    mangle(from_spread, to_spread, users_file, commit, log_events,
           exclude_events, disable_requests)
