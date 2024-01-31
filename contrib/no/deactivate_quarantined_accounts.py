#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2023 University of Oslo, Norway
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
Deactivate accounts with a given quarantine.

The criterias for deactivating accounts:

- The account must have an ACTIVE quarantine of the given type.

- The quarantine must have had a `start_date` from before the given number of
  days.

- If the account belongs to a person, it can not have any person affiliation.
  The script could be specified to ignore certain affiliations from this
  criteria.

- The account can't already be deleted.

Note that this script depends by default on `Account.deactivate()` for removal
of spreads, home directory etc. depending on what the institution needs. The
`deactivate` method must be implemented in the institution specific account
mixin - normally `Cerebrum/modules/no/$INST/Account.py` - before this script
would work.

The script also supports *deleting* (nuking) accounts instead of just
deactivating them. You should be absolutely sure before you run it with nuking,
as this deletes *all* the details around the user accounts, even its change
log.

Note: If a quarantine has been temporarily disabled, it would not be found by
this script. This would make it possible to let accounts live for a prolonged
period. This is a problem which should be solved in other ways, and not by this
script.
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
import textwrap

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError as BofhdError
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.utils import argutils
from Cerebrum.utils import date_compat

logger = logging.getLogger(__name__)


def get_default_operator_id(db):
    """ Get operator_id for bofhd_requests. """
    ac = Factory.get("Account")(db)
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return int(ac.entity_id)


def _fetch_quarantined_since(db, quarantine_types, start_before):
    """ Fetch quarantined accounts. """
    logger.debug("fetching accounts quarantined before %s ...", start_before)
    ac = Factory.get("Account")(db)
    accounts = set(
        row['entity_id']
        for row in ac.list_entity_quarantines(
            entity_types=ac.const.entity_account,
            quarantine_types=quarantine_types,
            only_active=True,
        )
        if date_compat.get_date(row['start_date']) <= start_before
    )
    logger.debug("found %d quarantined accounts", len(accounts))
    return accounts


def _fetch_deleted_accounts(db):
    """ Fetch all accounts already considered deleted/deactivated. """
    logger.debug("fetching deleted accounts ...")
    ac = Factory.get("Account")(db)
    accounts = set(int(row['account_id']) for row in ac.list_deleted_users())
    logger.debug("found %d deleted accounts", len(accounts))
    return accounts


def _fetch_affiliated_accounts(db, ignore_affs):
    """ Fetch all personal accounts of affiliated persons. """
    # prepare int tuples
    ignore_aff_t = set(
        (int(aff), None if status is None else int(status))
        for aff, status in ignore_affs)

    # find affilated persons
    logger.debug("fetching affiliated persons ...")
    pe = Factory.get("Person")(db)
    affiliated_persons = set(
        row['person_id']
        for row in pe.list_affiliations(include_deleted=False)
        if (int(row['affiliation']), None) not in ignore_aff_t
        and (int(row['affiliation']), int(row['status'])) not in ignore_aff_t)
    logger.debug("found %d affiliated persons", len(affiliated_persons))

    # find their active accounts
    logger.debug("fetching affiliated personal accounts ...")
    ac = Factory.get("Account")(db)
    accounts = set(
        int(row['account_id'])
        for row in ac.search(owner_type=ac.const.entity_person)
        if int(row['owner_id']) in affiliated_persons)
    logger.debug("found %d affiliated personal accounts", len(accounts))
    return accounts


def _fetch_system_accounts(db):
    """ Fetch all system accounts. """
    logger.debug("fetching system accounts ...")
    ac = Factory.get("Account")(db)
    accounts = set(
        int(row['account_id'])
        for row in ac.search(owner_type=ac.const.entity_group))
    logger.debug("found %d system accounts", len(accounts))
    return accounts


def fetch_target_accounts(db, quarantine_types, started_before, ignore_affs,
                          include_system_accounts):
    """
    Fetch all accounts that matches the criterias for deactivation.

    :param list quarantine_types:
        Quarantines to select

    :param datetime.date started_before:
        Select quarantines started before this date

    :type ignore_affs: set, list or tuple
    :param ignore_affs:
        A given list of `PersonAffiliationCode`. If given, we will ignore them,
        and process the persons' accounts as if they didn't have an
        affiliation, and could therefore be targeted for deactivation.

    :param bool include_system_accounts:
        If True, accounts owned by groups are also included in the resulting
        target list.

    :rtype: set
    :returns: The `entity_id` for all the accounts that match the criterias.

    """

    # Get quarantined accounts
    targets = _fetch_quarantined_since(db, quarantine_types, started_before)
    logger.info("Found %d quarantined targets", len(targets))
    if not targets:
        return targets

    # Remove deleted accounts, as they won't be processed anyway
    already_deleted = _fetch_deleted_accounts(db)
    targets -= already_deleted
    logger.info("Ignoring %d deleted accounts, %d remaining targets",
                len(already_deleted), len(targets))
    if not targets:
        return targets

    # Ignore accounts owned by persons with non-ignored affs
    affiliated_accounts = _fetch_affiliated_accounts(db, ignore_affs)
    targets -= affiliated_accounts
    logger.info("Ignoring %d affiliated accounts, %d remaining targets",
                len(affiliated_accounts), len(targets))
    if not targets:
        return targets

    if not include_system_accounts:
        # remove system accounts from targets
        system_accounts = _fetch_system_accounts(db)
        targets -= system_accounts
        logger.info("Ignoring %d system accounts, %d remaining targets",
                    len(system_accounts), len(targets))

    return targets


def process_account(account, operator_id, terminate=False, use_request=False):
    """ Deactivate the given account.

    :param Cerebrum.Account: The account that should get deactivated.

    :param bool terminate:
        If True, the account will be totally deleted instead of just
        deactivated.

    :param bool use_request:
        If True, the account will be given to BofhdRequest for further
        processing. It will then not be deactivated by this script.

    :rtype: bool
    :returns: If the account really got deactivated/deleted.

    """
    db = account._db
    const = account.const
    account_repr = "%s (%d)" % (account.account_name, account.entity_id)

    if account.is_deleted():
        logger.warning("Account %s already deleted", account_repr)
        return False

    logger.debug("Processing account %s", account_repr)

    if terminate:
        account.terminate()
        logger.info("Terminated %s", account_repr)
        return True

    if use_request:
        br = BofhdRequests(db, const)
        try:
            reqid = br.add_request(
                operator=operator_id,
                when=br.now,
                op_code=const.bofh_delete_user,
                entity_id=int(account.entity_id),
                destination_id=None,
            )
            logger.info("Queued delete request for %s: request_id=%r",
                        account_repr, reqid)
            return True
        except BofhdError as e:
            # TODO: This *should* probably be a Cerebrum.Errors.CerebrumError,
            # but we'd need to rewrite error handling everywhere else...
            logger.warn("Unable to queue request for %s: %s", account_repr,  e)
            return False

    account.deactivate()
    logger.info("Deactivated %s", account_repr)
    return True


def _iter_csv_arg(values):
    """
    Iterate over values in list arguments.

    This is used to get individual items from arguments that have
    action=append, but can also be comma-separated.
    """
    for raw_value in (values or ()):
        for item in raw_value.split(","):
            item = item.strip()
            if item:
                yield item


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Deactivate all accounts where given quarantine has been set for at
            least DAYS.

            Accounts will NOT be deactivated by default if their persons are
            registered with affiliations, or if the account is a system
            account, i.e. owned by a group and not a person.

            {}
            """
        ).strip().format(__doc__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    arg_quarantines = parser.add_argument(
        "-q", "--quarantines",
        action='append',
        help=textwrap.dedent(
            """
            Quarantine types to select accounts for deactivation.  Multiple
            quarantines can be given by repeating the argument, or by giving a
            comma-separated list.  Defaults to 'generell' if no quarantines are
            given.
            """
        ).strip(),
        metavar="QUAR",
    )
    parser.add_argument(
        "-s", "--since",
        default=30,
        type=int,
        help=textwrap.dedent(
            """
            Number of days since quarantine started (default: %(default)s)
            """
        ).strip(),
        metavar="DAYS",
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        help=textwrap.dedent(
            """
            Limit number of deactivations by the script (default: %(default)s)
            """
        ).strip(),
        metavar="LIMIT",
    )
    parser.add_argument(
        "--bofhdrequest",
        dest="use_bofhd_request",
        action="store_true",
        default=False,
        help=textwrap.dedent(
            """
            Use BofhdRequest for deactivation.  If specified, instead of
            deactivating the account directly, it is handed over to
            BofhdRequest for further processing.  This is needed e.g. when we
            need to archive the home directory before the account gets
            deactivated.
           """
        ).strip(),
    )
    arg_affiliations = parser.add_argument(
        "-a", "--affiliations",
        action='append',
        help=textwrap.dedent(
            """
            List of affiliations that will be ignored (not considered active).
            Values can be affiliations (e.g. MANUELL), or statuses (e.g.
            TILKNYTTET/fagperson).  Multiple values can be given by repeating
            the arugment, or by giving a comma-separated list.
           """
        ).strip(),
        metavar="AFFS",
    )
    parser.add_argument(
        "--include-system-accounts",
        action="store_true",
        default=False,
        help="Deactivate system accounts as well",
    )
    parser.add_argument(
        "--terminate",
        action="store_true",
        default=False,
        help=textwrap.dedent(
            """
            *Delete* the account instead of just deactivating it.  Warning:
            This deletes *everything* about the accounts with active
            quarantines, even their logs.  This can not be undone, so use with
            care!
           """
        ).strip(),
    )
    # TODO: default should be False
    argutils.add_commit_args(parser, default=True)
    Cerebrum.logutils.options.install_subparser(parser)

    #
    # Prepare arguments
    #
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    with argutils.ParserContext(parser, arg_quarantines):
        quarantine_types = [
            const.get_constant(const.Quarantine, v)
            for v in _iter_csv_arg(args.quarantines)]

    if not quarantine_types:
        quarantine_types = [const.quarantine_generell]

    with argutils.ParserContext(parser, arg_affiliations):
        ignore_affs = set(const.get_affiliation(aff)
                          for aff in _iter_csv_arg(args.affiliations))

    started_before = (datetime.date.today()
                      - datetime.timedelta(days=args.since))

    pretty_quarantines = ", ".join(six.text_type(q) for q in quarantine_types)
    pretty_ignores = ", ".join(six.text_type(st) if st else six.text_type(aff)
                               for aff, st in ignore_affs)
    pretty_mode = ("terminate" if args.terminate
                   else "bofhd-request" if args.use_bofhd_request
                   else "deactivate")

    logger.info("Start deactivation: quarantines=%s, start=%s, ignore=%s, "
                "mode=%s, limit=%s", pretty_quarantines, started_before,
                pretty_ignores, pretty_mode, args.limit)

    #
    # Fetch and process
    #
    db.cl_init(change_program="deactivate-qua")
    operator_id = get_default_operator_id(db)

    logger.info("Fetching relevant accounts ...")
    to_deactivate = fetch_target_accounts(
        db,
        quarantine_types=quarantine_types,
        started_before=started_before,
        ignore_affs=ignore_affs,
        include_system_accounts=args.include_system_accounts,
    )
    logger.info("Found %d accounts to process", len(to_deactivate))

    ac = Factory.get("Account")(db)

    num_deactivated = 0
    for entity_id in to_deactivate:
        if args.limit and num_deactivated >= args.limit:
            logger.info("Reached limit (%d) of deactivations, stopping",
                        args.limit)
            break

        try:
            ac.clear()
            ac.find(entity_id)
        except Cerebrum.Errors.NotFoundError:
            logger.warn("Could not find account_id=%r, skipping", entity_id)
            continue

        try:
            if process_account(ac, operator_id,
                               terminate=args.terminate,
                               use_request=args.use_bofhd_request):
                num_deactivated += 1
        except Exception:
            logger.error("Failed deactivating account: %s (%s)",
                         ac.account_name, ac.entity_id, exc_info=True)
            continue

    logger.info("Deactivated %d accounts", num_deactivated)

    if args.commit:
        logger.info("Commiting changes")
        db.commit()
    else:
        logger.info("Rolling back changes (dryrun)")
        db.rollback()

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
