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
from __future__ import absolute_import, print_function

import getopt
import os
import sys

import libxml2
import mx

import cereconf
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import OU
from Cerebrum.modules.no.uit.Account import UsernamePolicy
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError


progname = __file__.split(os.sep)[-1]
__doc__ = """
usage:: %s [-d|--dryrun]
--dryrun : do no commit changes to database
-p | --person_file: sito person xml file
--logger-name name: name of logger to use
--logger-level level: loglevel to use
""" % (progname)


accounts = persons = logger = None
sito = None
skipped = added = updated = unchanged = deletedaff = 0
sito_affs = {}

db = Factory.get('Database')()
db.cl_init(change_program='process_sito')
co = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
logger = Factory.get_logger("cronjob")
sito_affs = {}
person = Factory.get('Person')(db)
group = Factory.get('Group')(db)
# ou = Factory.get('OU')(db)
ou = OU.OUMixin(db)
# exp = EntityExpire(db)


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


def is_ou_expired(ou_id):
    ou.clear()
    try:
        ou.find(ou_id)
    except EntityExpiredError:
        return True
    else:
        return False


def get_existing_accounts():
    # get persons that comes from Sito and their accounts
    logger.info("Loading persons...")
    tmp_persons = {}
    pid2fnr = {}
    person_obj = Factory.get('Person')(db)

    # getting deceased persons
    deceased = person_obj.list_deceased()

    for row in person_obj.list_external_ids(id_type=co.externalid_fodselsnr,
                                            source_system=co.system_sito):
        if int(row['entity_id']) not in pid2fnr:
            pid2fnr[int(row['entity_id'])] = row['external_id']
            tmp_persons[row['external_id']] = \
                ExistingPerson(person_id=int(row['entity_id']))

        if int(row['entity_id']) in deceased:
            tmp_persons[row['external_id']].set_deceased_date(
                deceased[int(row['entity_id'])])

    logger.info("Loading person affiliations...")
    for row in person.list_affiliations(source_system=co.system_sito,
                                        fetchall=False):
        tmp = pid2fnr.get(int(row['person_id']), None)

        if tmp is not None:
            if is_ou_expired(row['ou_id']):
                logger.error("Skipping affiliation to ou_id %s (expired) for "
                             "person %s", row['ou_id'], int(row['person_id']))
                continue
            tmp_persons[tmp].append_affiliation(int(row['affiliation']),
                                                int(row['ou_id']),
                                                int(row['status']))

    logger.info("Loading accounts...")
    tmp_ac = {}
    account_obj = Factory.get('Account')(db)
    for row in account_obj.search(expire_start=None):
        a_id = row['account_id']
        if not row['owner_id'] or int(row['owner_id']) not in pid2fnr:
            continue
        tmp_ac[int(a_id)] = ExistingAccount(pid2fnr[int(row['owner_id'])],
                                            row['name'],
                                            row['expire_date'])

    # Posixusers
    logger.info("Loading posixinfo...")
    posix_user_obj = PosixUser.PosixUser(db)
    for row in posix_user_obj.list_posix_users():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_posix(int(row['posix_uid']))

    # quarantines
    logger.info("Loading account quarantines...")
    for row in account_obj.list_entity_quarantines(
            entity_types=co.entity_account):
        tmp = tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_quarantine(int(row['quarantine_type']))

    # Spreads
    logger.info("Loading spreads... %s",
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
            logger.warn("Unknown spread type")
            continue
        for row in account_obj.list_all_with_spread(spread_id):
            if is_account_spread:
                tmp = tmp_ac.get(int(row['entity_id']), None)
            if is_person_spread:
                tmp = tmp_persons.get(int(row['entity_id']), None)
            if tmp is not None:
                tmp.append_spread(int(spread_id))

    # Account homes
    logger.info("Loading account homes...")
    for row in account_obj.list_account_home():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_home(int(row['home_spread']),
                         row['home'],
                         int(row['homedir_id']))

    # Account Affiliations
    logger.info("Loading account affs...")
    for row in account_obj.list_accounts_by_type(filter_expired=False,
                                                 primary_only=False,
                                                 fetchall=False):
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            if is_ou_expired(int(row['ou_id'])):
                continue
            tmp.append_affiliation(int(row['affiliation']), int(row['ou_id']),
                                   int(row['priority']))

    # persons accounts....
    for ac_id, tmp in tmp_ac.items():
        fnr = tmp_ac[ac_id].get_fnr()
        tmp_persons[fnr].append_account(ac_id)
        for aff in tmp.get_affiliations():
            aff, ou_id, pri = aff
            tmp_persons[fnr].set_primary_account(ac_id, pri)

    logger.info(" found %i persons and %i accounts",
                len(tmp_persons), len(tmp_ac))
    return tmp_persons, tmp_ac


#
# build accounts
#
class Build(object):

    def __init__(self):
        self.source_personlist = list()

    def load_fnr_from_xml(self, person):
        self.source_personlist.append(person['fnr'])

    def parse(self, person_file):
        logger.info("Loading %s" % person_file)

        if not os.path.isfile(person_file):
            logger.error("File:%s does not exist. Exiting", person_file)
            sys.exit(1)
        datafile = libxml2.parseFile(person_file)
        ctxt = datafile.xpathNewContext()

        for person in ctxt.xpathEval("//Persons/Person"):
            person_dict = {}
            ssn = ''
            ctxt.setContextNode(person)

            try:
                ssn = ctxt.xpathEval('SocialSecurityNumber')[0].getContent()
                logger.debug("processing fnr:%s", ssn)
            except IndexError:
                # person does not have ssn. log error message
                logger.warn("person does not have ssn")

            positionpercent = "0.0"
            try:
                for aff in person.xpathEval(
                        'EmploymentInfo/Employee/Employment/Employment'):
                    new_positionpercent = aff.xpathEval(
                        'EmploymentDistributionList/EmploymentDistribution/'
                        'PositionPercent')[0].getContent()
                    if float(positionpercent) < float(new_positionpercent):
                            positionpercent = new_positionpercent

            except IndexError:
                # person does not have a position percentage. does person have
                # any affiliation at all?
                logger.warning("%s does not have a position percentage", ssn)

            logger.debug("best position percentage is: %s" % positionpercent)

            try:
                person_dict['isDeactivated'] = ctxt.xpathEval(
                    'IsDeactivated')[0].getContent()
            except IndexError:
                # Person does not have isDeactivated tag. Report warning
                # message and continue
                logger.warning('Person:%s is missing IsDeactivated tag', ssn)

            # only append to list if person is NOT deactivated
            logger.info("positionpercent:%s" % (positionpercent))
            if (person_dict['isDeactivated'] == 'false'):
                self.source_personlist.append(ssn)
            if person_dict['isDeactivated'] == 'true':
                logger.warning("person:%s is deactivated" % ssn)

    def process_all(self):
        for ssn in self.source_personlist:
            self.process_person(ssn)

    def _calculate_spreads(self, acc_affs, new_affs):
        default_spreads = [int(co.Spread(x))
                           for x in cereconf.SITO_EMPLOYEE_DEFAULT_SPREADS]
        all_affs = acc_affs + new_affs
        # need at least one aff to give exchange spread
        if set(all_affs):
            default_spreads.append(int(co.Spread('exchange_mailbox')))
        return default_spreads

    #
    # create a sito account for every person processed
    #
    def process_person(self, fnr):
        logger.info("-------------------------------------------------------")
        logger.info("Process employee %s" % (fnr))
        p_obj = persons.get(fnr, None)
        if not p_obj:
            logger.warn("Unknown person %s." % (fnr,))
            return None

        changes = []

        if not p_obj.has_account():
            # person does not have an account.  Create a sito account
            acc_id = create_sito_account(fnr)

        else:
            # person has account(s)
            sito_account = 0
            acc_id = 0
            logger.debug("person:%s has %s accounts",
                         p_obj._personid, len(p_obj._accounts))
            for acc in p_obj._accounts:
                account.clear()
                account.find(acc)
                logger.debug("Processing account:%s", account.account_name)
                for type in account.get_account_types():
                    if co.affiliation_ansatt_sito in type:
                        sito_account = account.entity_id

                # An account may have its account type not set.
                # in these cases, the only way to check if an acocunt is a sito
                # account is to check the last 2 letters in the account name.
                # if they are'-s', then its a sito account.
                #
                if sito_account == 0:
                    # Account did not have a sito type (only set on active
                    # accounts).  we will have to check account name in case we
                    # have to reopen an inactive account.
                    if account.account_name.endswith(
                            cereconf.USERNAME_POSTFIX['sito']):
                        logger.debug("account %s has no account type, but its "
                                     "name indicates its a sito account",
                                     account.entity_id)
                        sito_account = account.entity_id
            if sito_account > 0:
                logger.debug("person:%s already has account %s with sito "
                             "affiliation", p_obj._personid, sito_account)
                acc_id = sito_account
            elif sito_account == 0:
                logger.debug("Person:%s does not have account with sito "
                             "affiliation. Create new sito account",
                             p_obj._personid)
                acc_id = create_sito_account(fnr)

        # we now have correct account object. Add missing account data.
        #
        acc_obj = accounts[acc_id]

        # check if account is a posix account
        if not acc_obj.get_posix():
            changes.append(('promote_posix', True))

        # Update expire if needed
        current_expire = str(acc_obj.get_expire_date())
        new_expire = str(get_expire_date())

        # expire account if person is deceased
        new_deceased = False
        if p_obj.get_deceased_date() is not None:
            new_expire = str(p_obj.get_deceased_date())
            if current_expire != new_expire:
                logger.warn("Account owner deceased: %s", acc_obj.get_uname())
                new_deceased = True

        logger.debug("Current expire %s, new expire %s", current_expire,
                     new_expire)
        if new_expire > current_expire or new_deceased:
            changes.append(('expire_date', str(new_expire)))

        # check account affiliation and status
        changes.extend(_populate_account_affiliations(acc_id, fnr))
        logger.debug("person affs:%s", p_obj.get_affiliations())

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
                         p_obj._personid)

        # check quarantines
        for qt in acc_obj.get_quarantines():
            # employees should not have tilbud quarantine.
            if qt == co.quarantine_tilbud:
                changes.append(('quarantine_del', qt))

        if changes:
            logger.debug("Changes [%i/%s]: %s", acc_id, fnr, repr(changes))
            _handle_changes(acc_id, changes)


def create_sito_account(fnr):
    owner = persons.get(fnr)
    if not owner:
        logger.error("Cannot create account to person %s, not from sito" % fnr)
        return None

    p_obj = Factory.get('Person')(db)
    p_obj.find(owner.get_personid())

    first_name = p_obj.get_name(co.system_cached, co.name_first)
    last_name = p_obj.get_name(co.system_cached, co.name_last)
    full_name = "%s %s" % (first_name, last_name)

    name_gen = UsernamePolicy(db)
    uname = name_gen.get_sito_uname(fnr, full_name)

    acc_obj = Factory.get('Account')(db)
    acc_obj.populate(
        uname,
        co.entity_person,
        p_obj.entity_id,
        None,
        get_creator_id(),
        get_expire_date())

    try:
        acc_obj.write_db()
    except Exception as m:
        logger.error("Failed create for %s, uname=%s, reason: %s",
                     fnr, uname, m)
    else:
        password = acc_obj.make_passwd(uname)
        acc_obj.set_password(password)
    tmp = acc_obj.write_db()
    logger.debug("Created account %s(%s), write_db=%s",
                 uname, acc_obj.entity_id, tmp)

    # register new account obj in existing accounts list
    accounts[acc_obj.entity_id] = ExistingAccount(fnr, uname, None)

    return acc_obj.entity_id


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


def _handle_changes(a_id, changes):
    do_promote_posix = False
    ac = Factory.get('Account')(db)
    ac.find(a_id)

    for chg in changes:
        ccode, cdata = chg
        if ccode == 'spreads_add':
            for s in cdata:
                ac.add_spread(s)
                ac.set_home_dir(s)
        elif ccode == 'quarantine_add':
            ac.add_entity_quarantine(cdata, get_creator_id())
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
        #     update_email(a_id, cdata)
        else:
            logger.error("Changing %s/%d: Unknown changecode: %s, "
                         "changedata=%s", ac.account_name, a_id, ccode, cdata)
            continue
    ac.write_db()
    if do_promote_posix:
        _promote_posix(ac)
    logger.info("All changes written for %s/%d", ac.account_name, a_id)


def _promote_posix(acc_obj):
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


def get_creator_id():
    entity_name = Entity.EntityName(db)
    entity_name.find_by_name(cereconf.INITIAL_ACCOUNTNAME,
                             co.account_namespace)
    return entity_name.entity_id


def _populate_account_affiliations(account_id, fnr):
    """
    Assert that the account has the same affiliations as the person.
    """

    changes = []
    tmp_affs = accounts[account_id].get_affiliations()
    account_affs = list()
    logger.debug('generate aff list for account_id:%s', account_id)
    for aff, ou, pri in tmp_affs:
        account_affs.append((aff, ou))

    logger.debug("Person %s has affs=%s", fnr, persons[fnr].get_affiliations())
    logger.debug("Account_id=%s,Fnr=%s has account affs=%s",
                 account_id, fnr, account_affs)
    for aff, ou, status in persons[fnr].get_affiliations():
        if (aff, ou) not in account_affs:
            changes.append(('set_ac_type', (ou, aff)))
            accounts[account_id].append_new_affiliations(aff, ou)
    return changes


def main():
    global sito
    global accounts, persons, dryrun
    person_file = '/cerebrum/var/source/sito/gjeldende_person'

    dryrun = False

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'dp:',
            ['dryrun', 'person_file='])
    except getopt.GetoptError as m:
        logger.error("Unknown option: %s", m)
        usage()

    for opt, val in opts:
        if opt in ('--dryrun', ):
            dryrun = True
        if opt in('-p', '--person_file'):
            person_file = val

    persons, accounts = get_existing_accounts()
    build = Build()
    build.parse(person_file)
    build.process_all()

    if dryrun:
        logger.info("Dryrun: Rollback all changes")
        db.rollback()
    else:
        logger.info("Committing all changes to database")
        db.commit()


def usage():
    print(__doc__)
    sys.exit(1)


if __name__ == '__main__':
    main()
