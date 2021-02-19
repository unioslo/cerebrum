#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
Generate a list of recently created users without a password.


Format
------
The file contains one user account per line, and contains the owners norwegian
national id, the user account name, and some additional info: "<nin> <username>
<info>"

For accounts that are missing a password update, the info field will contain an
ISO8601 formatted creation date for the account. If the account included in the
export *has* performed a password update, the field will include a default
message:

::

    01017000000 user1 2019-01-01 13:00:00
    01017000000 user2 Was either not created recently ...


History
-------
This script was previously a part of the old cerebrum_config repository. It was
moved into the main Cerebrum repository, as it was currently in use by ØFK.

The original can be found in cerebrum_config.git, as
'bin/new_accounts_wo_pass.py' at:

  commit e83e053edc03dcd399775fadd9833101637757ef
  Merge: bef67be2 3bfbd8a2
  Date:  Wed Jun 19 16:07:06 2019 +0200
"""
import argparse
import datetime
import functools
import logging
import sys

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type
from Cerebrum.utils.date_compat import get_datetime_tz

logger = logging.getLogger(__name__)


def read_account_names(filename):
    with open(filename, 'r') as f:
        for raw_line in f:
            account_name = raw_line.strip()
            if not account_name or account_name.startswith('#'):
                continue
            yield account_name


def find_recent_accounts(db, days):
    """
    Get a list of accounts created within the last <n> days that has not
    changed their password.
    """
    cl = Factory.get('CLConstants')(db)
    start_date = datetime.date.today() - datetime.timedelta(days=days)
    has_password = set(
        r['subject_entity']
        for r in db.get_log_events(types=cl.account_password,
                                   sdate=start_date))

    for r in db.get_log_events(types=cl.account_create, sdate=start_date):
        if r['subject_entity'] in has_password:
            continue
        yield int(r['subject_entity'])


def get_account_by_id(db, account_id):
    """
    Procure account by account_id.
    """
    ac = Factory.get('Account')(db)
    ac.find(account_id)
    return ac


def get_account_by_name(db, account_name):
    """
    Procure account by account_name.
    """
    ac = Factory.get('Account')(db)
    ac.find_by_name(account_name)
    return ac


def get_user_info(ac):
    db = ac._db
    pe = Factory.get('Person')(db)
    pe.find(ac.owner_id)
    co = Factory.get('Constants')(db)

    if not ac.created_at:
        raise ValueError("Missing created_at for account_id=%r (%s)" %
                         (ac.entity_id, ac.account_name))

    created_at = ac.created_at.pydatetime()

    for row in pe.get_external_id(id_type=co.externalid_fodselsnr):
        nin = row['external_id']
        break
    else:
        raise ValueError('Missing external_id for account_id=%r (%s)' %
                         (ac.entity_id, ac.account_name))

    return {
        'owner_id': ac.owner_id,
        'owner_nin': nin,
        'created_at': created_at,
        'account_id': ac.entity_id,
        'account_name': ac.account_name,
    }


def format_line(user_info, data):
    return '{info[owner_nin]} {info[account_name]} {data}\n'.format(
        info=user_info, data=data)


def write_missing_passwords(db, account_ids, stream):
    stats = {'ok': 0, 'skipped': 0}
    for account_id in account_ids:
        try:
            ac = get_account_by_id(db, account_id)
            user_info = get_user_info(ac)
            stats['ok'] += 1
        except Exception as e:
            logger.error("Unable to get account_id=%r: %s", account_id, e)
            stats['skipped'] += 1
        stream.write(
            format_line(
                user_info,
                user_info['created_at'].strftime('%Y-%m-%d %H:%M:%S')))
    logger.debug('Stats: %s', repr(stats))


def write_check_account(names_to_check, db, account_ids, stream):
    stats = {'changed': 0, 'not-changed': 0, 'skipped': 0}
    default_msg = ('Was either not created recently or did indeed change '
                   'own password')

    for account_name in sorted(names_to_check):
        try:
            ac = get_account_by_name(db, account_name)
            user_info = get_user_info(ac)
        except Exception as e:
            logger.error("Unable to get account_name=%r: %s",
                         account_name, e)
            stats['skipped'] += 1
            continue

        if ac.entity_id in account_ids:
            # No recent password change
            line = format_line(
                user_info,
                user_info['created_at'].strftime('%Y-%m-%d %H:%M:%S'))
            stats['not-changed'] += 1
        else:
            line = format_line(user_info, default_msg)
            stats['changed'] += 1
        stream.write(line)
    logger.debug('Stats: %s', repr(stats))


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Write a report on users without passwords',
    )

    parser.add_argument(
        '-o', '--output',
        type=argparse.FileType('w'),
        default='-',
        help='the file to print the report to (stdout)',
        metavar='<file>',
    )

    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        type=codec_type,
        default='utf-8',
        help='output file encoding (%(default)s)',
        metavar='<codec>',
    )

    parser.add_argument(
        '--days',
        default=180,
        type=lambda i: abs(int(i)),
        help='report accounts newer than %(metavar)s days (%(default)s)',
        metavar='<n>',
    )

    parser.add_argument(
        '-l', '--list',
        help='filter by account names found in %(metavar)s',
        metavar='<file>',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    if args.list:
        check_names = set(read_account_names(args.list))
        logger.info('Restricting report to %d accounts from %r',
                    len(check_names), args.list)
        write_report = functools.partial(write_check_account, check_names)
    else:
        write_report = write_missing_passwords

    db = Factory.get('Database')()
    stream = args.codec.streamwriter(args.output)

    recent_accounts = set(find_recent_accounts(db, args.days))
    logger.info('Considering %d accounts from change_log',
                len(recent_accounts))

    write_report(db, recent_accounts, stream)

    args.output.flush()

    # If the output is being written to file, close the filehandle
    if args.output not in (sys.stdout, sys.stderr):
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done %s', parser.prog)


if __name__ == "__main__":
    main()
