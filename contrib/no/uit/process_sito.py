#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2019 University of Tromsø, Norway
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
Process accounts for SITO employees.

This should run after importing employee data from SITO.
"""
from __future__ import absolute_import, print_function

import argparse
import logging
import os
import sys
import xml.etree.ElementTree

import mx.DateTime

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit.Account import UsernamePolicy
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)


class ExistingAccount(object):
    def __init__(self, fnr, uname, expire_date):
        self._affs = list()
        self._new_affs = list()
        self._expire_date = expire_date
        self._fnr = fnr
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

    def get_fnr(self):
        return self._fnr

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


def get_existing_accounts(db):
    """
    Get caches of SITO data.

    :rtype: tuple
    :return:
        Returns two dict mappings:

        - fnr to ExistingPerson object
        - account_id to ExistingAccount object
    """
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    pu = PosixUser.PosixUser(db)

    logger.info("Loading persons...")
    person_cache = {}
    account_cache = {}
    pid2fnr = {}

    # getting deceased persons
    deceased = pe.list_deceased()

    for row in pe.search_external_ids(id_type=co.externalid_fodselsnr,
                                      source_system=co.system_sito,
                                      fetchall=False):
        p_id = int(row['entity_id'])
        if p_id not in pid2fnr:
            pid2fnr[p_id] = row['external_id']
            person_cache[row['external_id']] = ExistingPerson(person_id=p_id)
        if p_id in deceased:
            person_cache[row['external_id']].set_deceased_date(deceased[p_id])
        del p_id

    logger.info("Loading person affiliations...")
    for row in pe.list_affiliations(source_system=co.system_sito,
                                    fetchall=False):
        p_id = int(row['person_id'])
        if p_id in pid2fnr:
            person_cache[pid2fnr[p_id]].append_affiliation(
                int(row['affiliation']),
                int(row['ou_id']),
                int(row['status']))
        del p_id

    logger.info("Loading accounts...")
    for row in ac.search(expire_start=None):
        a_id = int(row['account_id'])
        if not row['owner_id'] or int(row['owner_id']) not in pid2fnr:
            continue
        account_cache[a_id] = ExistingAccount(
            pid2fnr[int(row['owner_id'])],
            row['name'],
            row['expire_date'])
        del a_id

    # Posixusers
    logger.info("Loading posixinfo...")
    for row in pu.list_posix_users():
        a_obj = account_cache.get(int(row['account_id']), None)
        if a_obj is not None:
            a_obj.set_posix(int(row['posix_uid']))
        del a_obj

    # quarantines
    logger.info("Loading account quarantines...")
    for row in ac.list_entity_quarantines(
            entity_types=co.entity_account):
        a_obj = account_cache.get(int(row['entity_id']), None)
        if a_obj is not None:
            a_obj.append_quarantine(int(row['quarantine_type']))
        del a_obj

    # Spreads
    logger.info("Loading spreads... %r",
                cereconf.SITO_EMPLOYEE_DEFAULT_SPREADS)
    spread_list = [int(co.Spread(x))
                   for x in cereconf.SITO_EMPLOYEE_DEFAULT_SPREADS]
    for spread_id in spread_list:
        is_account_spread = is_person_spread = False
        spread = co.Spread(spread_id)
        if spread.entity_type == co.entity_account:
            is_account_spread = True
        elif spread.entity_type == co.entity_person:
            is_person_spread = True
        else:
            logger.warn("Unknown spread type (%r)", spread)
            continue
        for row in ac.list_all_with_spread(spread_id):
            e_id = int(row['entity_id'])
            if is_account_spread and e_id in account_cache:
                account_cache[e_id].append_spread(int(spread))
            elif is_person_spread and e_id in pid2fnr:
                account_cache[pid2fnr[e_id]].append_spread(int(spread))
            del e_id

    # Account homes
    logger.info("Loading account homes...")
    for row in ac.list_account_home():
        a_id = int(row['account_id'])
        if a_id in account_cache:
            account_cache[a_id].set_home(int(row['home_spread']),
                                         row['home'],
                                         int(row['homedir_id']))
        del a_id

    # Account Affiliations
    logger.info("Loading account affs...")
    for row in ac.list_accounts_by_type(filter_expired=False,
                                        primary_only=False,
                                        fetchall=False):
        a_id = int(row['account_id'])
        if a_id in account_cache:
            account_cache[a_id].append_affiliation(
                int(row['affiliation']),
                int(row['ou_id']),
                int(row['priority']))
        del a_id

    # persons accounts....
    for a_id, a_obj in account_cache.items():
        fnr = account_cache[a_id].get_fnr()
        person_cache[fnr].append_account(a_id)
        for aff in a_obj.get_affiliations():
            aff, ou_id, pri = aff
            person_cache[fnr].set_primary_account(a_id, pri)

    logger.info("Found %d persons and %d accounts",
                len(person_cache), len(account_cache))
    return person_cache, account_cache


def parse_person(person):
    """
    Parse a Person xml element.

    :param person: A //Persons/Person element

    :rtype: dict
    :return: A dictionary with normalized values.
    """
    employee_id = None

    def get(xpath, default=None):
        elem = person.find(xpath)
        if elem is None or not elem.text:
            logger.warning('Missing element %r for employee_id=%r',
                           xpath, employee_id)
            return default
        else:
            return (elem.text or '').strip()

    # Mandatory params
    employee_id = get('EmploymentInfo/Employee/EmployeeNumber')

    person_dict = {
        'employee_id': employee_id,
        'ssn': get('SocialSecurityNumber'),
        'is_deactivated': get('IsDeactivated') != 'false',
    }

    pos_pct = 0.0
    for employment in person.findall('EmploymentInfo/Employee/'
                                     'Employment/Employment'):
        pct_elem = employment.find('EmploymentDistributionList/'
                                   'EmploymentDistribution/PositionPercent')
        if pct_elem is not None and pct_elem.text:
            pos_pct = max(pos_pct, float(pct_elem.text))

    logger.debug('Position percentage for employee_id=%r: %f',
                 employee_id, pos_pct)
    person_dict['position_percentage'] = pos_pct
    return person_dict


def generate_persons(filename):
    """
    Find and parse employee data from an xml file.
    """
    if not os.path.isfile(filename):
        raise OSError('No file %r' % (filename, ))

    tree = xml.etree.ElementTree.parse(filename)
    root = tree.getroot()

    stats = {'ok': 0, 'skipped': 0, 'failed': 0}

    for i, person in enumerate(root.findall(".//Persons/Person"), 1):
        try:
            person_dict = parse_person(person)
        except Exception:
            stats['failed'] += 1
            logger.error('Skipping person #%d (element=%r), invalid data',
                         i, person, exc_info=True)
            continue

        if person_dict['is_deactivated']:
            logger.info('Skipping person #%d (employee_id=%r), deactivated',
                        i, person_dict['employee_id'])
            stats['skipped'] += 1
            continue

        if not person_dict['employee_id']:
            logger.warning('Skipping person #%d (employee_id=%r), missing '
                           ' employee_id', i, person_dict['employee_id'])
            stats['skipped'] += 1
            continue

        if not person_dict['ssn']:
            # TODO: Should use employee_id as identifier...
            logger.warning('Skipping person #%d (employee_id=%r), missing ssn',
                           i, person_dict['employee_id'])
            stats['skipped'] += 1
            continue

        stats['ok'] += 1
        yield person_dict

    logger.info("Parsed %d persons (%d ok)",
                sum(stats.values()), stats['ok'])


class SkipPerson(Exception):
    """Skip processing a person."""
    pass


class NotFound(Exception):
    """Missing required info."""
    pass


class Build(object):
    """
    Account builder
    """

    def __init__(self, db, persons=None, accounts=None):
        self.db = db
        self.co = Factory.get('Constants')(db)
        self.persons = persons or {}
        self.accounts = accounts or {}

    def process(self, person_data):
        """
        Process a list of persons from the sito import data.

        :param person_data: An iterable with dicts from py:func:`parse_person`
        """
        stats = {'ok': 0, 'skipped': 0, 'failed': 0}

        for person_dict in person_data:
            try:
                self.process_person(person_dict)
            except SkipPerson as e:
                logger.warning('Skipping employee_id=%r: %s',
                               person_dict['employee_id'], e)
                stats['skipped'] += 1
            except Exception:
                logger.error('Skipping employee_id=%r: unhandled error',
                             person_dict['employee_id'], exc_info=True)
                stats['failed'] += 1
                continue
            else:
                stats['ok'] += 1

        logger.info("Processed %d persons (%d ok)",
                    sum(stats.values()), stats['ok'])

    def _calculate_spreads(self, acc_affs, new_affs):
        default_spreads = [int(self.co.Spread(x))
                           for x in cereconf.SITO_EMPLOYEE_DEFAULT_SPREADS]
        all_affs = acc_affs + new_affs
        # need at least one aff to give exchange spread
        if set(all_affs):
            default_spreads.append(int(self.co.Spread('exchange_mailbox')))
        return default_spreads

    def process_person(self, person_dict):
        """
        Process a given person:

        :param person_data: A dict from py:func:`parse_person`
        """
        employee_id = person_dict['employee_id']
        logger.info("Process employee_id=%r", employee_id)

        fnr = person_dict['ssn']
        if not fnr:
            raise SkipPerson('missing ssn')
        if fnr not in self.persons:
            raise SkipPerson('unknown person')

        p_obj = self.persons[fnr]
        changes = []

        account = Factory.get('Account')(self.db)

        if not p_obj.has_account():
            # person does not have an account.  Create a sito account
            acc_id = self.create_sito_account(p_obj, fnr)
        else:
            # person has account(s)
            sito_account = 0
            acc_id = 0
            try:
                acc_id = self.get_sito_account(p_obj)
            except NotFound:
                acc_id = self.create_sito_account(p_obj, fnr)

        # we now have correct account object. Add missing account data.
        acc_obj = self.accounts[acc_id]

        # Check if account is a posix account
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
                logger.warn("Account owner deceased: %s", acc_obj.get_uname())
                new_deceased = True

        logger.debug("Current expire %s, new expire %s", current_expire,
                     new_expire)
        if new_expire > current_expire or new_deceased:
            changes.append(('expire_date', str(new_expire)))

        # check account affiliation and status
        changes.extend(self._populate_account_affiliations(acc_id, p_obj))

        # make sure user has correct spreads
        if p_obj.get_affiliations():
            # if person has affiliations, add spreads
            default_spreads = self._calculate_spreads(
                acc_obj.get_affiliations(),
                acc_obj.get_new_affiliations())
            logger.debug("old affs:%s, new affs:%s",
                         acc_obj.get_affiliations(),
                         acc_obj.get_new_affiliations())
            def_spreads = set(default_spreads)
            cb_spreads = set(acc_obj.get_spreads())
            to_add = def_spreads - cb_spreads
            if to_add:
                changes.append(('spreads_add', to_add))

        # Set spread expire date
        # Always use new expire to avoid SITO specific spreads to be
        # extended because of mixed student / employee accounts
        # TBD: 3  personer fra SITO har i dag bare 1 tilhørighet til rot-noden.
        # Disse må få enda en tilhørighet.  Hvis det ikke skjer, vil disse 3
        # ikke få konto.
        if 'def_spreads' in locals():
            for ds in def_spreads:
                account.set_spread_expire(spread=ds, expire_date=new_expire,
                                          entity_id=acc_id)
        else:
            logger.debug("person %s has no active sito affiliation",
                         p_obj.get_personid())

        # check quarantines
        for qt in acc_obj.get_quarantines():
            # employees should not have tilbud quarantine.
            if qt == self.co.quarantine_tilbud:
                changes.append(('quarantine_del', qt))

        if changes:
            logger.info("Changes for account_id=%r: %s", acc_id, repr(changes))
            _handle_changes(self.db, acc_id, changes)

    def create_sito_account(self, existing_person, fnr):
        """
        Create a sito account for a given person.
        """
        p_obj = Factory.get('Person')(self.db)
        p_obj.find(existing_person.get_personid())

        first_name = p_obj.get_name(self.co.system_cached, self.co.name_first)
        last_name = p_obj.get_name(self.co.system_cached, self.co.name_last)
        full_name = "%s %s" % (first_name, last_name)

        name_gen = UsernamePolicy(self.db)
        uname = name_gen.get_sito_uname(fnr, full_name)

        acc_obj = Factory.get('Account')(self.db)
        acc_obj.populate(
            uname,
            self.co.entity_person,
            p_obj.entity_id,
            None,
            get_creator_id(self.db),
            get_expire_date())

        try:
            acc_obj.write_db()
        except Exception as m:
            logger.error("Failed create for %s, uname=%s, reason: %s",
                         fnr, uname, m)
        else:
            password = acc_obj.make_passwd(uname)
            acc_obj.set_password(password)
        acc_obj.write_db()

        # register new account obj in existing accounts list
        self.accounts[acc_obj.entity_id] = ExistingAccount(fnr, uname, None)
        logger.info("Created sito account_id=%r (%s) for person_id=%r",
                    acc_obj.entity_id, uname, existing_person.get_personid())
        return acc_obj.entity_id

    def get_sito_account(self, existing_person):
        account = Factory.get('Account')(self.db)
        person_id = existing_person.get_personid()
        sito_account = None

        for acc in existing_person._accounts:
            account.clear()
            account.find(acc)
            for acc_type in account.get_account_types():
                if self.co.affiliation_ansatt_sito in acc_type:
                    sito_account = account.entity_id
                    logger.info("Found sito account_id=%r (%s) for "
                                "person_id=%r (from acc_type)",
                                sito_account, account.account_name,
                                person_id)
                    break

        if sito_account is None:
            # An account may have its account type not set.
            # in these cases, the only way to check if an acocunt is a sito
            # account is to check the last 2 letters in the account name.
            # if they are'-s', then its a sito account.
            for acc in existing_person._accounts:
                account.clear()
                account.find(acc)
                # Account did not have a sito type (only set on active
                # accounts).  we will have to check account name in case we
                # have to reopen an inactive account.
                if account.account_name.endswith(
                        cereconf.USERNAME_POSTFIX['sito']):
                    sito_account = account.entity_id
                    logger.info("Found sito account_id=%r (%s) for "
                                "person_id=%r (from username)", sito_account,
                                account.account_name, person_id)
                    break

        if sito_account is None:
            raise NotFound("No sito account for %r", existing_person)
        else:
            return sito_account

    def _populate_account_affiliations(self, account_id, existing_person):
        """
        Generate changes to account affs from person affs.
        """
        changes = []
        tmp_affs = self.accounts[account_id].get_affiliations()
        account_affs = list()
        logger.debug('generate aff list for account_id:%s', account_id)
        for aff, ou, pri in tmp_affs:
            account_affs.append((aff, ou))
        p_id = existing_person.get_personid()
        p_affs = existing_person.get_affiliations()
        logger.debug("person_id=%r has affs=%r", p_id, p_affs)
        logger.debug("account_id=%s has account affs=%r",
                     account_id, account_affs)
        for aff, ou, status in p_affs:
            if (aff, ou) not in account_affs:
                changes.append(('set_ac_type', (ou, aff)))
                self.accounts[account_id].append_new_affiliations(aff, ou)
        return changes


def get_expire_date():
    """
    calculate a default expire date.

    Take into consideration that we do not want an expiredate in the general
    holiday time in Norway.
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


def _handle_changes(db, account_id, changes):
    do_promote_posix = False
    ac = Factory.get('Account')(db)
    ac.find(account_id)

    for chg in changes:
        ccode, cdata = chg
        if ccode == 'spreads_add':
            for s in cdata:
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
        # TODO: no update_email?
        # elif ccode == 'update_mail':
        #     update_email(account_id, cdata)
        else:
            logger.error("Invalid change for account_id=%r change=%r (%r)",
                         account_id, ccode, cdata)
            continue
    ac.write_db()
    if do_promote_posix:
        _promote_posix(db, ac)
    logger.info("All changes written for account_id=%r", account_id)


def _promote_posix(db, acc_obj):
    co = Factory.get('Constants')(db)
    group = Factory.get('Group')(db)
    pu = PosixUser.PosixUser(db)
    uid = pu.get_free_uid()
    shell = co.posix_shell_bash
    grp_name = "posixgroup"
    group.clear()
    group.find_by_name(grp_name, domain=co.group_namespace)
    try:
        pu.populate(uid, group.entity_id, None, shell, parent=acc_obj)
        pu.write_db()
    except Exception as msg:
        logger.error("Error during promote_posix. Error was: %s", msg)
        return False
    # only gets here if posix user created successfully
    logger.info("%s promoted to posixaccount (uidnumber=%s)",
                acc_obj.account_name, uid)
    return True


def get_creator_id(db):
    co = Factory.get('Constants')(db)
    entity_name = Entity.EntityName(db)
    entity_name.find_by_name(cereconf.INITIAL_ACCOUNTNAME,
                             co.account_namespace)
    return entity_name.entity_id


default_person_file = os.path.join(sys.prefix,
                                   'var/cache/sito/Sito-Persons.xml')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Process accounts for SITO employees")

    parser.add_argument(
        '-p', '--person-file',
        default=default_person_file,
        help='Process persons from %(metavar)s',
        metavar='xml-file',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='process_sito')
    builder = Build(db)

    logger.info('Fetching cerebrum data')
    builder.persons, builder.accounts = get_existing_accounts(db)

    logger.info('Reading persons from %r', args.person_file)
    source_data = generate_persons(args.person_file)

    logger.info('Processing persons')
    builder.process(source_data)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        db.rollback()
        logger.info('Rolling back changes')
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
