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

from mx import DateTime

import cereconf
from Cerebrum import Errors, Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.ou_disk_mapping import utils
from Cerebrum.modules.ou_disk_mapping.dbal import OUDiskMapping

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


def update_account(db, pe, creator, new_trait=None, spreads=(), ignore_affs=(),
                   remove_quars=(), posix=False, home=None, home_auto=None):
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
    # Restore the _last_ expired account, if any:
    old_accounts = ac.search(owner_id=pe.entity_id, expire_start=None,
                             expire_stop=None)
    for row in sorted(old_accounts, key=itemgetter('expire_date'),
                      reverse=True):
        logger.info("Restore account %s for person %d", row['name'],
                    pe.entity_id)
        ac.find(row['account_id'])
        restore_account(db, pe, ac, remove_quars)
        break
    else:
        # no account found, create a new one
        names = ac.suggest_unames(pe)
        if len(names) < 1:
            logger.warn('Person %d has no name, skipping', pe.entity_id)
            return

        logger.info("Create account for person %d: %s", pe.entity_id, names[0])
        ac.populate(names[0],
                    co.entity_person,
                    pe.entity_id,
                    None,
                    creator.entity_id,
                    None)
        ac.write_db()

    if new_trait:
        logger.debug("Add trait to account %s: %s", ac.account_name, new_trait)
        ac.populate_trait(new_trait, date=DateTime.now())

    for s in spreads:
        logger.debug("Add spread to account %s: %s", ac.account_name, s)
        ac.add_spread(s)

    for row in set((row['affiliation'], row['ou_id']) for row in
                   pe.list_affiliations(person_id=pe.entity_id)
                   if (row['affiliation'] not in ignore_affs and row['status']
                       not in ignore_affs)):
        # This only iterates once per affiliation per OU, even if person has
        # several statuses for the same OU. Due to the account_type limit.
        affiliation, ou_id = row
        logger.debug("Give %s aff %s to ou_id=%s", ac.account_name,
                     co.PersonAffiliation(affiliation), ou_id)
        ac.set_account_type(affiliation=affiliation, ou_id=ou_id)

    ac.write_db()

    if posix:
        logger.debug("Add POSIX for account: %s", ac.account_name)
        pu = Factory.get('PosixUser')(db)
        pu.populate(posix_uid=pu.get_free_uid(),
                    gid_id=posix.get('dfg'),
                    gecos=None,
                    shell=co.posix_shell_bash,
                    parent=ac)
        pu.write_db()

    if home or home_auto:
        # Deal with home argument
        if home:
            disk_id = home['disk_id']
            home_spread = home['spread']
        # Deal with home_auto
        else:
            disk_mapping = OUDiskMapping(db)
            # Get highest precedent affiliation
            _, ou_id, aff, _, status, _, _, _, _ = pe.list_affiliations(
                pe.entity_id)[0]
            # Find the right disk id for this person
            if aff:
                aff = co.PersonAffiliation(aff)
            if status:
                status = co.PersonAffStatus(status)
            disk_id = utils.get_disk(
                db,
                disk_mapping,
                ou_id,
                aff,
                status,
                co.OUPerspective(cereconf.DEFAULT_OU_PERSPECTIVE))
            home_spread = home.get('spread', cereconf.DEFAULT_HOME_SPREAD)
        logger.debug("Set homedir for account %s to disk_id=%s",
                     ac.account_name, disk_id)
        homedir_id = ac.set_homedir(
            disk_id=disk_id,
            status=co.home_status_not_created)
        ac.set_home(home_spread, homedir_id)
        ac.write_db()


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
            remove_quars=(), posix=False, home=None, home_auto=None):
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

    for p_id in persons:
        logger.debug("Processing person_id=%d", p_id)
        pe.clear()
        pe.find(p_id)
        update_account(db, pe, creator, new_trait, spreads, ignore_affs,
                       remove_quars, posix, home, home_auto)


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
    parser.add_argument(
        '--posix-dfg',
        metavar='POSIXGROUP',
        help='POSIX GID - default file group')
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
    new_trait = int(co.EntityTrait(args.trait)) if args.trait else None
    spreads = [co.Spread(s) for s in args.spreads]
    ignore_affs = [str2aff(co, a) for a in args.ignore_affs]
    remove_quars = [co.Quarantine(q) for q in args.remove_quars]
    home = None
    if args.home_disk:
        home = {
            'spread': int(co.Spread(args.home_spread)),
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
            posix, home, args.home_auto)

    if args.commit:
        db.commit()
        logger.info("changes commited")
    else:
        db.rollback()
        logger.info("changes rolled back (dryrun)")

    logger.info("done")


if __name__ == '__main__':
    main()
