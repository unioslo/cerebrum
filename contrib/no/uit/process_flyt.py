#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2014 University of Tromso, Norway
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

import ConfigParser
#
# Generic imports
#
import getopt
import os
import sys
from sets import Set

#
# Cerebrum imports
#
import cereconf
import mx
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError
from Cerebrum.utils.email import sendmail
from Cerebrum.utils.funcwrap import memoize

#
# Global variables
#
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)

accounts = None
persons = None
db = Factory.get('Database')()
const = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
ou = Factory.get('OU')(db)
account = Factory.get('Account')(db)
group = Factory.get('Group')(db)
progname = __file__.split(os.sep)[-1]
db.cl_init(change_program=progname)
em = Email.email_address(db)
person_file = ''

__doc__ = """
    usage:: %s Generates user accounts and general user maintenance for flyt
            persons [-d] [-p] [-e]
            All accounts will be created with an activation code. This is
            needed to remove the quarantine which is default for all flyt
            accounts.

    -t | --type [S/E]  : (S)tudent/(E)mployee
    -d | --dryrun      : Do no commit changes to database
    -p | --person_file : Flyt-person file
    -e | --email       : Will set email forward to email address from external
                         organization (NOT IMPLEMENTED YET)
    -h | --help        : This text

    --logger-name name: name of logger to use
    --logger-level level: loglevel to use
""" % progname


def get_existing_accounts(person_type):
    # init local variables
    logger.info("Loading persons...")
    tmp_persons = {}
    pid2fnr = {}
    person_obj = Factory.get('Person')(db)

    # getting deceased persons
    logger.info("Loading deceased person list...")
    deceased = person_obj.list_deceased()
    for row in person_obj.list_external_ids(id_type=const.externalid_fodselsnr,
                                            source_system=const.system_flyt):
        if not int(row['entity_id']) in pid2fnr:
            pid2fnr[int(row['entity_id'])] = row['external_id']
            tmp_persons[row['external_id']] = \
                ExistingPerson(person_id=int(row['entity_id']))

        if int(row['entity_id']) in deceased:
            tmp_persons[row['external_id']].set_deceased_date(
                deceased[int(row['entity_id'])])

    # Creating person affiliation list for flyt persons
    logger.info("Loading person affiliations...")
    for row in person.list_affiliations(source_system=const.system_flyt,
                                        fetchall=False):
        tmp = pid2fnr.get(int(row['person_id']), None)
        if tmp is not None:
            if is_ou_expired(row['ou_id']):
                logger.warn("Skipping affiliation to ou_id %s (expired) for " +
                            "person %s", row['ou_id'], int(row['person_id']))
                continue

            # Create list of all person affiliations
            tmp_persons[tmp].append_affiliation(int(row['affiliation']),
                                                int(row['ou_id']),
                                                int(row['status']))
    logger.info("Loading accounts...")
    tmp_ac = {}
    account_obj = Factory.get('Account')(db)
    for row in account_obj.search(expire_start=None):
        a_id = row['account_id']
        if not row['owner_id'] or not int(row['owner_id']) in pid2fnr:
            continue
        account_name = row.name
        if account_name.endswith(cereconf.USERNAME_POSTFIX['sito']):
            # This is a sito account. do not process as part of flyt accounts
            logger.debug(
                "%s is a sito account. Do not process as part of flyt import",
                account_name)
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
            entity_types=const.entity_account):
        tmp = tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_quarantine(int(row['quarantine_type']))

    #
    # Spreads
    #
    if person_type == 'E':
        # load employee spreadlists
        logger.info("Loading spreads... %s", cereconf.FLYT_EMPLOYEE_SPREADLIST)
        spread_list = [int(const.Spread(x)) for x in
                       cereconf.FLYT_EMPLOYEE_SPREADLIST]
    elif person_type == 'S':
        # load student spreadlists
        logger.info(
            "Loading spreads... %s", cereconf.FLYT_STUDENT_SPREADLIST)
        spread_list = [int(const.Spread(x)) for x in
                       cereconf.FLYT_STUDENT_SPREADLIST]

    for spread_id in spread_list:
        is_account_spread = is_person_spread = False
        spread = const.Spread(spread_id)
        if spread.entity_type == const.entity_account:
            is_account_spread = True
        elif spread.entity_type == const.entity_person:
            is_person_spread = True
        else:
            logger.warn("Unknown spread type")
            continue
        for row in account_obj.list_all_with_spread(spread_id):
            # print "processing person:%s" % (row))
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
                # logger.warn("Skipping affiliation to ou_id %s (expired)
                # for account %s." % (row['ou_id'],int(row['account_id'])))
                continue
            tmp.append_affiliation(int(row['affiliation']), int(row['ou_id']),
                                   int(row['priority']))
    # persons accounts....
    for ac_id, tmp in tmp_ac.items():
        fnr = str(tmp_ac[ac_id].get_fnr())
        tmp_persons[fnr].append_account(ac_id)
        for aff in tmp.get_affiliations():
            aff, ou_id, pri = aff
            tmp_persons[fnr].set_primary_account(ac_id, pri)

    logger.info(" found %i persons and %i accounts in database",
                len(tmp_persons), len(tmp_ac))
    return tmp_persons, tmp_ac


#
# Build accounts
#
class Build:

    def __init__(self, person_type, email_template_file, ttl):
        self.source_personlist = list()
        self.source_emaillist = list()
        self.expire_date = {}
        self.email = {}
        self.type = person_type
        self.email_template = email_template_file
        self.ttl = ttl
        # self.email_dict = {}

    def parse(self, person_file):
        dict_keys = []

        logger.info("Loading %s", person_file)

        if not os.path.isfile(person_file):
            logger.error("File:%s does not exist. Exiting", person_file)
            sys.exit(1)
        # datafile = libxml2.parseFile(person_file)
        # ctxt = datafile.xpathNewContext()

        # for each entry in person file do:
        fh = open(person_file, "r")
        for person in fh:
            person = person.rstrip()
            person = person.decode("utf-8").encode("iso8859-1")
            if person[0] == "#":
                # comment. Get dict keys
                person = person.lstrip("#").lstrip().rstrip()
                dict_keys = person.split(";")
            else:
                pers_dict = {}
                counter = 0
                pers_list = person.split(";")

                for item in dict_keys:
                    pers_dict[item] = pers_list[counter]
                    counter = counter + 1
                try:
                    ssn = pers_dict['norEduPersonNIN']
                    affiliation_type = pers_dict['eduPersonAffiliation']
                    self.expire_date[ssn] = pers_dict['expire_date']
                    self.email[ssn] = pers_dict['mail']
                except KeyError:
                    logger.warn(
                        "person:%s is missing required keys. Processing " +
                        "stopped for this person", pers_dict)
                    continue
                # only collect persons with eduPersonAffiliation equal to
                # faculty or staff
                if ('faculty' in affiliation_type or 'staff' in
                        affiliation_type) and self.type == 'E':
                    # logger.info("appending:%s to personlist" % (ssn))
                    self.source_personlist.append(ssn)
                # only collect persons with eduPersonAffiliation equal to
                # student
                elif 'student' in affiliation_type and self.type == 'S':
                    # logger.info("appending:%s to personlist" % (ssn))
                    self.source_personlist.append(ssn)

    def process_all(self):
        # pprint(self.source_personlist)
        # print "NOW persons list:"
        # pprint(persons)
        for ssn in self.source_personlist:
            temp_person = Factory.get('Person')(db)
            expire_date = self.expire_date[ssn]
            self.process_person(ssn, expire_date)

    def _calculate_spreads(self, acc_affs, new_affs):

        if (self.type == 'E'):
            default_spreads = [int(const.Spread(x)) for x in
                               cereconf.FLYT_EMPLOYEE_SPREADLIST]
        elif (self.type == 'S'):
            default_spreads = [int(const.Spread(x)) for x in
                               cereconf.FLYT_STUDENT_SPREADLIST]
        # logger.debug("acc_affs=%s, new_affs=%s" % (acc_affs,new_affs))
        all_affs = acc_affs + new_affs
        # logger.debug("all_affs=%s" % (all_affs,))
        # do not build uit.no addresses for affs in these sko's
        no_exchange_skos = cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO
        tmp = Set()
        for aff, ou_id, pri in all_affs:
            sko = get_sko(ou_id)
            for x in no_exchange_skos:
                if sko.startswith(x):
                    tmp.add((aff, ou_id, pri))
                    break

        # need atleast one aff to give exchange spread
        # logger.debug("acc_affs=%s,in filter=%s, result=%s" % (Set(all_affs)
        # ,tmp,Set(all_affs)-tmp))
        if Set(all_affs) - tmp:
            default_spreads.append(int(const.Spread('exchange_mailbox')))
        return default_spreads

    #
    # send email to new user that the account is now ready
    #
    def notify_user(self, email, username):
        if not os.path.isfile(self.email_template):
            logger.error("Unable to find email template. Exiting")
            sys.exit(1)
        else:
            # couldnt get ConfigParser to read emptylines, so not using that
            # to read template file :(
            # email_body =''
            # fh = open(self.email_template)
            # lines = fh.readlines()
            # for line in lines:
            #    if line[0] != "#":
            #        try
            #
            #        email_body +=line
            # pprint(email_body)

            # file exists. Continue
            template = ConfigParser.ConfigParser()
            template.empty_lines_in_values = False
            template.allow_no_value = True
            template.read(self.email_template)
            print("email is:%s" % email)
            email = "%s,bas-admin@cc.uit.no" % email
            email_from = template.get('NOTIFY_1', 'from')
            email_subject = template.get('NOTIFY_1', 'subject')
            email_body = template.get('NOTIFY_1', 'body')
            email_body = email_body.replace('USERNAME', username)

            # stupid ConfigParser. Cannot get it to read newlines. When
            # newlines are added to template file. ConfigParser adds yet a
            # newline
            # so: \n on empty line is now suddenly: \n\\n\n.
            # replace \\n with ''
            email_body = email_body.replace('\\n', '')
            cc = "bas-admin@cc.uit.no"
            sendmail(
                toaddr=email,
                fromaddr=email_from,
                subject=email_subject,
                body=email_body.decode('utf-8').encode("iso-8859-1"),
                cc=cc,
                debug=False)

    #
    # create an account for every person processed
    #
    def process_person(self, fnr, expire_date):
        logger.info("\t ### Process person %s ###", fnr)
        # logger.info("ssn is type:%s" % type(fnr))
        # logger.info("person data from persons list:")
        # pprint(persons[int(fnr)])
        p_obj = persons.get(fnr, None)
        if not p_obj:
            logger.warn(
                "Unknown person %s. Processing stopped for this person",
                fnr)
            return None

        changes = []
        # check if person has an account
        new_account = False
        if not p_obj.has_account():
            acc_id = create_flyt_account(fnr, expire_date)
            new_account = True

        else:
            acc_id = p_obj.get_primary_account()
        acc_obj = accounts[acc_id]
        # pprint(acc_obj.get_expire_date())
        # print "EMAIL IS:%s" % self.email[fnr]
        # foo = "CONCAT EMAIL IS:%s,bas-admin@cc.uit.no" % self.email[fnr]
        # print foo
        if new_account:
            self.notify_user(self.email[fnr], acc_obj.get_uname())
        logger.info("Update account %s/%d", acc_obj.get_uname(), acc_id)

        # check if account is a posix account
        if not acc_obj.get_posix():
            changes.append(('promote_posix', True))

        # Update expire if needed
        current_expire_string = str(acc_obj.get_expire_date())
        print("current_expire_string:%s" % current_expire_string)
        if not new_account:
            current_expire = mx.DateTime.Date(int(current_expire_string[0:4]),
                                              int(current_expire_string[5:7]),
                                              int(current_expire_string[8:10]))
        else:
            current_expire = current_expire_string
        logger.debug("account current expire is:%s", current_expire)
        today = mx.DateTime.today()
        logger.debug("today is:%s", today)

        """
        Calculate expire_date.
        NEW ACCOUNT: expire_date  = today +
        lokal_org_expire_date/account_ttl from flyt data

        UPDATE_ACCOUNT(everyday): handle/change expire_date only when today
            > account.expire_date
            If account is no longer in flyt data:
                Do not touch expire_date (account closes)
            If account is in flyt data:
                if last_seen + expire_date > today:
                    update_expire_date(but not to a date after
                        agreement_expire_date)
        """
        if today > current_expire:
            #
            # account expire date is reached. Check if expire date from flyt
            # is changed.
            #
            # This is not trivial. All flyt accounts are created with an
            # expire date = today + 12 months.
            # When an accounts expire date has been reached. the program
            # checks if a newer exire date exists in the data received from
            # the flyt server. The problem here is that if such an expire date
            # exists. There is no way to determine if this date is in fact a
            # valid expire date, or if its been set wrongly in the first place.
            #
            #
            logger.debug("account expire date reached")
            flyt_expire = self.expire_date[fnr]
            mx_flyt_expire = mx.DateTime.Date(int(flyt_expire[0:4]),
                                              int(flyt_expire[5:7]),
                                              int(flyt_expire[8:10]))
            if mx_flyt_expire > today:
                # OK
                new_expire = str(get_expire_date(flyt_expire))
                logger.debug(
                    "new expire date from flyt data. update expire date " +
                    "to:%s", new_expire)
            else:
                #
                # Flyt data does not contain any new expire dates. Use old
                # (and no longer valid) date
                #
                # OK
                logger.debug("no new expire date from flyt data")
                new_expire = current_expire
        else:
            #
            # Have not reached accounts current expire date. use current
            # expire date.
            #
            logger.debug("have not reached accounts expire date")
            if new_account:
                # OK
                logger.debug(
                    "use account OBJECT exire date:%s",
                    acc_obj.get_expire_date())
                new_expire = acc_obj.get_expire_date()
            else:
                # OK
                logger.debug(
                    "use account in DB expire_date:%s", current_expire)
                new_expire = current_expire
        # expire account if person is deceased
        new_deceased = False
        if p_obj.get_deceased_date() is not None:
            new_expire = str(p_obj.get_deceased_date())
            if current_expire != new_expire:
                logger.warn(
                    "Account owner deceased: %s. Processing stopped for " +
                    "this person", acc_obj.get_uname())
                new_deceased = True

        logger.debug(
            "Current expire %s, new expire %s", current_expire, new_expire)
        if new_expire > current_expire or new_deceased:
            changes.append(('expire_date', "%s" % new_expire))

        # check account affiliation and status
        changes.extend(_populate_account_affiliations(acc_id, fnr))

        # check gecos?
        # Har ikke personnavn tilgjengelig pr nuh..

        # make sure user has correct spreads
        if p_obj.get_affiliations():
            # if person has affiliations, add spreads
            default_spreads = self._calculate_spreads(
                acc_obj.get_affiliations(), acc_obj.get_new_affiliations())
            def_spreads = Set(default_spreads)
            cb_spreads = Set(acc_obj.get_spreads())
            to_add = def_spreads - cb_spreads
            if to_add:
                logger.info(
                    "change in spread. add following spreads:%s", to_add)
                changes.append(('spreads_add', to_add))

            # Set spread expire date
            # Always use new expire to avoid PAGA/HiFm specific spreads to be
            # extended because of mixed student / employee accounts
            for ds in def_spreads:
                account.set_spread_expire(spread=ds, expire_date=new_expire,
                                          entity_id=acc_id)

        # check quarantines
        for qt in acc_obj.get_quarantines():
            # flyt persons should not have tilbud quarantine.
            if qt == const.quarantine_tilbud:
                changes.append(('quarantine_del', qt))

        if changes:
            logger.debug("Changes [%i/%s]: %s", acc_id, fnr, repr(changes))
            _handle_changes(acc_id, changes)


def _promote_posix(acc_obj):
    group = Factory.get('Group')(db)
    pu = PosixUser.PosixUser(db)
    uid = pu.get_free_uid()
    shell = const.posix_shell_bash
    grp_name = "posixgroup"
    group.clear()
    group.find_by_name(grp_name, domain=const.group_namespace)
    try:
        pu.populate(uid, group.entity_id, None, shell, parent=acc_obj)
        pu.write_db()
    except Exception as msg:
        logger.warn("Error during promote_posix. Error was: %s", msg)
        return False
    # only gets here if posix user created successfully
    logger.info("%s promoted to posixaccount (uidnumber=%s)",
                acc_obj.account_name, uid)
    return True


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
        elif ccode == 'update_mail':
            update_email(a_id, cdata)
        else:
            logger.warn("Changing %s/%d: Unknown changecode: %s, " +
                        "changedata=%s", ac.account_name, a_id, ccode, cdata)
            continue
    ac.write_db()
    if do_promote_posix:
        _promote_posix(ac)
    logger.info("All changes written for %s/%d", ac.account_name, a_id)


def _populate_account_affiliations(account_id, fnr):
    """
    Assert that the account has the same affiliations as the person.
    """
    tmp_ou = Factory.get('OU')(db)
    changes = []
    tmp_affs = accounts[account_id].get_affiliations()
    account_affs = list()
    for aff, ou, pri in tmp_affs:
        account_affs.append((aff, ou))

    logger.debug("Person %s has affs=%s",
                 fnr, persons[fnr].get_affiliations())
    logger.debug("Account_id=%s,Fnr=%s has account affs=%s",
                 account_id, fnr, account_affs)
    ou_list = tmp_ou.list_all_with_perspective(const.perspective_fs)

    for aff, ou, status in persons[fnr].get_affiliations():
        valid_ou = False
        for i in ou_list:
            if i[0] == ou:
                valid_ou = True

        if not valid_ou:
            logger.debug(
                "ignoring aff:%s, ou:%s, status:%s", aff, ou, status)
            # we have an account affiliation towards and none FS ou. ignore it.
            continue
        if not (aff, ou) in account_affs:
            changes.append(('set_ac_type', (ou, aff)))
            accounts[account_id].append_new_affiliations(aff, ou)
    return changes


#
# Create new account
#
def create_flyt_account(fnr, expire_date):
    logger.debug(
        "creating account for person:%s. flyt wants expire date to be:%s",
        fnr, expire_date)
    owner = persons.get(fnr)
    if not owner:
        logger.error(
            "Cannot create account to person %s, not from flyt. Processing " +
            "stopped for this person", fnr)
        return None

    p_obj = Factory.get('Person')(db)
    p_obj.find(owner.get_personid())

    first_name = p_obj.get_name(const.system_cached, const.name_first)
    last_name = p_obj.get_name(const.system_cached, const.name_last)

    acc_obj = Factory.get('Account')(db)
    uname = acc_obj.suggest_unames(fnr, first_name, last_name)
    acc_obj.populate(uname,
                     const.entity_person,
                     p_obj.entity_id,
                     None,
                     get_creator_id(),
                     get_expire_date())

    try:
        acc_obj.write_db()
    except Exception as m:
        logger.warn(
            "Failed create for %s, uname=%s, reason: %s. Processing " +
            "stopped for this person", fnr, uname, m)
    else:
        pwd = acc_obj.make_passwd(uname)
        acc_obj.set_password(pwd)

    tmp = acc_obj.write_db()
    logger.debug("Created account %s(%s), write_db=%s, with password:%s",
                 uname, acc_obj.entity_id, tmp, pwd)

    # register new account obj in existing accounts list
    accounts[acc_obj.entity_id] = ExistingAccount(fnr, uname, None)

    return acc_obj.entity_id


@memoize
def is_ou_expired(ou_id):
    ou.clear()
    try:
        ou.find(ou_id)
        # exp.is_expired(ou)
    except EntityExpiredError:
        return True
    else:
        return False


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


@memoize
def get_creator_id():
    entity_name = Entity.EntityName(db)
    entity_name.find_by_name(cereconf.INITIAL_ACCOUNTNAME,
                             const.account_namespace)
    id = entity_name.entity_id
    return id


@memoize
def get_sko(ou_id):
    ou.clear()
    try:
        ou.find(ou_id)
        ou.get_parent(const.perspective_fs)
    except Errors.NotFoundError:
        # Persons has an affiliation to a non-fs ou.
        # Return NoneNoneNone
        # print "unable to find stedkode. Return NoneNoneNone"
        return "NoneNoneNone"
    return "%02s%02s%02s" % (ou.fakultet, ou.institutt, ou.avdeling)


#
# All flyt accounts have their default expire date set to today + 12 months
#
def get_expire_date(flyt_expire_date=None):
    if flyt_expire_date is None:
        #
        # Force expire date to be today + 12 months
        #
        cerebrum_expire = mx.DateTime.now() + mx.DateTime.RelativeDateTime(
            years=1)
        logger.debug("using today + 1 year")
    else:
        #
        # Use expire date from flyt service
        #

        cerebrum_expire = mx.DateTime.Date(int(flyt_expire_date[0:4]),
                                           int(flyt_expire_date[5:7]),
                                           int(flyt_expire_date[8:10]))
        logger.debug("setting expire to after fellesferien")

    today = mx.DateTime.today()
    ff_start = mx.DateTime.DateTime(today.year, 6, 15)
    ff_slutt = mx.DateTime.DateTime(today.year, 8, 15)
    # nextMonth = today + mx.DateTime.DateTimeDelta(30)

    if cerebrum_expire > ff_start and cerebrum_expire < ff_slutt:
        print("1. expire date is set to:%s" % mx.DateTime.DateTime(today.year,
                                                                   9, 1))
        return mx.DateTime.DateTime(today.year, 9, 1)
    else:
        print("2. expire date is set to:%s" % cerebrum_expire)
        return cerebrum_expire


def get_expire_date_old(expire_date):
    """ calculate a default expire date
    Take into consideration that we do not want an expire date
    in the general holiday time in Norway
    """
    today = mx.DateTime.today()
    ff_start = mx.DateTime.DateTime(today.year, 6, 15)
    ff_slutt = mx.DateTime.DateTime(today.year, 8, 15)
    nextMonth = today + mx.DateTime.DateTimeDelta(30)

    # ikke sett default expire til en dato i fellesferien
    if nextMonth > ff_start and nextMonth < ff_slutt:
        # fellesferien. Bruk 1 sept istedet.
        return mx.DateTime.DateTime(today.year, 9, 1)
    else:
        return nextMonth


def main():
    flyt_person_file = None
    dryrun = False
    email_forward = False
    person_type = None
    ttl = None
    email_template_file = 'email_notification.tmpl'
    global persons
    global accounts
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'E:t:dp:ehT:',
                                   ['email_template=', 'type=', 'dryrun',
                                    'person_file=', 'email', 'help',
                                    'time_to_live'])
    except getopt.GetoptError as m:
        logger.error("Unknown option:%s", m)
        usage()

    for opt, val in opts:
        if opt in ('T', '--time_to_live'):
            ttl = val
            if not ttl.isdigit():
                print("time to live must be set with digits")
                usage()
        if opt in ('-E', '--email_template'):
            email_template_file = val
        if opt in ('-t', '--type'):
            person_type = val
        if opt in ('-d', '--dryrun'):
            dryrun = True
            logger.info('dryrun chosen, will not commit changes')
        if opt in ('-p', '--person_file'):
            flyt_person_file = val
            logger.info("Loading flyt person file:%s", flyt_person_file)
        if opt in ('-e', '--email'):
            email_forward = True
            logger.info(
                'will set email forward to email address from external '
                'organization')
        if opt in ('-h', '--help'):
            usage()

    if person_type not in ('S', 'E'):
        print("type must be either[S]tudent or [E]mployee")
        usage()
    else:
        if person_type == 'S':
            logger.debug("Processing Students...")
        elif person_type == 'E':
            logger.debug("Processing Employees...")
    #
    # Get existing accounts from database
    #
    persons, accounts = get_existing_accounts(person_type)

    #
    # init build class
    #
    build = Build(person_type, email_template_file, ttl)

    #
    # Parse person file
    #
    logger.info("Parse person file")
    build.parse(flyt_person_file)

    #
    # Build accounts
    #
    logger.info("process persons from person file")
    build.process_all()
    # print "persons list contains:"
    # pprint(persons)
    #
    # Commit or rollback
    #
    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


def usage():
    print(__doc__)
    sys.exit(1)


if __name__ == '__main__':
    main()
