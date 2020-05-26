#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012, 2018 University of Oslo, Norway
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

""" Make sure people with given affiliations have an account.

The use case is to automatically create accounts for new employee.

Supports restoring previously terminated accounts.

Note: Existing accounts are not updated. This script's job is done after the
creation.

TODO: add functionality for only affecting new person affiliations instead,
e.g. only new employees from the last 7 days? This is usable e.g. for UiO.

"""

import argparse
from operator import itemgetter

import cereconf

from Cerebrum import Errors, Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.AccountPolicy import AccountPolicy

logger = Factory.get_logger('cronjob')


def str2aff(co, affstring):
    """Get a string with an affiliation or status and return its constant."""
    aff = affstring.split('/', 1)
    if len(aff) > 1:
        aff = co.PersonAffStatus(aff[0], aff[1])
    else:
        aff = co.PersonAffiliation(affstring)
    try:
        int(aff)
    except Errors.NotFoundError:
        raise Exception("Unknown affiliation: %s" % affstring)
    return aff


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


def get_account_types(pe, ignore_affs):
    affiliations = []
    for row in set((row['affiliation'], row['ou_id']) for row in
                   pe.list_affiliations(person_id=pe.entity_id)
                   if (row['affiliation'] not in ignore_affs and row['status']
                       not in ignore_affs)):
        # This only iterates once per affiliation per OU, even if person has
        # several statuses for the same OU. Due to the account_type limit.
        affiliation, ou_id = row
        affiliations.append({'affiliation': affiliation, 'ou_id': ou_id})
    return affiliations


def get_gid(posix, posix_uio):
    if posix and not posix_uio:
        return posix.get('dfg')
    return None


def update_account(db, pe, account_policy, creator, new_trait=None, spreads=(),
                   ignore_affs=(), remove_quars=(), posix=False, home=None,
                   home_auto=None, posix_uio=False):
    """Make sure that the given person has an active account. It the person has
    no accounts, a new one will be created. If the person already has an
    account it will be 'restored'.

    Note that we here assume that a person only should have one account
    automatically created.

    This function must only be called if a person does not have an active
    account.

    """
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    affiliations = get_account_types(pe, ignore_affs)
    disks = (home,) if home else ()
    # Some logging
    logger.debug("Will add trait: %s to account", new_trait)
    logger.debug("Will add spreads: %s to account",
                 ", ".join(str(i) for i in spreads))
    # Log stedkode if ou has stedkode mixin
    ou = Factory.get('OU')(db)
    for affiliation in affiliations:
        stedkode = "UNKNOWN"
        if hasattr(ou, 'get_stedkode'):
            ou.clear()
            ou.find(affiliation['ou_id'])
            stedkode = ou.get_stedkode()
        logger.debug("Will give account aff %s@%s (ou_id=%s)",
                     co.PersonAffiliation(affiliation['affiliation']),
                     stedkode,
                     affiliation['ou_id'])
    if posix:
        logger.debug("Will add POSIX for account")
    if home or home_auto:
        logger.debug("Will add homedir for account")

    # Restore the _last_ expired account, if any:
    old_accounts = ac.search(owner_id=pe.entity_id, expire_start=None,
                             expire_stop=None)
    for row in sorted(old_accounts, key=itemgetter('expire_date'),
                      reverse=True):
        ac.find(row['account_id'])
        restore_account(db, pe, ac, remove_quars)
        try:
            account_policy.update_account(
                pe,
                ac.entity_id,
                affiliations,
                disks,
                None,
                traits=(new_trait, ) if new_trait else (),
                spreads=spreads,
                make_posix_user=posix,
                gid=get_gid(posix, posix_uio),
                shell=co.posix_shell_bash,
                ou_disk=home_auto
            )
        except Errors.InvalidAccountCreationArgument as e:
            logger.error(e)
        else:
            logger.info("Restored account %s for person %d",
                        row['name'],
                        pe.entity_id)
        return
    # no account found, create a new one
    try:
        account = account_policy.create_personal_account(
            pe,
            affiliations,
            disks,
            None,
            creator.entity_id,
            traits=(new_trait,) if new_trait else (),
            spreads=spreads,
            make_posix_user=posix,
            gid=get_gid(posix, posix_uio),
            shell=co.posix_shell_bash,
            ou_disk=home_auto
        )
    except Errors.InvalidAccountCreationArgument as e:
        logger.error(e)
    else:
        logger.info("Created account %s for person %d",
                    account.account_name,
                    pe.entity_id)


def personal_accounts(db):
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    for row in ac.search(owner_type=co.entity_person):
        yield row['owner_id']


def get_disk(db, path):
    disk = Factory.get('Disk')(db)
    try:
        disk.find_by_path(path)
    except Errors.NotFoundError:
        raise Exception("Unknown disk: %s" % path)
    return disk.entity_id


def get_posixgroup(db, groupname):
    pg = Factory.get('PosixGroup')(db)
    try:
        pg.find_by_name(groupname)
    except Errors.NotFoundError:
        raise Exception("Unknown POSIX group: %s" % groupname)
    return pg.entity_id


def process(db, affiliations, new_trait=None, spreads=(), ignore_affs=(),
            remove_quars=(), posix=False, home=None, home_auto=None,
            posix_uio=None):
    """Go through the database for new persons and give them accounts."""

    creator = Factory.get('Account')(db)
    creator.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    logger.debug('Creator: {0} ({1})'.format(creator.account_name,
                                             creator.entity_id))

    logger.debug('Caching existing accounts')
    has_account = set(personal_accounts(db))
    logger.debug("%d people already have an active account" % len(has_account))

    pe = Factory.get('Person')(db)

    # sort by affiliation and status
    statuses = tuple(af for af in affiliations
                     if isinstance(af, Constants._PersonAffStatusCode))
    affs = tuple(af for af in affiliations
                 if isinstance(af, Constants._PersonAffiliationCode))

    persons = set()
    if statuses:
        persons.update(row['person_id'] for row in
                       pe.list_affiliations(status=statuses)
                       if row['person_id'] not in has_account)
    if affs:
        persons.update(row['person_id'] for row in
                       pe.list_affiliations(affiliation=affs)
                       if row['person_id'] not in has_account)
    logger.debug("Found %d persons without an account", len(persons))

    account_policy = AccountPolicy(db)
    for p_id in persons:
        logger.debug("Processing person_id=%d", p_id)
        pe.clear()
        pe.find(p_id)
        update_account(db, pe, account_policy, creator, new_trait, spreads,
                       ignore_affs, remove_quars, posix, home, home_auto,
                       posix_uio)


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
        dest='trait',
        metavar='TRAITNAME',
        help='If set, gives every new account the given trait. '
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
        help='Affiliations to NOT copy from person to new account. '
             'Can be comma separated. ')
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
    posix_dfg = parser.add_mutually_exclusive_group()
    posix_dfg.add_argument(
        '--posix-dfg',
        metavar='POSIXGROUP',
        help='POSIX GID - default file group')
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
        help='Actually commit the work. The default is dryrun.')
    return parser


def main(inargs=None):
    parser = make_parser()
    args = parser.parse_args(inargs)

    logger.info("start ({0})".format(__file__))
    logger.debug(repr(args))

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    # Lookup stuff
    affiliations = [str2aff(co, a) for a in args.affs]
    new_trait = co.EntityTrait(args.trait) if args.trait else None
    spreads = [co.Spread(s) for s in args.spreads]
    ignore_affs = [str2aff(co, a) for a in args.ignore_affs]
    remove_quars = [co.Quarantine(q) for q in args.remove_quars]

    # Verify as valid constants
    int(new_trait)
    for i in spreads:
        int(i)
    for i in remove_quars:
        int(i)

    home = {}
    if args.home_disk:
        home = {
            'home_spread': int(co.Spread(args.home_spread)),
            'disk_id': get_disk(db, args.home_disk),
        }
    posix = {}
    if args.with_posix:
        posix['enabled'] = True
        if args.posix_dfg:
            posix['dfg'] = get_posixgroup(db, args.posix_dfg)

    if not affiliations:
        raise RuntimeError("No affiliations given")

    db.cl_init(change_program="generate_accounts")
    process(db, affiliations, new_trait, spreads, ignore_affs, remove_quars,
            posix, home, args.home_auto, args.posix_uio)

    if args.commit:
        db.commit()
        logger.info("changes commited")
    else:
        db.rollback()
        logger.info("changes rolled back (dryrun)")

    logger.info("done")


if __name__ == '__main__':
    main()
