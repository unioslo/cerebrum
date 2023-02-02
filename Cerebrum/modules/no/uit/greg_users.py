# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
Account maintenance for Greg users at UiT.

This module adds a task queue and task processing to create and update user
accounts for guests at UiT.  The greg person import should queue a new
greg-user-update task each time a person is updated from Greg, and a script
should then process these tasks regularly.

The user maintenance is mostly a re-implementation of functions from
`contrib/no/uit/process_systemx.py`.

"""
import datetime
import logging

import six

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import backoff
from Cerebrum.utils import date_compat
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks import queue_handler
from Cerebrum.modules.no.uit import POSIX_GROUP_NAME
from Cerebrum.modules.no.uit.Account import UsernamePolicy
from Cerebrum.utils import transliterate
from Cerebrum.utils import date as date_utils

logger = logging.getLogger(__name__)


delay_on_error = backoff.Backoff(
    backoff.Exponential(2),
    backoff.Factor(datetime.timedelta(hours=1) / 8),
    backoff.Truncate(datetime.timedelta(hours=12)),
)


class UitGregUserUpdateHandler(queue_handler.QueueHandler):
    """
    Queue and task processing for guest user accounts at UiT.
    """

    queue = 'greg-user-update'
    manual_sub = 'manual'
    max_attempts = 10
    get_retry_delay = delay_on_error

    payload_format = 'greg-expire-date'
    payload_version = 1

    def __init__(self):
        pass

    @classmethod
    def _create_payload(cls, expire_date=None):
        """ Create a task payload with the given expire date. """
        if expire_date:
            expire_date = expire_date.isoformat()
        else:
            expire_date = None
        return task_models.Payload(
            fmt=cls.payload_format,
            version=cls.payload_version,
            data={'expire_date': expire_date},
        )

    @classmethod
    def _extract_payload(cls, payload):
        """ Extract expire-date from a task payload. """
        if not payload:
            raise ValueError("No payload")
        if payload.format != cls.payload_format:
            raise ValueError("Wrong payload format: %r (expected %r)"
                             % (payload.format, cls.payload_format))
        if payload.version != cls.payload_version:
            raise ValueError("Wrong payload version: %r (expected %r)"
                             % (payload.version, cls.payload_version))

        if payload.data['expire_date']:
            return date_utils.parse_date(payload.data['expire_date'])
        return None

    @classmethod
    def create_task(cls, person_id, expire_date=None, sub="", reason=""):
        """ Helper - create a new greg-user-update task. """
        key = "id:{}".format(int(person_id))
        return task_models.Task(
            queue=cls.queue,
            sub=sub,
            key=key,
            nbf=date_utils.now(),
            attempts=0,
            reason=reason,
            payload=cls._create_payload(expire_date),
        )

    @classmethod
    def create_manual_task(cls, person_id, expire_date=None):
        """ Create a manual task. """
        return cls.create_task(person_id, expire_date=expire_date,
                               sub=cls.manual_sub, reason="manually added")

    def handle_task(self, db, task):
        # task key to person-id
        id_type, _, id_value = task.key.partition(":")
        if id_type != "id":
            raise ValueError("Invalid task key: " + repr(task.key))
        entity_id = int(id_value)

        # task payload to expire-date
        try:
            expire_date = self._extract_payload(task.payload)
        except Exception as e:
            logger.warning("Invalid payload in task %s: %s", task, e)
            expire_date = None

        # create or update user account for the given person
        update_greg_person(db, entity_id, expire_date)


def get_creator(db):
    """ Get default creator for new accounts. """
    creator = Factory.get("Account")(db)
    creator.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return creator


def get_posix_group(db):
    """ Get the default posix group at UiT. """
    group = Factory.get('Group')(db)
    group.find_by_name(POSIX_GROUP_NAME)
    return group


def get_ou_by_id(db, ou_id):
    """ Get OU object by id. """
    ou = Factory.get('OU')(db)
    ou.find(int(ou_id))
    return ou


def get_greg_id(person):
    """ Get greg-id for a given person object, if it exists. """
    const = person.const
    for row in person.get_external_id(id_type=const.externalid_greg_pid,
                                      source_system=const.system_greg):
        return row['external_id']
    return None


def get_candidate_accounts(person):
    """ Get candidate accounts for a given person. """
    db = person._db
    account = Factory.get("Account")(db)
    for row in account.search(owner_id=int(person.entity_id),
                              expire_start=None):
        if row['name'][3:6] == "999":
            # "Admin" account
            continue
        if UsernamePolicy.is_valid_sito_name(row['name']):
            # Sito account
            continue
        yield int(row['account_id'])


def get_person_name(person):
    """ Get the full name of a given person. """
    const = person.const
    try:
        return person.get_name(const.system_cached, const.name_full)
    except Errors.NotFoundError:
        logger.warning("No authoritative full name for person id=%r",
                       person.entity_id)
        return ""


def get_greg_affiliations(person):
    """ Get all current, active Greg affiliations for a given person. """
    db = person._db
    const = person.const
    person_id = int(person.entity_id)
    for row in person.get_affiliations():
        if row['source_system'] != const.system_greg:
            continue
        # aff = const.get_constant(const.PersonAffiliation, row['affiliation'])
        status = const.get_constant(const.PersonAffStatus, row['status'])
        ou_id = int(row['ou_id'])

        try:
            get_ou_by_id(db, ou_id)
        except Errors.NotFoundError:
            logger.debug("Ignoring aff for person id=%s to ou_id=%s (missing)",
                         person_id, ou_id)
            continue
        except EntityExpiredError:
            logger.debug("Ignoring aff for person id=%s to ou_id=%s (expired)",
                         person_id, ou_id)
            continue

        yield status, ou_id


def promote_posix(account):
    """ Ensure account is a posix account object. """
    db = account._db
    co = Factory.get('Constants')(db)
    pu = Factory.get('PosixUser')(db)

    try:
        pu.find(int(account.entity_id))
        logger.debug("Account %s (id=%s) is already a posix user (uid=%s)",
                     repr(account.account_name), repr(account.entity_id),
                     repr(pu.posix_uid))
        return pu
    except Errors.NotFoundError:
        # Missing posix promote
        pu.clear()

    uid = pu.get_free_uid()
    shell = co.posix_shell_bash
    group_id = int(get_posix_group(db).entity_id)
    pu.populate(uid, group_id, None, shell, parent=account)
    pu.write_db()
    logger.info("Promoted account %s (id=%s) to posix (uid=%s)",
                repr(account.account_name), repr(account.entity_id), repr(uid))
    return pu


def populate_account_affiliations(account, affiliations):
    """
    Assert that the account has the given affiliations.

    :type account: Cerebrum.Account.Account
    :param affiliations: sequence of aff tuples (aff-status, ou-id)
    """
    current_person_affs = tuple(
        (affst.affiliation, ou_id)
        for affst, ou_id in affiliations)

    current_account_affs = tuple(
        (int(row['affiliation']), int(row['ou_id']))
        for row in account.list_accounts_by_type(
            account_id=int(account.entity_id),
            filter_expired=False))

    to_add = []
    for aff, ou_id in current_person_affs:
        if (int(aff), int(ou_id)) not in current_account_affs:
            to_add.append((aff, ou_id))

    for aff, ou_id in to_add:
        logger.info("Adding aff to account %s (id=%s): %s @ ou id=%s",
                    repr(account.account_name), repr(account.entity_id),
                    aff, ou_id)
        account.set_account_type(ou_id, aff)

    # Note: This function will not remove any account affs - this needs to be
    # handled manually, if needed...

    return tuple(to_add)


def create_account(owner, default_expire_date):
    """ Create a new posix account. """
    db = owner._db
    const = owner.const

    creator_id = int(get_creator(db).entity_id)
    dfg_id = int(get_posix_group(db).entity_id)
    logger.info("Creating account for person id=%r", owner.entity_id)

    account = Factory.get('PosixUser')(db)
    uname = account.suggest_unames(owner)[0]
    full_name = get_person_name(owner)

    account.populate(
        name=uname,
        owner_id=owner.entity_id,
        owner_type=const.entity_person,
        np_type=None,
        creator_id=creator_id,
        expire_date=default_expire_date,
        posix_uid=account.get_free_uid(),
        gid_id=dfg_id,
        gecos=transliterate.for_posix(full_name),
        shell=const.posix_shell_bash,
    )

    password = account.make_passwd(uname)
    account.set_password(password)
    account.write_db()

    return account


#
# TODO: Update spread map
#
# This assumes that the Greg roles maps one-to-one with affiliations - if two
# or more roles map to the *same* affiliation in Cerebrum, but needs
# *different* spreads, then we'll need to re-work this mapping and
# `calculate_greg_spreads`.
#
# If this is the case, we'll also need additional information from Greg on
# which roles the owner has.
#
SPREAD_MAP = {
    'TILKNYTTET/emeritus': ('people@ldap', 'system@ldap'),
    'MANUELL/gjest': ('people@ldap', 'system@ldap', 'cristin@uit'),
    'TILKNYTTET/fagperson': ('AD_account',),
}
# spread_list = [
#     co.spread_uit_ldap_people,
#     co.spread_uit_fronter_account,
#     co.spread_uit_ldap_system,
#     co.spread_uit_ad_account,
#     co.spread_uit_cristin,
#     co.spread_uit_exchange,
# ]


def calculate_greg_spreads(const, affiliations):
    """
    Get selection of spreads to add from affiliations.

    :type const: Cerebrum.Constants.ConstantsBase
    :param affiliations: sequence of aff tuples (aff-status, ou-id)
    """
    spreads = set((const.spread_uit_ldap_system,))

    for aff_status, _ in affiliations:
        aff_string = six.text_type(aff_status)
        for spread in SPREAD_MAP.get(aff_string, ()):
            spreads.add(const.get_constant(const.Spread, spread))

    # Exchange-spread follows AD-spread.
    if const.spread_uit_ad_account in spreads:
        spreads.add(const.spread_uit_exchange)

    return spreads


def update_greg_person(db, person_id, new_expire_date, _today=None):
    """
    Update accounts for a given person.

    :type db: Cerebrum.database.Database
    :param int person_id:
        person to update
    :param date new_expire_date:
        expire date for the greg account / greg data
    :param date _today:
        override the current date (e.g. in tests for exprire checks, etc...)
    """
    today = _today or datetime.date.today()
    const = Factory.get("Constants")(db)
    person = Factory.get("Person")(db)
    account = Factory.get("Account")(db)

    logger.info("Processing person id=%r", person_id)
    try:
        person.find(person_id)
    except Errors.NotFoundError:
        logger.error("Invalid person id=%r", person_id)
        # We return None here to mark execution as a success.  There's nothing
        # we can do for a non-existing person.
        return None

    greg_id = get_greg_id(person)
    if greg_id:
        logger.debug("Person id=%r has greg-id=%r", person_id, greg_id)
    else:
        logger.error("No greg-id for person id=%r", person_id)
        # We return None here to mark execution as a success.  There's nothing
        # we can do for a person that has never had any info from Greg.
        return None

    # sequence of (aff-status, ou-id) tuples from greg
    current_affs = tuple(get_greg_affiliations(person))

    # Check if person is deceased in Cerebrum
    deceased_date = date_compat.get_date(person.deceased_date)

    # sequence of account_id, expire_date for this person
    # that *could* be used as guest/greg/system-x account
    # (account-id, expire_date) pairs
    accounts = tuple(get_candidate_accounts(person))
    if len(accounts) > 1:
        raise RuntimeError("Too many accounts for person id=%r: %r",
                           person_id, accounts)

    if len(accounts) < 1 and deceased_date:
        # Deceased owner, and no accounts - there's nothing more to do
        logger.warning("Person id=%r is deceased w/ no accounts: ignoring",
                       person_id)
        return None

    if len(accounts) < 1 and not current_affs:
        logger.warning("Person id=%r has no affs and no accounts: ignoring",
                       person_id)
        # Inactive owner, and no accounts - there's nothing more to do
        return None

    #
    # create or find account
    #
    if len(accounts) < 1:
        account = create_account(person, default_expire_date=today)
        account_id = account.entity_id
        current_expire_date = date_compat.get_date(account.expire_date)
        new_account = True
    else:
        account_id = accounts[0]
        account.find(account_id)
        if account.expire_date:
            current_expire_date = date_compat.get_date(account.expire_date)
        else:
            # Set an initial expire date if we somehow find an account
            # without...
            account.expire_date = current_expire_date = today
            account.write_db()
        promote_posix(account)
        new_account = False

    logger.info("%s account %r (id=%r) for person id=%r",
                "Created" if new_account else "Found",
                account.account_name, account.entity_id,
                person.entity_id)

    #
    # update expire date
    #
    logger.debug("Dates for account %r (id=%r): "
                 "deceased=%s current-expire=%s new-expire=%s",
                 account.account_name, account.entity_id,
                 deceased_date, current_expire_date, new_expire_date)

    # Note: If a person is deceased, we won't neccessarily have any updates
    # from Greg that triggers this logic...  Either a manual task must be added
    # to update the user account, *or* the user account must be expired
    # manually.
    new_deceased = False
    if deceased_date:
        new_expire_date = deceased_date
        if current_expire_date != new_expire_date:
            logger.warning("person_id=%s is deceased (%s)",
                           person_id, new_expire_date)
            new_deceased = True

    # Expire date is updated if:
    #
    # 1. Person is deceased, and the user account *isn't* expired
    # 2. We get a new expire date in the future, *and* the expire date is
    #    further into the future than the current expire date
    #
    if ((new_expire_date and (new_expire_date > today)
         and (new_expire_date > current_expire_date))
            or new_deceased):
        logger.info("Updating expire-date for account %r (id=%r): %s -> %s",
                    account.account_name, account.entity_id,
                    current_expire_date, new_expire_date)
        account.expire_date = new_expire_date
        account.write_db()

    populate_account_affiliations(account, current_affs)

    if new_expire_date:
        need_spreads = calculate_greg_spreads(const, current_affs)
    else:
        # Without an expire-date to work with, we don't want to add any spreads
        # or deal with spread-expire.
        need_spreads = set()

    # Ensure spreads added by this logic has an expire date
    #
    # Note: We set expire date here for spreads that may already be in
    # place from other systems, not only the spreads that we end up adding!
    # This has two consequences - we may *prolong* spread expire for
    # existing spreads, but we may also end up *shortening* spread expire!
    #
    # TODO: Maybe only set expire date if it *adds* an expire date, or
    # *prolongs* a current expire date?
    for spread in need_spreads:
        account.set_spread_expire(entity_id=int(account.entity_id),
                                  spread=spread,
                                  expire_date=new_expire_date)

    current_spreads = set(const.get_constant(const.Spread, row['spread'])
                          for row in account.get_spread())
    spreads_to_add = need_spreads - current_spreads
    for spread in spreads_to_add:
        account.add_spread(spread)
        account.set_home_dir(spread)
