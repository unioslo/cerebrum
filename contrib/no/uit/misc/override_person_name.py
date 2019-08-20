#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2019 University of Oslo, Norway
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
import argparse
import logging
# import os

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def get_person(db, username):
    account = Factory.get('Account')(db)
    try:
        account.find_by_name(username)
    except Errors.NotFoundError:
        logger.error("No username=%r", username)
        raise

    person = Factory.get('Person')(db)
    try:
        person.find(account.owner_id)
    except Errors.NotFoundError:
        logger.error("No person with person_id=%r", account.owner_id)
        raise

    return person


def ask_yn(question, default=False):
    """Interactive confirmation prompt"""
    if question:
        print(question)
    if default:
        prompt = '[Y]/n'
    else:
        prompt = 'y/[N]'

    while True:
        resp = raw_input(prompt + ': ').strip().lower()
        if resp == 'y':
            return True
        elif resp == 'n':
            return False
        elif resp == '':
            return default
        else:
            print('Invalid input')
            continue


def change_person_name(db, person, firstname, lastname):
    const = Factory.get('Constants')(db)
    fullname = " ".join((firstname, lastname))
    print("First name: %r -> %r" % (person.get_name(const.system_cached,
                                                    const.name_first),
                                    firstname))
    print("Last name:  %r -> %r" % (person.get_name(const.system_cached,
                                                    const.name_last),
                                    lastname))
    print("Full name:  %r -> %r" % (person.get_name(const.system_cached,
                                                    const.name_full),
                                    fullname))
    source_system = const.system_override
    person.affect_names(source_system,
                        const.name_first,
                        const.name_last,
                        const.name_full)
    person.populate_name(const.name_first, firstname)
    person.populate_name(const.name_last, lastname)
    person.populate_name(const.name_full, fullname)
    person._update_cached_names()
    person.write_db()


def nonempty_type(raw_value):
    value = raw_value.strip()
    if value:
        return value
    else:
        raise ValueError("empty value %r" % (raw_value, ))


def main(inargs=None):
    # --firstname name      : persons first name
    # --lastname name       : persons last name
    # --account name        : account name. The owner of the account is changed
    parser = argparse.ArgumentParser(
        description="Set person name (override)",
    )
    parser.add_argument(
        '--firstname',
        required=True,
        type=nonempty_type,
    )
    parser.add_argument(
        '--lastname',
        required=True,
        type=nonempty_type,
    )
    parser.add_argument(
        '--account',
        dest='username',
        required=True,
        type=nonempty_type,
        metavar='username',
    )
    add_commit_args(parser.add_argument_group('Database'))
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    # TODO: Change to cronjob? Raise default log level?
    Cerebrum.logutils.autoconf('tee', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    dryrun = not args.commit

    person = get_person(db, args.username)
    change_person_name(db, person, args.firstname, args.lastname)

    dryrun = not args.commit
    if not dryrun:
        is_sure = ask_yn("Do you want to store these changes?")
        logger.info('Prompt response=%r', is_sure)
        dryrun = not is_sure

    if dryrun:
        logger.info('Rolling back changes')
        db.rollback()
        print("Abort (use --commit and answer Y to commit changes)")
    else:
        logger.info('Commiting changes')
        db.commit()
        print("Changes commited")
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
