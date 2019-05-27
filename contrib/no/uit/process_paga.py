#! /usr/bin/env python
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
"""
Process accounts for Paga employees.

This script creates accounts for all persons in Cerebrum that has the correct
employee affiliations and:

- assigns account affiliations
- assigns default spreads
- creates email address
- creates homedir

Configuration
-------------
The following cereconf values affects the Paga account maintenance:

INITIAL_ACCOUNTNAME
    Creator of Paga accounts.

USERNAME_POSTFIX['sito']
    Postfix that identifies Sito accounts (we don't touch sito accounts).

EMPLOYEE_SPREADLIST
    A list of spreads to load (and maintain) for Paga accounts.

EMPLOYEE_DEFAULT_SPREADS
    A list of default spreads for Paga accounts.

EMPLOYEE_FILTER_EXCHANGE_SKO
    A list of stedkode codes to exclude from exchange spreads.
"""
import argparse
import datetime
import logging
import os
import xml.sax

import mx.DateTime
import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.argutils import ParserContext
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)


class PagaDataParser(xml.sax.ContentHandler):
    """
    This class is used to iterate over all users in PAGA.
    """
    # TODO: Move this to Cerebrum.modules.no.uit.PagaDataParser

    def __init__(self, filename, callback):
        self.callback = callback
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):  # noqa: N802
        if name == 'data':
            pass
        elif name in ("tils", "gjest", "permisjon"):
            pass
        elif name == "person":
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = six.text_type(attrs[k])
        else:
            logger.warning('Unknown element %r (attrs: %r)',
                           name, attrs.keys())

    def endElement(self, name):  # noqa: N802
        if name == "person":
            self.callback(self.p_data)


# TODO: Combine duplicated code from import_sito, import_paga, other imports
# (ExistingAccount, ExistingPerson, get_existing_accounts, _handle_changes,
# ...)

class ExistingAccount(object):

    def __init__(self, id_type, id_value, uname, expire_date):
        self._affs = list()
        self._new_affs = list()
        self._expire_date = expire_date
        self._id_type = id_type
        self._id_value = id_value
        self._owner_id = None
        self._uid = None
        self._home = dict()
        self._quarantines = list()
        self._spreads = list()
        self._traits = list()
        self._email = None
        self._uname = uname
        self._gecos = None

    def append_affiliation(self, affiliation, ou_id, priority):
        self._affs.append((affiliation, ou_id, priority))

    def append_new_affiliations(self, affiliation, ou_id):
        self._new_affs.append((affiliation, ou_id, None))

    def append_quarantine(self, q):
        self._quarantines.append(q)

    def append_spread(self, spread):
        self._spreads.append(spread)

    def append_trait(self, trait_code, trait_str):
        self._traits.append((trait_code, trait_str))

    def get_affiliations(self):
        return self._affs

    def get_new_affiliations(self):
        return self._new_affs

    def get_email(self):
        return self._email

    def get_expire_date(self):
        return self._expire_date

    def get_external_id(self):
        return self._id_value

    def get_external_id_type(self):
        return self._id_type

    def set_external_id(self, id_type, id_value):
        self._id_type, self._id_value = id_type, id_value

    def get_gecos(self):
        return self._gecos

    def get_posix(self):
        return self._uid

    def get_home(self, spread):
        return self._home.get(spread, (None, None))

    def get_home_spreads(self):
        return self._home.keys()

    def get_quarantines(self):
        return self._quarantines

    def get_spreads(self):
        return self._spreads

    def get_traits(self):
        return self._traits

    def get_uname(self):
        return self._uname

    def has_affiliation(self, aff_cand):
        return aff_cand in [aff for aff, ou in self._affs]

    def has_homes(self):
        return len(self._home) > 0

    def set_email(self, email):
        self._email = email

    def set_posix(self, uid):
        self._uid = uid

    def set_gecos(self, gecos):
        self._gecos = gecos

    def set_home(self, spread, home, homedir_id):
        self._home[spread] = (homedir_id, home)


class ExistingPerson(object):

    def __init__(self, person_id=None):
        self._affs = list()
        self._groups = list()
        self._spreads = list()
        self._accounts = list()
        self._primary_accountid = None
        self._personid = person_id
        self._fullname = None
        self._deceased_date = None

    def append_account(self, acc_id):
        self._accounts.append(acc_id)

    def append_affiliation(self, affiliation, ou_id, status):
        self._affs.append((affiliation, ou_id, status))

    def append_group(self, group_id):
        self._groups.append(group_id)

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_affiliations(self):
        return self._affs

    def get_new_affiliations(self):
        return self._new_affs

    def get_fullnanme(self):
        return self._full_name

    def get_groups(self):
        return self._groups

    def get_personid(self):
        return self._personid

    def get_primary_account(self):
        if self._primary_accountid:
            return self._primary_accountid[0]
        else:
            return self.get_account()

    def get_spreads(self):
        return self._spreads

    def has_account(self):
        return len(self._accounts) > 0

    def get_account(self):
        return self._accounts[0]

    def set_primary_account(self, ac_id, priority):
        if self._primary_accountid:
            old_id, old_pri = self._primary_accountid
            if priority < old_pri:
                self._primary_accountid = (ac_id, priority)
        else:
            self._primary_accountid = (ac_id, priority)

    def set_personid(self, id):
        self._personid = id

    def set_fullname(self, full_name):
        self._fullname = full_name

    def set_deceased_date(self, deceased_date):
        self._deceased_date = deceased_date

    def get_deceased_date(self):
        return self._deceased_date


@memoize
def get_creator_id(db):
    const = Factory.get('Constants')(db)
    entity_name = Entity.EntityName(db)
    entity_name.find_by_name(cereconf.INITIAL_ACCOUNTNAME,
                             const.account_namespace)
    id = entity_name.entity_id
    return id


@memoize
def get_sko(db, ou_id):
    ou = Factory.get('OU')(db)
    try:
        ou.find(ou_id)
    except Errors.NotFoundError:
        # Persons has an affiliation to a non-fs ou.
        # Return NoneNoneNone
        return None
    try:
        return "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
    except AttributeError:
        # OU without SKO?
        return None


def get_expire_date():
    """ calculate a default expire date
    Take into consideration that we do not want an expiredate
    in the general holiday time in Norway
    """
    today = mx.DateTime.today()
    ff_start = mx.DateTime.DateTime(today.year, 6, 15)
    ff_slutt = mx.DateTime.DateTime(today.year, 8, 15)
    nextmonth = today + mx.DateTime.DateTimeDelta(30)

    # ikke sett default expire til en dato i fellesferien
    if nextmonth > ff_start and nextmonth < ff_slutt:
        # fellesferien. Bruk 1 sept istedet.
        return mx.DateTime.DateTime(today.year, 9, 1)
    else:
        return nextmonth


def get_existing_accounts(db):
    """
    Get persons that comes from Paga and their accounts.
    """
    const = Factory.get('Constants')(db)
    person = Factory.get('Person')(db)
    account_obj = Factory.get('Account')(db)

    logger.info("Loading persons...")
    person_cache = {}
    account_cache = {}
    pid2fnr = {}
    pid2passnr = {}

    # getting deceased persons
    deceased = person.list_deceased()

    # Get ExistingPerson objects by ssn
    for row in person.search_external_ids(
            id_type=const.externalid_fodselsnr,
            source_system=const.system_paga,
            fetchall=False):
        p_id = int(row['entity_id'])
        key = (int(const.externalid_fodselsnr), row['external_id'])
        if p_id not in pid2fnr:
            pid2fnr[p_id] = row['external_id']
            person_cache[key] = ExistingPerson(person_id=p_id)
            if p_id in deceased:
                person_cache[key].set_deceased_date(deceased[p_id])
        del p_id, key

    # Get remaining ExistingPerson objects by passport number
    for row in person.search_external_ids(
            id_type=const.externalid_pass_number,
            source_system=const.system_paga,
            fetchall=False):
        p_id = int(row['entity_id'])
        key = (int(const.externalid_pass_number), row['external_id'])
        if p_id not in pid2fnr and p_id not in pid2passnr:
            pid2passnr[p_id] = row['external_id']
            person_cache[key] = ExistingPerson(person_id=p_id)
            logger.debug("Using passport id for person_id=%r", p_id)
            if p_id in deceased:
                person_cache[key].set_deceased_date(deceased[p_id])
        del p_id, key

    logger.info("Loading person affiliations...")
    for row in person.list_affiliations(source_system=const.system_paga,
                                        fetchall=False):
        p_id = int(row['person_id'])
        if p_id in pid2fnr:
            key = (int(const.externalid_fodselsnr), pid2fnr[p_id])
        elif p_id in pid2passnr:
            key = (int(const.externalid_pass_number), pid2fnr[p_id])
        else:
            key = None

        if key is not None:
            person_cache[key].append_affiliation(
                int(row['affiliation']),
                int(row['ou_id']),
                int(row['status']))
        del p_id, key

    logger.info("Loading accounts...")
    sito_postfix = cereconf.USERNAME_POSTFIX['sito']
    for row in account_obj.search(expire_start=None):
        a_id = int(row['account_id'])
        id_type = id_value = None
        if not row['owner_id']:
            continue
        if int(row['owner_id']) in pid2fnr:
            id_type = const.externalid_fodselsnr
            id_value = pid2fnr[int(row['owner_id'])]
        elif int(row['owner_id']) in pid2passnr:
            id_type = const.externalid_pass_number
            id_value = pid2passnr[int(row['owner_id'])]
        else:
            continue
        if row['name'].endswith(sito_postfix):
            # this is a sito account, do not process as part of uit employees
            logger.debug("Omitting account id=%r (%s), sito account",
                         a_id, row['name'])
            continue
        account_cache[a_id] = ExistingAccount(id_type, id_value, row['name'],
                                              row['expire_date'])
        del a_id

    # Posixusers
    logger.info("Loading posixinfo...")
    posix_user_obj = PosixUser.PosixUser(db)
    for row in posix_user_obj.list_posix_users():
        a_obj = account_cache.get(int(row['account_id']), None)
        if a_obj is not None:
            a_obj.set_posix(int(row['posix_uid']))
        del a_obj

    # quarantines
    logger.info("Loading account quarantines...")
    for row in account_obj.list_entity_quarantines(
            entity_types=const.entity_account):
        a_obj = account_cache.get(int(row['entity_id']), None)
        if a_obj is not None:
            a_obj.append_quarantine(int(row['quarantine_type']))
        del a_obj

    # Spreads
    logger.info("Loading spreads... %r ", cereconf.EMPLOYEE_SPREADLIST)
    spread_list = [int(const.Spread(x)) for x in cereconf.EMPLOYEE_SPREADLIST]
    for spread_id in spread_list:
        is_account_spread = is_person_spread = False
        spread = const.Spread(spread_id)
        if spread.entity_type == const.entity_account:
            is_account_spread = True
        elif spread.entity_type == const.entity_person:
            is_person_spread = True
        else:
            logger.warning("Unknown spread type (%r)", spread)
            continue
        for row in account_obj.list_all_with_spread(spread_id):
            e_id = int(row['entity_id'])
            if is_account_spread and e_id in account_cache:
                account_cache[e_id].append_spread(spread_id)
            elif is_person_spread and e_id in pid2fnr:
                person_cache[int(const.externalid_fodselsnr),
                             pid2fnr[e_id]].append_spread(spread_id)
            elif is_person_spread and e_id in pid2passnr:
                person_cache[int(const.externalid_pass_number),
                             pid2passnr[e_id]].append_spread(spread_id)
            del e_id

    # Account Affiliations
    logger.info("Loading account affs...")
    for row in account_obj.list_accounts_by_type(filter_expired=False,
                                                 primary_only=False,
                                                 fetchall=False):
        tmp = account_cache.get(int(row['account_id']))
        if tmp is not None:
            tmp.append_affiliation(int(row['affiliation']), int(row['ou_id']),
                                   int(row['priority']))
        del tmp

    # persons accounts....
    for ac_id, ac_obj in account_cache.items():
        id_type = ac_obj.get_external_id_type()
        id_value = ac_obj.get_external_id()
        key = (int(id_type), id_value)
        person_cache[key].append_account(ac_id)
        for aff in ac_obj.get_affiliations():
            aff, ou_id, pri = aff
            person_cache[key].set_primary_account(ac_id, pri)

    logger.info("Found %d persons and %d accounts",
                len(person_cache), len(account_cache))
    return person_cache, account_cache


def _promote_posix(db, acc_obj):
    group = Factory.get('Group')(db)
    const = Factory.get('Constants')(db)
    pu = PosixUser.PosixUser(db)
    uid = pu.get_free_uid()
    shell = const.posix_shell_bash
    grp_name = "posixgroup"
    group.find_by_name(grp_name, domain=const.group_namespace)
    try:
        pu.populate(uid, group.entity_id, None, shell, parent=acc_obj)
        pu.write_db()
    except Exception:
        logger.error("Unable to promote_posix", exc_info=True)
        return False
    # only gets here if posix user created successfully
    logger.info("%s promoted to posixaccount (uidnumber=%s)",
                acc_obj.account_name, uid)
    return True


def _handle_changes(db, ac, changes):
    do_promote_posix = False
    for chg in changes:
        ccode, cdata = chg
        if ccode == 'spreads_add':
            for s in cdata:
                # print "cdata[s] is: %s" % s
                ac.add_spread(s)
                ac.set_home_dir(s)
        elif ccode == 'quarantine_add':
            ac.add_entity_quarantine(cdata, get_creator_id(db))
        elif ccode == 'quarantine_del':
            ac.delete_entity_quarantine(cdata)
        elif ccode == 'set_ac_type':
            ac.set_account_type(cdata[0], cdata[1])
        elif ccode == 'gecos':
            ac.gecos = cdata
        elif ccode == 'expire_date':
            ac.expire_date = cdata
        elif ccode == 'promote_posix':
            do_promote_posix = True
        else:
            logger.error("Invalid change for account id=%r (%s) change=%r "
                         "(%r)", ac.entity_id, ac.account_name, ccode, cdata)
            continue
    ac.write_db()
    if do_promote_posix:
        _promote_posix(db, ac)
    logger.info("All changes written for account id=%r (%s)",
                ac.entity_id, ac.account_name)


def generate_persons(filename):
    """
    Fetch person data from a Paga xml file.

    :rtype: lis
    :return: A list of dicts, each dict represents a person in Paga.
    """
    logger.info('Loading data from %r', filename)
    persons = list()
    PagaDataParser(filename, persons.append)
    logger.info('Found %d persons from file', len(persons))
    return persons


class SkipPerson(Exception):
    """Skip processing a person."""
    pass


class Build(object):

    def __init__(self, db, persons=None, accounts=None):
        self.db = db
        self.co = Factory.get('Constants')(db)
        self.persons = persons or {}
        self.accounts = accounts or {}

        # create list of all valid countries
        # TODO: Country codes should *really* not be part of the cerebrum
        # database. UiT is currently the only ones using it
        entity_address = Entity.EntityAddress(db)
        self.country_codes = {row['code_str']
                              for row in entity_address.list_country_codes()
                              if row['code_str']}

    def process(self, person_data):
        """
        Process a list of persons from the Paga import data.

        :param person_data:
            A list of dicts with person data. Each dict must a 'fnr'
        """
        stats = {'ok': 0, 'skipped': 0, 'failed': 0}

        def get_identifier(person_dict):
            if (person_dict.get('fnr') and
                    person_dict['fnr'][6:11] != '00000'):
                return (self.co.externalid_fodselsnr, person_dict['fnr'])
            if (person_dict.get('edag_id_type') == 'passnummer' and
                    person_dict.get('edag_id_nr') and
                    person_dict.get('country') in self.country_codes):
                passnr = '%s-%s' % (person_dict['country'],
                                    person_dict['edag_id_nr'])
                return (self.co.externalid_pass_number, passnr)
            raise SkipPerson('No valid identifier (fnr, edag_id_nr)')

        # TODO: Should use ansattnr, not fnr/passnr
        for i, person_dict in enumerate(person_data, 1):
            try:
                id_type, id_value = get_identifier(person_dict)
            except SkipPerson as e:
                logger.error('Skipping person #%d: %s', i, e)
                stats['skipped'] += 1
                continue
            except Exception:
                logger.error('Skipping person #%d: unhandled error', i,
                             exc_info=True)
                stats['failed'] += 1
                continue

            try:
                logger.info("Processing person #%d (%s=%r)",
                            i, id_type, id_value)
                self.process_person(id_type, id_value)
            except SkipPerson as e:
                logger.warning('Skipping person #%d (%s=%r): %s',
                               i, id_type, id_value, e)
                stats['skipped'] += 1
            except Exception:
                logger.error('Skipping person #%d (%s=%r): unhandled error',
                             i, id_type, id_value, exc_info=True)
                stats['failed'] += 1
            else:
                stats['ok'] += 1

        logger.info('Processed %d persons (%d ok)',
                    sum(stats.values()), stats['ok'])

    def _calculate_account_spreads(self, existing_person, existing_account):
        const = self.co
        default_spreads = [int(const.Spread(x))
                           for x in cereconf.EMPLOYEE_DEFAULT_SPREADS]
        person_affs = existing_person.get_affiliations()
        acc_affs = existing_account.get_affiliations()
        new_affs = existing_account.get_new_affiliations()
        logger.debug("acc_affs=%s, new_affs=%s", acc_affs, new_affs)
        all_affs = acc_affs + new_affs
        logger.debug("all_affs=%s", all_affs)
        # do not build uit.no addresses for affs in these sko's
        no_exchange_skos = cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO
        tmp = set()
        for aff, ou_id, pri in all_affs:
            sko = get_sko(self.db, ou_id)
            for x in no_exchange_skos:
                if sko.startswith(x):
                    tmp.add((aff, ou_id, pri))
                    break

        # need atleast one aff to give exchange spread
        result = set(all_affs) - tmp
        logger.debug("acc_affs=%s, in filter=%s, result=%s",
                     set(all_affs), tmp, result)
        if result:
            default_spreads.append(int(const.Spread('exchange_mailbox')))

        # add cristin spread if person has aff_status == 'vitenskapelig'
        for aff, ou_id, status in person_affs:
            if status == int(const.affiliation_status_ansatt_vitenskapelig):
                default_spreads.append(int(const.Spread('cristin@uit')))
                break

        return default_spreads

    def process_person(self, id_type, id_value):
        try:
            p_obj = self.persons[int(id_type), id_value]
        except KeyError:
            raise SkipPerson('not in cerebrum')

        changes = []
        # check if person has an account
        if p_obj.has_account():
            acc_id, acc_obj = self.get_employee_account(p_obj)
        else:
            acc_id, acc_obj = self.create_employee_account(p_obj, id_type,
                                                           id_value)

        account = Factory.get('Account')(self.db)
        account.find(acc_id)
        # check if account is a posix account
        if not acc_obj.get_posix():
            changes.append(('promote_posix', True))

        # Update expire if needed
        current_expire = acc_obj.get_expire_date()
        new_expire = get_expire_date()

        # expire account if person is deceased
        new_deceased = False
        if p_obj.get_deceased_date() is not None:
            new_expire = p_obj.get_deceased_date()
            if current_expire != new_expire:
                logger.warning("Account owner deceased: %s",
                               acc_obj.get_uname())
                new_deceased = True
        if (new_expire > current_expire or
                new_deceased or
                current_expire is None):
            changes.append(('expire_date', str(new_expire)))

        # check account affiliation and status
        changes.extend(self._populate_account_affiliations(acc_id, p_obj))

        # make sure user has correct spreads
        if p_obj.get_affiliations():
            # if person has affiliations, add spreads
            default_spreads = self._calculate_account_spreads(p_obj, acc_obj)
            def_spreads = set(default_spreads)
            cb_spreads = set(acc_obj.get_spreads())
            to_add = def_spreads - cb_spreads
            if to_add:
                changes.append(('spreads_add', to_add))

            # Set spread expire date
            # Always use new expire to avoid PAGA specific spreads to be
            # extended because of mixed student / employee accounts
            for ds in def_spreads:
                account.set_spread_expire(spread=ds,
                                          expire_date=new_expire,
                                          entity_id=acc_id)

        # check quarantines
        for qt in acc_obj.get_quarantines():
            # employees should not have tilbud quarantine.
            if qt == self.co.quarantine_tilbud:
                changes.append(('quarantine_del', qt))

        if changes:
            logger.info("Changes for account id=%r: %s", acc_id, repr(changes))
            _handle_changes(self.db, account, changes)

    def create_employee_account(self, existing_person, id_type, id_value):
        """
        Create a new employee account for a given person object.

        :type existing_person: ExistingPerson

        :rtype: tuple
        :returns: A tuple with (<account-id>, <ExistingAccount object>)
        """
        const = self.co
        pe = Factory.get('Person')(self.db)
        ac = Factory.get('Account')(self.db)

        pe.find(existing_person.get_personid())

        first_name = pe.get_name(const.system_cached, const.name_first)
        last_name = pe.get_name(const.system_cached, const.name_last)

        uname = ac.suggest_unames(id_value, first_name, last_name)[0]
        ac.populate(uname,
                    const.entity_person,
                    pe.entity_id,
                    None,
                    get_creator_id(self.db),
                    get_expire_date())

        ac.write_db()
        password = ac.make_passwd(uname)
        ac.set_password(password)
        tmp = ac.write_db()
        logger.info("Created account id=%r (%s) for person_id=%r, write_db=%r",
                    ac.entity_id, uname, pe.entity_id, tmp)

        acc_id = ac.entity_id
        acc_obj = self.accounts[acc_id] = ExistingAccount(id_type, id_value,
                                                          uname, None)
        return acc_id, acc_obj

    def get_employee_account(self, existing_person):
        acc_id = existing_person.get_primary_account()
        acc_obj = self.accounts[acc_id]
        logger.info("Found employee account_id=%r (%s) for person_id=%r",
                    acc_id, acc_obj.get_uname(),
                    existing_person.get_personid())
        return acc_id, acc_obj

    def _populate_account_affiliations(self, account_id, existing_person):
        """
        Update account affiliations from person affiliations.
        """
        ou = Factory.get('OU')(self.db)
        changes = []

        existing_account = self.accounts[account_id]
        p_id = existing_person.get_personid()
        p_affs = existing_person.get_affiliations()
        account_affs = [(aff, ou_id) for aff, ou_id, _ in
                        existing_account.get_affiliations()]

        logger.debug("person_id=%r has affs=%r", p_id, p_affs)
        logger.debug("account_id=%r has account affs=%r",
                     account_id, account_affs)

        ou_list = set(r['ou_id'] for r in
                      ou.list_all_with_perspective(self.co.perspective_fs))

        for aff, ou_id, status in p_affs:
            if ou_id not in ou_list:
                logger.debug("ignoring aff:%s, ou:%s, status:%s",
                             aff, ou_id, status)
                # we have an account affiliation towards and none FS ou. ignore
                # it.
                continue
            if (aff, ou_id) not in account_affs:
                changes.append(('set_ac_type', (ou_id, aff)))
                existing_account.append_new_affiliations(aff, ou_id)
        return changes


def check_cereconf():
    missing = set()
    for attr in (
        'EMPLOYEE_FILTER_EXCHANGE_SKO',
        'EMPLOYEE_DEFAULT_SPREADS',
        'EMPLOYEE_SPREADLIST',
    ):
        if not hasattr(cereconf, attr):
            logger.critical("Missing 'cereconf.%s'", attr)
            missing.add(attr)
    if missing:
        raise RuntimeError("Missing cereconf values: %r", missing)


default_filename = 'paga_persons_{date}.xml'.format(
    date=datetime.date.today().strftime('%Y-%m-%d'))
default_person_file = os.path.join(
    cereconf.DUMPDIR, 'employees', default_filename)
default_log_preset = getattr(cereconf, 'DEFAULT_LOGGER_TARGET', 'console')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Import Paga XML files into the Cerebrum database")

    parser.add_argument(
        '-f', '-p', '--file', '--person-file',
        dest='filename',
        default=default_person_file,
        help='Read and import persons from %(metavar)s',
        metavar='xml-file',
    )
    id_type_arg = parser.add_argument(
        '--id-type',
        dest='id_type',
        choices=('ssn', 'passnummer'),
        help=(
            "Process a single person with id type %(metavar)s "
            "(default: process all). This option also requires a value"),
        metavar='<id-type>',
    )
    id_value_arg = parser.add_argument(
        '--id-value',
        dest='id_value',
        help=(
            "Process a single person with id value %(metavar)s "
            "(default: process all). This option also requires an id type"),
        metavar='<id-value>',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    check_cereconf()

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    builder = Build(db)

    logger.info('Fetching cerebrum data')
    builder.persons, builder.accounts = get_existing_accounts(db)

    logger.info('Reading persons from %r', args.filename)
    source_data = generate_persons(args.filename)

    if args.id_type or args.id_value:
        const = Factory.get('Constants')(db)
        with ParserContext(parser, id_type_arg):
            if args.id_type == 'ssn':
                id_type = const.externalid_fodselsnr
            elif args.id_type == 'passnummer':
                id_type = const.externalid_pass_number
            else:
                raise ValueError("Invalid id_type %r" % (args.id_type, ))

        with ParserContext(parser, id_value_arg):
            if not args.id_value:
                raise ValueError("Missing external id value")
        builder.process_person(id_type, args.id_value)
    else:
        builder.process(source_data)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
