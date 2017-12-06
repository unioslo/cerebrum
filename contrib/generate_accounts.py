#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2012 University of Oslo, Norway
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
"""Script for creating accounts for all persons that matches given criterias.
If a person has previously had an account which is now deactivated, it will be
restored.

Note that a person will only get one account top. TBD: or should it be possible
to override this?

Note that the script does not update already existing accounts. This might be
the job for another script? We don't want this script to be too complex...

TODO: Whern restoring, the account does not get all the updates it should have.
Maybe we should have a Account.restore() method that takes care of this?

TODO: add functionality for only affecting new person affiliations instead,
e.g. only new employees from the last 7 days. This is usable e.g. for UiO.

"""

import argparse
from mx import DateTime

import cereconf
from Cerebrum import Errors, Constants
from Cerebrum.Utils import Factory


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


def update_account(db, pe, creator, new_trait=None):
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
    for row in ac.search(owner_id=pe.entity_id, expire_start=None,
                         expire_stop=None):
        logger.info("Restore account %s for person %d", row['name'],
                    pe.entity_id)
        ac.find(row['account_id'])
        if not ac.is_expired():
            logger.error("Account %s not expired anyway, it's a trap",
                         ac.account_name)
            return True
        ac.expire_date = None
        ac.write_db()
        # TODO: more 'recreate' settings here? Should we instead make use of a
        # Account.recreate() or something?
        break
    else:
        # no account found, create a new one
        name = (pe.get_name(co.system_cached, co.name_first),
                pe.get_name(co.system_cached, co.name_last))
        names = ac.suggest_unames(domain=co.account_namespace,
                                  fname=name[0],
                                  lname=name[1])
        if len(names) < 1:
            logger.warn('Person %d has no name, skipping', pe.entity_id)
            return False

        ac.populate(names[0],
                    co.entity_person,
                    pe.entity_id,
                    None,
                    creator.entity_id,
                    None)
        ac.write_db()

        for s in getattr(cereconf, 'BOFHD_NEW_USER_SPREADS', ()):
            ac.add_spread(int(co.Spread(s)))

        # Creating an initial password
        ac.set_password(ac.make_passwd(name))
        ac.write_db()

        logger.info("Account %s created for person %d", names[0], pe.entity_id)

    if new_trait:
        ac.populate_trait(new_trait, date=DateTime.now())

    # give the account all the person's affiliations
    for row in pe.list_affiliations(person_id=pe.entity_id):
        ac.set_account_type(ou_id=row['ou_id'], affiliation=row['affiliation'])
        ac.write_db()
        logger.debug("Gave %s aff %s to ou_id=%s", ac.account_name,
                     co.PersonAffiliation(row['affiliation']), row['ou_id'])
    return True


def personal_accounts(db):
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

    for row in ac.search(owner_type=co.entity_person):
        yield row['owner_id']


def process(db, affiliations, commit=False, new_trait=None):
    """Go through the database for new persons and give them accounts."""

    creator = Factory.get('Account')(db)
    creator.find(cereconf.INITIAL_ACCOUNTNAME)
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
        update_account(db, pe, creator, new_trait)


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

    if not affiliations:
        raise RuntimeError("No affiliations given")

    db.cl_init(change_program="generate_accounts")
    process(db, affiliations, args.commit, new_trait)

    if args.commit:
        db.commit()
        logger.info("changes commited")
    else:
        db.rollback()
        logger.info("changes rolled back (dryrun)")

    logger.info("done")


if __name__ == '__main__':
    main()
