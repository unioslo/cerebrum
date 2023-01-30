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
from Cerebrum.utils.date import parse_date

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
    max_attempts = 10
    get_retry_delay = delay_on_error

    def __init__(self):
        pass

    def handle_task(self, db, task):
        id_type, _, id_value = task.key.partition(":")
        if id_type != "entity-id":
            raise ValueError("Invalid task key: " + repr(task.key))

        entity_id = int(id_value)
        expire_date = task.payload.data.get('expire_date')
        if expire_date:
            expire_date = parse_date(expire_date)
        else:
            expire_date = None
        update_greg_person(db, entity_id, expire_date)

    @classmethod
    def new_task(cls, entity_id, affiliations=None, expire_date=None):
        key = "entity-id:{}".format(int(entity_id))
        if expire_date:
            expire_date = expire_date.isoformat()
        else:
            expire_date = None
        return task_models.Task(
            queue=cls.queue,
            sub="",
            key=key,
            attempts=0,
            nbf=None,
            payload=task_models.Payload(
                fmt='greg-person-update',
                version=1,
                data={
                    'expire_date': expire_date,
                },
            ),
        )


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


def get_location_code(ou):
    """ Get location code (stedkode) for a given OU. """
    # TODO: Maybe make this a generic function somewhere?  It'll probably be
    # useful elsewhere as we move from mod_stedkode to entity_external_id for
    # this value.
    ou_id = ou.entity_id

    sko_values = set()
    for row in ou.get_external_id(id_type=ou.const.externalid_location_code):
        sko_values.add(row['external_id'])

    if len(sko_values) < 1:
        logger.warning("No location code for ou_id=%s", repr(ou_id))
        return None

    if len(sko_values) > 1:
        # TODO: Should maybe select the best match based on source system
        # (SYSTEM_LOOKUP_ORDER?) and return that?
        logger.warning("Multiple location codes for ou_id=%s (%s)",
                       repr(ou_id), repr(sko_values))
        return None

    return sko_values.pop()


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
        yield (
            int(row['account_id']),
            date_compat.get_date(row['expire_date']),
        )


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
            ou = get_ou_by_id(db, ou_id)
        except Errors.NotFoundError:
            logger.debug("Ignoring aff for person id=%s to ou_id=%s (missing)",
                         person_id, ou_id)
            continue
        except EntityExpiredError:
            logger.debug("Ignoring aff for person id=%s to ou_id=%s (expired)",
                         person_id, ou_id)
            continue

        location_code = get_location_code(ou)
        if not location_code:
            logger.debug("Ignoring aff for person id=%s to ou_id=%s "
                         "(no location code)", person_id, ou_id)
            continue

        yield status, ou_id, location_code


def promote_posix(account):
    """ Ensure account is a posix account object. """
    db = account._db
    co = Factory.get('Constants')(db)
    pu = Factory.get('PosixUser')(db)

    try:
        pu.find(int(account.entity_id))
        logger.debug("Account id=%r is already a PosixUser",
                     account.entity_id)
        return False
    except Errors.NotFoundError:
        # Missing posix promote
        pu.clear()

    uid = pu.get_free_uid()
    shell = co.posix_shell_bash
    group_id = int(get_posix_group(db).entity_id)
    try:
        pu.populate(uid, group_id, None, shell, parent=account)
        pu.write_db()
    except Exception:
        # TODO: This should probably not be handled here...
        logger.error("Unable to posix promote account %s (id=%s)",
                     repr(account.account_name), repr(account.entity_id),
                     exc_info=True)
        return False

    # only gets here if posix user created successfully
    logger.info("Promoted account %s (id=%s) to posix (uid=%s)",
                repr(account.account_name), repr(account.entity_id), repr(uid))
    return True


def populate_account_affiliations(account, affiliations):
    """
    Assert that the account has the given affiliations.

    :type account: Cerebrum.Account.Account
    :param affiliations: sequence of aff tuples (aff-status, ou-id, sko)
    """
    db = account._db
    current_account_affs = []
    current_person_affs = tuple((affst.affiliation, ou_id)
                                for affst, ou_id, _ in affiliations)

    for row in account.list_accounts_by_type(account_id=int(account.entity_id),
                                             filter_expired=False):
        # TODO: We should probably just remove any invalid account-aff here?
        #
        # TODO: Alternatively, if we don't want to clean up, we don't really
        # need to look up the ou_id here, as any not-found/expired shouldn't
        # occur in the person_affs tuple anyway?  And if it does we wouldn't
        # want to add it?
        try:
            get_ou_by_id(db, row['ou_id'])
        except Errors.NotFoundError:
            logger.debug("Ignoring account aff for account %s (id=%s) "
                         " to ou_id=%s (missing)",
                         repr(account.account_name), repr(account.entity_id),
                         repr(row['ou_id']))
            continue
        except EntityExpiredError:
            logger.debug("Ignoring account aff for account %s (id=%s) "
                         " to ou_id=%s (expired)",
                         repr(account.account_name), repr(account.entity_id),
                         repr(row['ou_id']))
            continue

        current_account_affs.append((int(row['affiliation']),
                                     int(row['ou_id'])))

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


def _needs_exchange(affiliations):
    """ Check if collection of affiliations qualifies for exchange. """
    could_have_exchange = False
    location_codes = tuple(aff[2] for aff in affiliations)

    for code in location_codes:
        # No external codes should have exchange spread, except GENØK (999510)
        # and AK (999620) and KUNN (999410) and NorgesUniv (921000)
        if (code[0:2] != '99'
                or code[0:6] in ('999510', '999620', '999410', '921000')):
            could_have_exchange = True

    # Run through exchange employee filter
    # TODO: This is weird: Ask UiT how this is supposed to work?
    #       This will never happen...
    #       `and not could_have_exchange` -> `could_have_exchange = False`
    for code in location_codes:
        for skofilter in cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO:
            if (skofilter == code[0:len(skofilter)]
                    and not could_have_exchange):
                logger.info("Skipping exchange spread for sko=%r", code)
                return False

    return could_have_exchange


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
    :param affiliations: sequence of aff tuples (aff-status, ou-id, sko)
    """
    spreads = set((const.spread_uit_ldap_system,))

    aff_statuses = tuple(affst for affst, _, _ in affiliations)

    for status in aff_statuses:
        # One of the things in the affiliation list is MANUELL/gjest_u_konto
        # No spreads (other than the *one* everybody gets...
        if status == const.affiliation_manuell_gjest_u_konto:
            return spreads

    for status in aff_statuses:
        aff_string = six.text_type(status)
        for spread in SPREAD_MAP.get(aff_string, ()):
            spreads.add(const.get_constant(const.Spread, spread))

    # Check if the affiliations from System-X qualifies for exchange_mailbox
    # spread
    #
    # TODO: Move _needs_exchange logic here when we figure out how it *should*
    # work?
    if (const.spread_uit_ad_account in spreads
            and _needs_exchange(affiliations)):
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
        return None

    greg_id = get_greg_id(person)
    if greg_id:
        logger.debug("Person id=%r has greg-id=%r", person_id, greg_id)
    else:
        logger.error("No greg-id for person id=%r", person_id)
        return None

    # sequence of (aff-status, ou-id, location-code) tuples from greg
    current_affs = tuple(get_greg_affiliations(person))
    if not current_affs:
        logger.error("No valid greg affiliations for person id=%r", person_id)
        return None

    # Check if person is deceased - set new_expire_date if this is the case
    deceased_date = date_compat.get_date(person.deceased_date)

    # sequence of account_id, expire_date for this person
    # that *could* be used as guest/greg/system-x account
    # (account-id, expire_date) pairs
    accounts = tuple(get_candidate_accounts(person))
    need_new_account = len(accounts) < 1

    # TODO: OK to ignore deceased persons without user accounts?
    # Check with UiT...
    if need_new_account and deceased_date:
        logger.warning("Person id=%r is deceased, nothing to do", person_id)
        return None

    #
    # create or find account
    #
    if need_new_account:
        account = create_account(person, default_expire_date=today)
        account_id = account.entity_id
        current_expire_date = date_compat.get_date(account.expire_date)
    else:
        # TODO: Should we try harder to find an existing account with guest
        # roles that looks like they come from Greg if there are more than one?
        #
        # - maybe prioritize accounts that have already been posix-promoted?
        # - maybe use a trait on person -> target_id=account to identify
        # previous greg account?
        account_id, current_expire_date = accounts[0]
        account.find(account_id)

        if not current_expire_date:
            # Safeguard - set an expire date if we find an account without
            # expire date...
            account.expire_date = current_expire_date = today
            account.write_db()
        # ensure posix account
        promote_posix(account)

    logger.info("%s account %r (id=%r) for person id=%r",
                "Created" if need_new_account else "Found",
                account.account_name, account.entity_id,
                person.entity_id)

    #
    # update expire date
    #
    # TODO: One caveat here - if a person is deceased, we won't neccessarily
    # have any updates from Greg that triggers this logic...  Maybe add a job
    # for UiT that checks for deceased-date and terminates (sets updated
    # expire-date) for accounts?  That should be fairly simple and
    # straight-forward...
    logger.debug("Dates for account %r (id=%r): "
                 "deceased=%s current-expire=%s new-expire=%s",
                 account.account_name, account.entity_id,
                 deceased_date, current_expire_date, new_expire_date)

    new_deceased = False
    if deceased_date:
        new_expire_date = deceased_date
        if current_expire_date != new_expire_date:
            logger.warning("person_id=%s is deceased (%s)",
                           person_id, new_expire_date)
            new_deceased = True

    # TODO: OK to ignore missing new_expire_date?  Check with UiT...
    if ((new_expire_date and (new_expire_date > today)
         and (new_expire_date > current_expire_date))
            or new_deceased):
        # If new expire is later than current expire then update expire
        logger.info("Updating expire-date for account %r (id=%r): %s -> %s",
                    account.account_name, account.entity_id,
                    current_expire_date, new_expire_date)
        account.expire_date = new_expire_date
        account.write_db()

    # account types
    populate_account_affiliations(account, current_affs)

    # get all person affiliations. Need em to calculate correct spread
    #
    # TODO: Figure out how to calculate this properly?
    #
    # 1. Multiple affs - what if a person has both
    #    affiliation_manuell_gjest_u_konto and another aff?
    #
    # 2. Why even have info on guest *without* account?
    #
    # 3. Will Greg even have any roles that maps to this aff?
    #
    # For now, assume if the guest have *any* affs of this type, we should
    # abort...

    # make sure all spreads defined in sysX is set

    # everybody gets this one:
    #
    # TODO: select spreads from role?  To replace spreads from system-x...
    need_spreads = calculate_greg_spreads(const, current_affs)

    # Set spread expire date
    # Use new_expire_date in order to guarantee that SystemX specific spreads
    # get SystemX specific expiry_dates
    for spread in need_spreads:
        # TODO: Set expire date for spreads?
        #
        # Note: We set expire date here for spreads that may already be in
        # place from other systems, not only the spreads that we end up adding!
        # This has two consequences - we may *prolong* spread expire for
        # existing spreads, but we may also end up *shortening* spread expire!
        #
        # TODO: Maybe only set expire date if it *adds* an expire date, or
        # *prolongs* a current expire date?
        account.set_spread_expire(entity_id=int(account.entity_id),
                                  spread=spread,
                                  expire_date=new_expire_date)

    # TODO: Fix sync? Should we ever *remove* any spreads? Should we select a
    # set of "managed" spreads?
    current_spreads = set(const.get_constant(const.Spread, row['spread'])
                          for row in account.get_spread())
    spreads_to_add = need_spreads - current_spreads
    for spread in spreads_to_add:
        account.add_spread(spread)
        account.set_home_dir(spread)

    # check quarantine
    #
    # TODO: Should we ever *add* any quarantines?  E.g. if greg-data is
    # removed?  Could bundle a quarantine-flag in the task when removing greg
    # data from person?  Ask UiT about this quarantine...
    #
    # TODO: We should probably remove any system-x quarantines on new, enabled
    # users here...  Check with UiT?
    quarantines_to_remove = set((
        const.quarantine_sys_x_approved,
    ))

    for row in list(account.get_entity_quarantine()):
        q_type = const.get_constant(const.Quarantine, row['quarantine_type'])
        if q_type in quarantines_to_remove:
            logger.info("Removing quarantine %s from account %r (id=%r)",
                        q_type, account.account_name, account.entity_id)
            account.delete_entity_quarantine(q_type)
