#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2023 University of Oslo, Norway
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
Create or restore accounts for affiliated persons.

This script ensures that all affiliated persons (according to the input
argument selection) has an active user acocunt.  This is typically used to
create or restore user accounts for employees and other, affiliated persons.

Note: Existing user accounts are not currently updated.

Future improvements
-------------------
Add functionality for only affecting new person affiliations instead, e.g. only
new employees from the last 7 days?

Move certain routines into a reusable module (e.g. create_account,
restore_account).

Consolidate and refactor *all* account create, restore, and disable
functionality.  Maybe change the AccountGenerator into a AccountSettings
object, and move into AccountPolicy?

Maybe replace script with event-based account creation?
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import logging

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.AccountPolicy import AccountPolicy
from Cerebrum.utils import date_compat

logger = logging.getLogger(__name__)


def get_account_by_name(db, name):
    account = Factory.get("Account")(db)
    account.find_by_name(name)
    return account


def get_person_by_id(db, person_id):
    person = Factory.get("Person")(db)
    person.find(person_id)
    return person


def get_disk_by_path(db, path):
    disk = Factory.get("Disk")(db)
    disk.find_by_path(path)
    return disk


def get_posix_group_by_name(db, name):
    pg = Factory.get("PosixGroup")(db)
    pg.find_by_name(name)
    return pg


class AccountGenerator(object):
    """ Account generator with settings from CLI.  """

    def __init__(self,
                 db,
                 creator,
                 new_traits=None,
                 spreads=None,
                 remove_quarantines=None,
                 posix_promote=True,
                 posix_dfg=None,
                 home_disks=None,
                 home_auto=None):
        """
        :type db: Cerebrum.database.Database
        :type creator: Cerebrum.Account.Account

        :type new_traits: collections[.abc].Collection
        :param new_traits:
            Traits to give to new or restored accounts.

        :type new_traits: collections[.abc].Collection
        :param collection new_traits:
            Spreads to give to new or restored accounts.

        :type remove_quarantines: collections[.abc].Collection
        :param remove_quarantines:
            Quarantines to remove from restored accounts.

        :param bool posix_promote:
            If new or restored accounts should be posix accounts

        :type posix_dfg: Cerbrum.modules.PosixGroup.PosixGroup
        :param posix_dfg:
            Use this common default file group for posix accounts.  If no
            common group is given, posix users will get a personal file group.

        :type home_disks: list<dict>
        :param home_disks:
            A list with disks to create homedirs on.

            Each item is a dict with {'disk_id': <id>, 'home_spread': <spread>}

        :param bool home_auto:
            Automatically find disk for homedirs from affiliations.
        """
        self.db = db
        self.creator = creator
        self.new_traits = new_traits or ()
        self.spreads = spreads or ()
        self.remove_quarantines = remove_quarantines or ()
        self.posix_promote = posix_promote
        self.posix_dfg = posix_dfg

        self.auto_disk = home_auto
        if home_auto:
            self.disks = ()
        else:
            self.disks = home_disks or ()

        self.account_policy = AccountPolicy(db)

    def __call__(self, person, affiliations):
        """
        Make sure that the given person has an active account.

        It the person has no accounts, a new one will be created. If the person
        already has an account it will be 'restored'.

        Note that we here assume that a person only should have one account
        automatically created.
        """
        logger.debug("Processing person_id=%d", person.entity_id)

        co = Factory.get("Constants")(self.db)
        ac = Factory.get("Account")(self.db)

        # TODO: This should probably be logged by AccountPolicy create/update?
        for affiliation in affiliations:
            logger.debug("using account aff %s @ ou_id=%s for person_id=%s",
                         affiliation['affiliation'],
                         affiliation['ou_id'],
                         person.entity_id)

        # Restore the _last_ expired account, if any:
        old_accounts = ac.search(owner_id=person.entity_id,
                                 expire_start=None,
                                 expire_stop=None)

        if self.posix_promote and self.posix_dfg:
            posix_gid = self.posix_dfg.entity_id
        else:
            posix_gid = None

        def _safe_date_sort_key(row):
            expire_date = date_compat.get_date(row['expire_date'])
            if expire_date:
                return expire_date
            # No expire date, but we need a date for sorting.  Let's return a
            # date far far into the future.  This generally *won't* happen, as
            # we only process persons with expired accounts, but that may
            # change in the future.
            return datetime.date.max

        for row in sorted(old_accounts,
                          key=_safe_date_sort_key,
                          reverse=True):
            ac.find(row['account_id'])
            restore_account(self.db, person, ac, self.remove_quarantines)
            try:
                self.account_policy.update_account(
                    person=person,
                    account_id=ac.entity_id,
                    affiliations=affiliations,
                    disks=self.disks,
                    expire_date=None,
                    traits=self.new_traits,
                    spreads=self.spreads,
                    make_posix_user=self.posix_promote,
                    gid=posix_gid,
                    shell=co.posix_shell_bash,
                    ou_disk=self.auto_disk,
                )
            except Errors.InvalidAccountCreationArgument as e:
                logger.error(e)
            else:
                logger.info("Restored account %s (%d) for person id=%d",
                            ac.account_name,
                            ac.entity_id,
                            person.entity_id)
            return

        # no account found, create a new one
        try:
            account = self.account_policy.create_personal_account(
                person=person,
                affiliations=affiliations,
                disks=self.disks,
                expire_date=None,
                creator_id=self.creator.entity_id,
                traits=self.new_traits,
                spreads=self.spreads,
                make_posix_user=self.posix_promote,
                gid=posix_gid,
                shell=co.posix_shell_bash,
                ou_disk=self.auto_disk,
            )
        except Errors.InvalidAccountCreationArgument as e:
            logger.error(e)
        except ValueError:
            # Temporary fix: username issue
            logger.error('Unable to create account for person id=%d',
                         person.entity_id, exc_info=True)
        else:
            logger.info("Created account %s (%d) for person id=%d",
                        account.account_name,
                        account.entity_id,
                        person.entity_id)


def restore_account(db, pe, ac, remove_quars):
    """Restore a previously expired account.

    The account is cleaned from previous details, to avoid e.g. getting IT
    privileges from the account's previous life.

    TODO: This functionality should be moved to a Cerebrum module.

    """
    if not ac.is_expired():
        logger.error("Account %s not expired anyway, it's a trap",
                     ac.account_name)
        return
    ac.expire_date = None
    ac.write_db()

    existing_quars = [row['quarantine_type'] for row in
                      ac.get_entity_quarantine(only_active=True)]
    for q in remove_quars:
        if int(q) in existing_quars:
            ac.delete_entity_quarantine(q)

    for row in ac.get_spread():
        ac.delete_spread(row['spread'])

    for row in ac.get_account_types(filter_expired=False):
        ac.del_account_type(row['ou_id'], row['affiliation'])

    ac.write_db()

    pu = Factory.get('PosixUser')(db)
    try:
        pu.find(ac.entity_id)
    except Errors.NotFoundError:
        pass
    else:
        pu.delete_posixuser()

    gr = Factory.get('Group')(db)
    for row in gr.search(member_id=ac.entity_id):
        gr.clear()
        gr.find(row['group_id'])
        gr.remove_member(ac.entity_id)
        gr.write_db()

    # TODO: remove old passwords


def personal_accounts(db):
    ac = Factory.get('Account')(db)
    for row in ac.search(owner_type=ac.const.entity_person):
        yield row['owner_id']


def select_persons(db, include_affs, exclude_affs, source_systems=None):
    """
    Collect matching persons and their matching affiliations.

    :returns dict:
        Mapping of person-id to a set of (affiliation, ou-id) tuples.
    """
    pe = Factory.get("Person")(db)

    persons = {}
    # TODO: Santiy check - we shouldn't be able to ignore something we
    # explicitly select. I.e. none of the exclude items should fully cancel out
    # any of the include items.
    #
    # Examples that *shouldn't* be allowed:
    #  - include=ANSATT        exclude=ANSATT
    #  - include=ANSATT/tekadm exclude=ANSATT
    #  - include=ANSATT/tekadm exclude=ANSATT/tekadm
    exclude_set = set(int(aff if st is None else st)
                      for aff, st in (exclude_affs or ()))

    for aff, st in include_affs:
        for row in pe.list_affiliations(affiliation=aff, status=st,
                                        source_system=source_systems):
            if row['affiliation'] in exclude_set:
                # Ignore this affiliation type (why is this even an option?)
                continue
            if row['status'] in exclude_set:
                # Ignore this affiliation status
                continue
            if row['person_id'] not in persons:
                persons[row['person_id']] = set()
            persons[row['person_id']].add((row['affiliation'], row['ou_id']))
    return persons


def process(generate_account, affiliations, ignore_affs, source_systems):
    """Go through the database for new persons and give them accounts."""
    db = generate_account.db

    logger.debug("caching persons and accounts...")
    persons = select_persons(db, affiliations, ignore_affs, source_systems)
    logger.debug("found %d matching persons", len(persons))

    has_account = set(personal_accounts(db))
    logger.debug("found %d persons with an active account", len(has_account))

    needs_account = set(persons) - set(has_account)
    logger.info("found %d matching persons without account",
                len(needs_account))

    for person_id in needs_account:
        person = get_person_by_id(db, person_id)
        # The AccountPolicy needs a list of dicts on this format for adding
        # account_type:
        affiliations = [
            {
                'affiliation': aff,
                'ou_id': ou_id,
            } for aff, ou_id in persons[person_id]
        ]
        generate_account(person, affiliations)


class ExtendAction(argparse.Action):
    """ Like the 'append'-action, but uses `list.extend`.

    This means that the `type` argument should be set to something that returns
    a sequence of items to add to the namespace value.
    """

    def __init__(self, option_strings, dest, default=None, type=None,
                 required=False, help=None, metavar=None):
        super(ExtendAction, self).__init__(option_strings=option_strings,
                                           dest=dest, nargs=None, const=None,
                                           default=default or [], type=type,
                                           choices=None, required=required,
                                           help=help, metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, [])[:]
        items.extend(values)
        setattr(namespace, self.dest, items)


def make_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--aff',
        dest='affs',
        required=True,
        action=ExtendAction,
        type=lambda arg: arg.split(','),
        metavar='AFFILIATIONS',
        help='Only persons with the given affiliations and/or '
             'statuses will get an account. Can be comma separated. '
             'Example: "ANSATT,TILKNYTTET/ekstern,STUDENT/fagperson"')
    parser.add_argument(
        '--new-trait',
        dest='traits',
        action=ExtendAction,
        type=lambda arg: arg.split(','),
        metavar='TRAITNAMES',
        help='If set, gives every new account the given trait(s). '
             'Usable e.g. for sending a welcome SMS for every new account.')
    parser.add_argument(
        '--spread',
        dest='spreads',
        action=ExtendAction,
        type=lambda arg: arg.split(','),
        metavar='SPREADS',
        help='Spreads to add to new accounts. Can be comma separated.')
    parser.add_argument(
        '--ignore-affs',
        action=ExtendAction,
        type=lambda arg: arg.split(','),
        metavar='AFFILIATIONS',
        help='Affiliations and/or statuses that will not generate accounts '
             'on their own, and also will not be copied from person to new '
             'account even if the person has other affiliations. Can be comma '
             'separated. Example: "ANSATT/bilag,MANUELL"')
    parser.add_argument(
        '--remove-quarantines',
        dest='remove_quars',
        action=ExtendAction,
        type=lambda arg: arg.split(','),
        metavar='QUARANTINE',
        help='Quarantines to removes when restoring old accounts. '
             'Avoid automatic quarantines.')
    parser.add_argument(
        '--with-posix',
        action='store_true',
        default=False,
        help='Add default POSIX data to new accounts.')
    parser.add_argument(
        '--source-systems',
        dest='source_systems',
        action=ExtendAction,
        type=lambda arg: arg.split(','),
        help='Specify source system from which to generate accounts. '
             'If none given, all source systems will be considered.')
    posix_dfg = parser.add_mutually_exclusive_group()
    posix_dfg.add_argument(
        '--posix-dfg',
        metavar='POSIXGROUP',
        help='POSIX GID - default file group')
    # TODO: posix uio has no real effect - by *not* giving a posix-dfg, we'll
    # get this behaviour.  This is just a sanity check, remove?
    posix_dfg.add_argument(
        '--posix-uio',
        action='store_true',
        default=False,
        help="Use the default setup for UiO to set dfg for posix users"
    )
    parser.add_argument(
        '--home-spread',
        metavar='SPREAD',
        default=cereconf.DEFAULT_HOME_SPREAD,
        help='The spread for the new home directory. Defaults to '
             'cereconf.DEFAULT_HOME_SPREAD')
    homedir = parser.add_mutually_exclusive_group()
    homedir.add_argument(
        '--home-disk',
        metavar='PATH',
        help="Path to disk to put new accounts' home directory")
    homedir.add_argument(
        '--home-auto',
        action='store_true',
        help="Set homedir automatically using the OU Disk Mapping module"
    )
    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help='Actually commit the work. The default is dryrun.',
    )

    Cerebrum.logutils.options.install_subparser(parser)

    return parser


def main(inargs=None):
    parser = make_parser()
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    #
    # check and prepare cli arguments
    #
    affiliations = tuple(co.get_affiliation(a) for a in (args.affs or ()))
    logger.info("affiliations to select: %s",
                tuple(six.text_type(a if s is None else s)
                      for a, s in affiliations))

    ignore_affs = tuple(co.get_affiliation(a)
                        for a in (args.ignore_affs or ()))
    logger.info("affiliations to ignore: %s",
                tuple(six.text_type(a if s is None else s)
                      for a, s in ignore_affs))

    if args.source_systems:
        source_systems = tuple(co.get_constant(co.AuthoritativeSystem, s)
                               for s in args.source_systems)
        _source_systems_repr = tuple(six.text_type(s) for s in source_systems)
    else:
        source_systems = None
        _source_systems_repr = "*"
    logger.info("source systems to consider: %s", _source_systems_repr)

    new_traits = tuple(co.get_constant(co.EntityTrait, t)
                       for t in (args.traits or ()))
    logger.info("traits to add: %r",
                tuple(six.text_type(t) for t in new_traits))

    spreads = tuple(co.get_constant(co.Spread, value)
                    for value in (args.spreads or ()))
    logger.info("spreads to add: %r",
                tuple(six.text_type(s) for s in spreads))

    remove_quars = tuple(co.get_constant(co.Quarantine, q)
                         for q in (args.remove_quars or ()))
    logger.info("quarantines to remove: %r",
                tuple(six.text_type(t) for t in remove_quars))

    home_disks = []
    if args.home_disk:
        home_disk = get_disk_by_path(db, args.home_disk)
        home_spread = co.get_constant(co.Spread, args.home_spread)
        home_disks.append({
            'home_spread': home_spread,
            'disk_id': home_disk.entity_id
        })
        logger.info("home-disk: %s (%d), spread: %s",
                    home_disk.path, home_disk.entity_id,
                    six.text_type(home_spread))
    elif args.home_auto:
        logger.info("home-disk: %s", "auto")
    else:
        logger.info("home-disk: %s", "none")

    if args.home_auto and home_disks:
        raise RuntimeError("home-auto has no effect when home-disk is given")

    if args.posix_dfg and not args.with_posix:
        raise RuntimeError("posix-dfg has no effect without posix promote")
    elif args.posix_uio and not args.with_posix:
        raise RuntimeError("posix-uio has no effect without posix promote")
    elif args.posix_dfg:
        posix_dfg = get_posix_group_by_name(db, args.posix_dfg)
    else:
        posix_dfg = None
    logger.info("with-posix: %s (dfg: %s)",
                args.with_posix, posix_dfg.group_name if posix_dfg else None)

    if not affiliations:
        raise RuntimeError("No affiliations given")

    #
    # find candidates and build accounts
    #
    db.cl_init(change_program="generate_accounts")

    creator = get_account_by_name(db, cereconf.INITIAL_ACCOUNTNAME)
    logger.info("creator: %s (%d)",
                creator.account_name, creator.entity_id)

    account_generator = AccountGenerator(
        db=db,
        creator=creator,
        new_traits=new_traits,
        spreads=spreads,
        remove_quarantines=remove_quars,
        posix_promote=args.with_posix,
        posix_dfg=posix_dfg,
        home_disks=home_disks,
        home_auto=args.home_auto)

    process(account_generator, affiliations, ignore_affs, source_systems)

    if args.commit:
        db.commit()
        logger.info("changes committed")
    else:
        db.rollback()
        logger.info("changes rolled back (dryrun)")

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
