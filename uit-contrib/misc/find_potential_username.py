#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.legacy_users import LegacyUsers
from Cerebrum.modules.no.uit.Account import UsernamePolicy
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def store_user(db, uname, ssn, name):
    """Reserve username in the LegacyUsers table"""
    type = 'P'  # personal
    source = "MANUAL"
    lu = LegacyUsers(db)
    lu.set(uname, ssn=ssn, source=source, type=type)


# Account type (Employee/Student) to cstart mapping
cstart_map = {
    'E': 0,
    'S': 0,
}


def generate_username(db, person_name, account_type):
    """Generate a new username"""
    cstart = cstart_map[account_type]
    name_gen = UsernamePolicy(db)
    inits = name_gen.get_initials(person_name)
    username = name_gen.get_serial(inits, cstart)
    logger.info("Generated username=%r", username)
    return username


def check_username(db, username):
    """Check if a given username is free"""
    account = Factory.get('Account')(db)
    try:
        account.find_by_name(username)
    except Errors.NotFoundError:
        logger.info("Username %r vacant", username)
        return True
    else:
        logger.error("Username %r taken", username)
        return False


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


def nonempty_type(raw_value):
    value = raw_value.strip()
    if value:
        return value
    else:
        raise ValueError("empty value %r" % (raw_value, ))


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Calculate a (and reserve) a username",
    )
    parser.add_argument(
        '-n', '--name',
        required=True,
        type=nonempty_type,
        help='full name of person',
    )
    parser.add_argument(
        '-s', '--ssn',
        required=True,
        type=nonempty_type,
        help='ssn (fødselsnummer) of person',
    )
    uname_grp = parser.add_argument_group(
        'Username',
        'Choose to supply a username or to have one generated automatically',
    )
    uname_mutex = uname_grp.add_mutually_exclusive_group(required=True)
    uname_mutex.add_argument(
        '-t', '--type',
        dest='account_type',
        type=lambda v: v.upper(),
        choices=tuple(cstart_map.keys()),
        help='Generate username for a [S]tudent or [E]mployee account',
    )
    uname_mutex.add_argument(
        '-u', '--uname',
        type=nonempty_type,
        help='Use the given username',
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

    dryrun = not args.commit

    if args.uname:
        if check_username(db, args.uname):
            username = args.uname
        else:
            raise SystemExit("Username %r is taken!" % (args.uname, ))
        logger.info("Reserving username=%r (given by user)", username)
    else:
        username = generate_username(db, args.name, args.account_type)
        logger.info("Reserving username=%r (generated)", username)

    print("Name:", args.name)
    print("SSN:", args.ssn)
    print("Username:", username)
    store_user(db, username, args.ssn, args.name)

    if not dryrun:
        is_sure = ask_yn("Are you sure you want to reserve this username?")
        logger.info('Prompt response=%r', is_sure)
        dryrun = not is_sure

    if dryrun:
        logger.info('Rolling back changes')
        db.rollback()
        print("Abort (use --commit and answer Y to commit changes)")
    else:
        logger.info('Commiting changes')
        db.commit()
        print("Changes commited, don't forget to notify SUT (paal) "
              "about the new user")
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
