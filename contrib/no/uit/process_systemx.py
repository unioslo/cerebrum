#! /usr/bin/env python
# -*- coding: utf-8 -*-

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
from __future__ import unicode_literals

import getopt
import htmlentitydefs
import mx.DateTime
import os
import re
from sets import Set
import sys

from Cerebrum.utils import transliterate
import cereconf
from Cerebrum import Errors
from Cerebrum.modules.no.uit.access_SYSX import SYSX
from Cerebrum.modules.no.uit import Email
from Cerebrum.utils import email
from Cerebrum.Utils import Factory
from Cerebrum.Entity import EntityName
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError

db = Factory.get('Database')()
db.cl_init(change_program='process_systemx')
co = Factory.get('Constants')(db)

logger = Factory.get_logger("cronjob")

# Used for getting OU names
ou = Factory.get('OU')(db)
sys_x_affs = {}


def get_existing_accounts():
    stedkoder = ou.get_stedkoder()
    ou_stedkode_mapping = {}
    for stedkode in stedkoder:
        ou_stedkode_mapping[stedkode['ou_id']] = str(
            stedkode['fakultet']).zfill(2) + str(stedkode['institutt']).zfill(
            2) + str(stedkode['avdeling']).zfill(2)

    # get persons that comes from sysX and their accounts
    pers = Factory.get("Person")(db)

    # getting deceased persons
    deceased = pers.list_deceased()

    tmp_persons = {}
    logger.info("Loading persons...")
    pid2sysxid = {}
    sysx2pid = {}
    for row in pers.list_external_ids(id_type=co.externalid_sys_x_id):
        # denne henter ut alle fra system x
        # logger.info("1. row['external_id'] %s" % row['external_id'])

        if (row['source_system'] == int(co.system_x) or
                (int(row['entity_id']) not in pid2sysxid)):

            # logger.info("2. row.['external_id']:%s" % row['external_id'])

            pid2sysxid[int(row['entity_id'])] = int(row['external_id'])
            sysx2pid[int(row['external_id'])] = int(row['entity_id'])
            tmp_persons[int(row['external_id'])] = ExistingPerson()

            if int(row['entity_id']) in deceased:
                tmp_persons[int(row['external_id'])].set_deceased_date(
                    deceased[int(row['entity_id'])])

    for row in pers.list_affiliations(
            source_system=co.system_x,
            fetchall=False):
        # Denne henter ut alle personer med AKTIV system_x affiliation

        # logger.info("person_id: %s" % row['person_id'])
        tmp = pid2sysxid.get(row['person_id'], None)
        # logger.info("tmp:%s" % tmp)
        if tmp is not None:
            ou.clear()
            try:
                # logger.info("ou_id: %s" % row['ou_id'])
                # logger.info("tmp: %s" % tmp)
                # logger.info("affiliation: %s" % row['affiliation'])
                ou.find(int(row['ou_id']))
                tmp_persons[tmp].append_affiliation(
                    int(row['affiliation']), int(row['ou_id']),
                    int(row['status']))
                try:
                    sys_x_affs[tmp] = ou_stedkode_mapping[row['ou_id']]
                    logger.info("storing stedkode: %s for sys_x_user:%s",
                                ou_stedkode_mapping[row['ou_id']], tmp)
                except:
                    logger.info("sysx-id:%s has expired stedkode:%s." % (
                        row['person_id'], row['ou_id']))
                    # logger.info("unable to store stedkode")
                    pass
            except EntityExpiredError as msg:
                logger.error("Skipping affiliation to ou_id %s (expired) for "
                             "person with sysx_id %s." % (row['ou_id'], tmp))
                continue

    tmp_ac = {}
    account_obj = Factory.get('Account')(db)
    account_name_obj = Factory.get('Account')(db)
    logger.info("Loading accounts...")

    #
    # hente alle kontoer for en person
    #
    for row in account_obj.list(filter_expired=False, fetchall=False):
        sysx_id = pid2sysxid.get(int(row['owner_id']), None)

        if not sysx_id or sysx_id not in tmp_persons:
            continue

        #
        # Need to exclude all non-uit accounts
        #
        account_name_obj.clear()
        account_name_obj.find(row['account_id'])
        if (account_name_obj.account_name.endswith(
                cereconf.USERNAME_POSTFIX['sito'])):
            # if (account_name_obj.account_name[-2:] ==
            #         cereconf.USERNAME_POSTFIX['sito']):
            logger.debug(
                "account:%s is a sito account and removed from systemx "
                "account process list", account_name_obj.account_name)
            continue

        #
        # Exclude accounts that ends with 999 (they are admin accounts and not
        # to be counted when checking for existing accounts)
        #
        if account_name_obj.account_name[3:6] == '999':
            logger.info(
                "account_name:%s is an admin account and excluded from list",
                account_name_obj.account_name)
            continue

        tmp_ac[row['account_id']] = ExistingAccount(sysx_id,
                                                    row['expire_date'])

    # Posixusers
    posix_user_obj = Factory.get('PosixUser')(db)
    for row in posix_user_obj.list_posix_users():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_posix(int(row['posix_uid']))

    # quarantines
    for row in account_obj.list_entity_quarantines(
            entity_types=co.entity_account):
        tmp = tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_quarantine(int(row['quarantine_type']))

    # Spreads
    spread_list = [co.spread_uit_ldap_people,
                   co.spread_uit_fronter_account,
                   co.spread_uit_ldap_system,
                   co.spread_uit_ad_account, co.spread_uit_cristin,
                   co.spread_uit_exchange]
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
    # FIXME: This does not work for us!
    for row in account_obj.list_account_home():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None and row['disk_id']:
            tmp.set_home(int(row['home_spread']), int(row['disk_id']),
                         int(row['homedir_id']))

    # Affiliations
    for row in account_obj.list_accounts_by_type(filter_expired=False):
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            ou.clear()
            try:
                ou.find(int(row['ou_id']))
                tmp.append_affiliation(int(row['affiliation']),
                                       int(row['ou_id']))
            except EntityExpiredError as msg:
                logger.warn(
                    "Skipping affiliation to ou_id %s (OU expired) for person"
                    " with account_id %s. (Is person affiliation on OU not "
                    "deleted because of grace?)",
                    row['ou_id'], row['account_id'])
                continue

    # traits
    for row in account_obj.list_traits(co.trait_sysx_registrar_notified):
        tmp = tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_trait(co.trait_sysx_registrar_notified, row['strval'])
    for row in account_obj.list_traits(co.trait_sysx_user_notified):
        tmp = tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_trait(co.trait_sysx_user_notified, row['strval'])

    # organize sysx id's
    for acc_id, tmp in tmp_ac.items():
        sysx_id = tmp_ac[acc_id].get_sysxid()
        logger.info(
            "appending sys-x id:%s, account id:%s to list of existing "
            "accounts", sysx_id, acc_id)
        tmp_persons[sysx_id].append_account(acc_id)

    logger.info(" found %i persons and %i accounts" % (
        len(tmp_persons), len(tmp_ac)))
    return tmp_persons, tmp_ac


def expire_date_conversion(expire_date):
    # historical reasons dictate that dates may be received on the format
    # dd.mm.yyyy if this is the case, we need to convert it to yyyy-mm-dd
    day, month, year = expire_date.split("-", 2)
    expire_date = "%s-%s-%s" % (year, month, day)
    return expire_date


def _send_mailq(mailq):
    for item in mailq:
        type = item['template']
        info = item['person_info']
        account_id = item['account_id']
        send_mail(type, info, account_id)


def send_mail(type, person_info, account_id):
    sender = cereconf.SYSX_EMAIL_NOTFICATION_SENDER
    cc = cereconf.SYSX_CC_EMAIL
    logger.debug("in send_mail")
    if type == 'ansvarlig':
        t_code = co.trait_sysx_registrar_notified

        template = (cereconf.CB_SOURCEDATA_PATH +
                    '/templates/sysx/ansvarlig.tpl')
        recipient = person_info.get('ansvarlig_epost')
        person_info['AD_MSG'] = ""
        if 'AD_account' in person_info.get('spreads'):
            person_info['AD_MSG'] = ""
    elif type == 'bruker':
        recipient = person_info.get('bruker_epost', None)
        if recipient in (None, ""):
            logger.info(
                'No recipient when sending bruker_epost, message not sent')
            return
        t_code = co.trait_sysx_user_notified
        template = cereconf.CB_SOURCEDATA_PATH + '/templates/sysx/bruker.tpl'
    else:
        logger.error("Unknown type '%s' in send_mail()" % type)
        return

    # record the username in person_info dict.
    ac = Factory.get('Account')(db)
    logger.debug("send_mail(): acc_id is ->%s<" % account_id)
    ac.find(account_id)
    person_info['USERNAME'] = ac.account_name

    # spreads may be a list
    if isinstance(person_info['spreads'], list):
        person_info['spreads'] = ",".join(person_info['spreads'])

    # hrrmpfh.. We talk to Oracle in iso-8859-1 format. Convert text
    for k in person_info.keys():
        person_info[k] = person_info[k]

    # finally, send the message
    debug = False
    logger.debug(
        "ABOUT to send email to user:%s with cc:%s" % (recipient, cc))
    # sys.exit(1)

    #
    # Deaktivert for testing. 2014-12-04
    #
    # ea = Email.email_address(db)

    ret = email.mail_template(recipient, template, sender=sender, cc=[cc],
                              substitute=person_info, charset='utf-8',
                              debug=debug)
    if debug:
        logger.debug("DRYRUN: mailmsg=\n%s", ret)

    # set trait on user
    r = ac.populate_trait(t_code, strval=recipient, date=mx.DateTime.today())
    logger.info("TRAIT populate result:%s", r)
    ac.write_db()


def _promote_posix(acc_obj):
    group = Factory.get('Group')(db)
    pu = Factory.get('PosixUser')(db)
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
    entity_name = EntityName(db)
    entity_name.find_by_name(cereconf.INITIAL_ACCOUNTNAME,
                             co.account_namespace)
    id = entity_name.entity_id
    return id


# get_creator_id=simple_memoize(get_creator_id)

def _handle_changes(a_id, changes):
    TODAY = mx.DateTime.today().strftime("%Y-%m-%d")
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
            ac.add_entity_quarantine(cdata, get_creator_id(), start=TODAY)
            # ac.quarantine_add(cdata)
        elif ccode == 'quarantine_del':
            ac.delete_entity_quarantine(cdata)
            # ac.quarantine_del(cdata)
        elif ccode == 'set_ac_type':
            ac.set_account_type(cdata[0], cdata[1])
        elif ccode == 'gecos':
            ac.gecos = cdata
        elif ccode == 'expire_date':
            ac.expire_date = cdata
        elif ccode == 'promote_posix':
            do_promote_posix = True
        else:
            logger.error("Change account: %s(id=%d): Unknown changecode: %s, "
                         "changedata=%s",
                         ac.account_name, a_id, ccode, cdata)
            continue
    ac.write_db()
    if do_promote_posix:
        _promote_posix(ac)
    logger.info("Change Account %s(id=%d): All changes written",
                ac.account_name, a_id)


def _update_email(acc_id, bruker_epost):
    em = Email.email_address(db)
    ad_email = em.get_employee_email(acc_id, db)

    account_obj = Factory.get('Account')(db)
    account_obj.find(acc_id)
    person_obj = Factory.get('Person')(db)
    person_obj.find(account_obj.owner_id)
    if len(ad_email) > 0:
        ad_email = ad_email[account_obj.account_name]
    else:
        # TODO: Use default maildomain whenever AD email is nonexistant!
        # No need to check for student aff.
        person_aff = person_obj.list_affiliations(
            person_id=person_obj.entity_id,
            affiliation=co.affiliation_student)
        logger.debug("update_email(): person_aff=%s" % person_aff)
        if len(person_aff) > 0:
            logger.debug(
                "update_email(): %s has student affiliation",
                account_obj.entity_id)
            ad_email = "@".join(
                (account_obj.account_name, cereconf.NO_MAILBOX_DOMAIN))
        elif bruker_epost != "":
            # FIXME: Never ever set extrernal email here !!!
            ad_email = "%s" % bruker_epost
        else:
            no_mailbox_domain = cereconf.NO_MAILBOX_DOMAIN
            ad_email = "@".join((account_obj.account_name, no_mailbox_domain))
            logger.warning(
                "update_email(): Using NO_MAILBOX_DOMAIN=>'%s'" % ad_email)

    current_email = ""
    try:
        current_email = account_obj.get_primary_mailaddress()
    except Errors.NotFoundError:
        # no current primary mail.
        pass

    if current_email.lower() != ad_email.lower():
        # update email!
        logger.debug("Email update needed old='%s', new='%s'" % (
            current_email, ad_email))
        try:
            em.process_mail(account_obj.entity_id, ad_email)
        except Exception as m:
            logger.critical(
                "EMAIL UPDATE FAILED: account_id=%s , email=%s,error:%s",
                account_obj.entity_id, ad_email, m)
            sys.exit(2)
    else:
        logger.debug("Email update not needed old=new='%s'", current_email)


class Build(object):

    def __init__(self, sysx, persons, accounts):
        # init variables
        ac = Factory.get('Account')(db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.bootstrap_id = ac.entity_id
        gr = Factory.get('Group')(db)
        gr.find_by_name("posixgroup", domain=co.group_namespace)
        self.posix_group = gr.entity_id
        self.num_expired = 0
        self.sysx = sysx
        self.persons = persons
        self.accounts = accounts

    # RMI000 2009-05-07
    # convert_entity and unquote_html should be utility functions.
    # They are placed here because I need them NOW, but I can't say
    # if they will work well enough to be available for general use.
    # This is a good place to test them over time before moving them
    # to a more suitable location - if they prove useful and robust
    # enough.
    def convert_entity(self, chunk):
        """Convert a HTML entity into ISO character"""
        if chunk.group(1) == '#':
            try:
                return chr(int(chunk.group(2)))
            except ValueError:
                return '&#%s;' % chunk.group(2)
        try:
            return htmlentitydefs.entitydefs[chunk.group(2)]
        except KeyError:
            return '&%s;' % chunk.group(2)

    def unquote_html(self, string):
        """Convert a HTML quoted string into ISO string

        Works with &#XX; and with &nbsp; &gt; etc."""
        return re.sub(r'&(#?)(.+?);', self.convert_entity, string)

    def process_all(self):
        for item in self.sysx.sysxids.items():
            logger.debug("-----------------------------")
            sysx_id, sysx_person = item
            self._process_sysx(int(sysx_id), sysx_person)

    def _CreateAccount(self, sysx_id):

        today = mx.DateTime.today()
        default_creator_id = self.bootstrap_id
        default_group_id = self.posix_group
        p_obj = Factory.get('Person')(db)
        logger.info("Try to create user for person with sysx_id=%s" % sysx_id)
        try:
            p_obj.find_by_external_id(co.externalid_sys_x_id, str(sysx_id),
                                      co.system_x, co.entity_person)
            # p_obj.find_by_external_id(co.entity_person,sysx_id,co.externalid_sys_x_id)
        except Errors.NotFoundError:
            logger.warn("OUCH! person (sysx_id=%s) not found" % sysx_id)
            return None
        else:
            person_id = p_obj.entity_id

        if not self.persons[sysx_id].get_affiliations():
            logger.error("Person (sysx_id=%s) has no sysX affs" % sysx_id)
            return None

        try:
            first_name = p_obj.get_name(co.system_cached, co.name_first)
        except Errors.NotFoundError:
            # This can happen if the person has no first name and no
            # authoritative system has set an explicit name_first variant.
            first_name = ""
        try:
            last_name = p_obj.get_name(co.system_cached, co.name_last)
        except Errors.NotFoundError:
            # See above.  In such a case, name_last won't be set either,
            # but name_full will exist.
            last_name = p_obj.get_name(co.system_cached, co.name_full)
            assert last_name.count(' ') == 0
        full_name = " ".join((first_name, last_name))

        try:
            fnr = p_obj.get_external_id(id_type=co.externalid_fodselsnr)[0][
                'external_id']
        except IndexError:
            fnr = sysx_id

        account = Factory.get('PosixUser')(db)
        fnr = str(fnr)
        uname = account.suggest_unames(fnr, first_name, last_name)[0]
        account.populate(name=uname,
                         owner_id=person_id,
                         owner_type=co.entity_person,
                         np_type=None,
                         creator_id=default_creator_id,
                         expire_date=today,
                         posix_uid=account.get_free_uid(),
                         gid_id=self.posix_group,
                         gecos=transliterate.for_posix(full_name),
                         # gecos=account.simplify_name(full_name,as_gecos=True),
                         shell=co.posix_shell_bash
                         )

        password = account.make_passwd(uname)
        account.set_password(password)
        tmp = account.write_db()
        logger.debug(
            "new Account=%s, write_db=%s" % (account.account_name, tmp))

        acc_obj = ExistingAccount(sysx_id, today)
        # register new account as posix
        acc_obj.set_posix(int(account.posix_uid))
        self.accounts[account.entity_id] = acc_obj
        return account.entity_id

    def _process_sysx(self, sysx_id, person_info):
        spread_acc = Factory.get('Account')(db)
        new_account = False
        user_mail_message = False
        logger.info("Starting process of sysXid=%s", sysx_id)
        p_obj = self.persons.get(sysx_id, None)
        if not p_obj:
            logger.error("ERROR Nonexistent sysx_id %s. Skipping", sysx_id)
            return None

        changes = []
        mailq = []

        if not p_obj.has_account():
            new_account = True
            acc_id = self._CreateAccount(sysx_id)
            mailq.append({
                'account_id': acc_id,
                'person_info': person_info,
                'template': 'bruker'
            })
            user_mail_message = True
        else:
            acc_id = p_obj.get_account()
            spread_acc.clear()
            spread_acc.find(acc_id)
            is_expired = spread_acc.is_expired()

        if acc_id is not None:
            acc_obj = self.accounts[acc_id]
        else:
            # unable to find account object. return None
            return None
        # check if account is a posix account
        if not acc_obj.get_posix():
            changes.append(('promote_posix', True))

        # Update expire if needed
        current_expire = acc_obj.get_expire_date()
        new_expire = mx.DateTime.DateFrom(person_info['expire_date'])
        today = mx.DateTime.today()

        # expire account if person is deceased
        new_deceased = False
        if p_obj.get_deceased_date() is not None:
            new_expire = str(p_obj.get_deceased_date())
            if current_expire != new_expire:
                # print person_info
                logger.warn("Person deceased: %s", 'TEST')
                new_deceased = True

        # current expire = from account object
        # new expire = from system_x
        # today = current date
        if ((new_expire > today) and (new_expire > current_expire) and (
                current_expire < today) and (user_mail_message is False)):
            mailq.append({
                'account_id': acc_id,
                'person_info': person_info,
                'template': 'bruker'
            })

        if (((new_expire > today) and (
                new_expire > current_expire)) or new_deceased):
            # If new expire is later than current expire
            # then update expire
            changes.append(('expire_date', "%s" % new_expire))

        # check account affiliation and status
        changes.extend(self._populate_account_affiliations(acc_id, sysx_id))

        # check gecos?

        # Check if at the affiliation from SystemX could qualify for
        # exchange_mailbox spread
        could_have_exchange = False
        got_exchange = False
        try:
            person_sko = sys_x_affs[sysx_id]
        except KeyError:
            logger.info(
                "person with sysxid: %s does not have active sys_x "
                "affiliation. Ignoring", sysx_id)
            return None
        # No external codes should have exchange spread, except GENØK (999510)
        # and AK (999620) and KUNN (999410) and NorgesUniv (921000)
        if person_sko[0:2] != '99' or person_sko[0:6] in (
                '999510', '999620', '999410', '921000'):
            could_have_exchange = True

        # Run through exchange employee filter
        for skofilter in cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO:
            if skofilter == person_sko[
                            0:len(skofilter)] and not could_have_exchange:
                logger.info(
                    'Not setting exchange spread because OU %s is in '
                    'EMPLOYEE_FILTER_EXCHANGE_SKO', person_sko)
                could_have_exchange = False
                break

        # get all person affiliations. Need em to calculate correct spread
        no_account = False
        try:
            aff_status = person_info['affiliation_status']
            logger.debug("sysx id:%s has affs:'%s'" % (sysx_id, aff_status))
            aff_str = str(co.affiliation_manuell_gjest_u_konto).split("/")
            if aff_status == aff_str[1]:
                no_account = True
        except:
            logger.debug("sysx id:%s has no affs" % (sysx_id))

        # make sure all spreads defined in sysX is set

        tmp_spread = [
            int(co.Spread('system@ldap'))]  # everybody gets this one
        if no_account is False:
            for s in person_info.get('spreads'):
                if s == 'ldap@uit':
                    s = 'people@ldap'
                    tmp_spread.append(int(co.Spread(s)))
                    s = 'system@ldap'
                    tmp_spread.append(int(co.Spread(s)))
                elif s == 'frida@uit':
                    logger.warn("renaming old spread frida to cristin")
                    s = 'cristin@uit'
                    tmp_spread.append(int(co.Spread(s)))
                else:
                    tmp_spread.append(int(co.Spread(s)))
                # if s=='SUT@uit':
                #    got_sut = True
                #    tmp_spread.append(int(co.Spread('fd@uit')))
                if s == "AD_account" and could_have_exchange:
                    got_exchange = True
                    tmp_spread.append(int(co.Spread('exchange_mailbox')))
            # if not got_exchange:
            #    tmp_spread.append(int(co.Spread('sut_mailbox')))
            #    if not got_sut:
            #        tmp_spread.append(int(co.Spread('SUT@uit')))

        # if(no_account == False):
        #     for s in person_info.get('spreads'):
        #         tmp_spread.append(int(co.Spread(s)))
        #         if s=="AD_account" and could_have_exchange:
        #             got_exchange = True
        #             tmp_spread.append(int(co.Spread('exchange_mailbox')))
        #             tmp_spread.append(int(co.Spread('people@ldap')))
        sysX_spreads = Set(tmp_spread)

        # Set spread expire date
        # Use new_expire in order to guarantee that SystemX specific spreads
        # get SystemX specific expiry_dates
        for ss in sysX_spreads:
            spread_acc.set_spread_expire(spread=ss, expire_date=new_expire,
                                         entity_id=acc_id)

        cb_spreads = Set(acc_obj.get_spreads())
        to_add = sysX_spreads - cb_spreads

        if to_add:
            changes.append(('spreads_add', to_add))

        # check account homes for each spread
        # FIXME: Get homes for all spreads.
        #  There is a bug in list_account_home()

        # check quarantine
        if person_info.get('approved') == 'Yes':
            if co.quarantine_sys_x_approved in acc_obj.get_quarantines():
                changes.append(
                    ('quarantine_del', co.quarantine_sys_x_approved))
        else:
            # make sure this account is quarantined
            if co.quarantine_sys_x_approved not in acc_obj.get_quarantines():
                changes.append(
                    ('quarantine_add', co.quarantine_sys_x_approved))

        if changes:

            logger.debug("Changes [%i/%s]: %s" % (
                acc_id,
                sysx_id,
                repr(changes)))
            _handle_changes(acc_id, changes)

            # Add info for template and obfuscate fnr
            if person_info['personnr'] != '':
                person_info['personnr'] = person_info['personnr'][
                                          0:6] + "xxxxx"
            person_info['ou_navn'] = 'N/A'

            ou.clear()
            try:
                ou.find_stedkode(int(person_info['ou'][0:2]),
                                 int(person_info['ou'][2:4]),
                                 int(person_info['ou'][4:6]),
                                 cereconf.DEFAULT_INSTITUSJONSNR)
                person_info['ou_navn'] = ou.name_with_language(co.ou_name,
                                                               co.language_nb)
            except Exception as m:
                logger.warn('OU not found from stedkode: %s. Error was: %s',
                            person_info['ou'], m)

            person_info['kontaktinfo'] = self.unquote_html(
                person_info['kontaktinfo']).replace('<br/>', '\n')
            person_info['hjemmel'] = self.unquote_html(
                person_info['hjemmel']).replace('<br/>', '\n')

            if new_account is True or is_expired is True:
                mailq.append({
                    'account_id': acc_id,
                    'person_info': person_info,
                    'template': 'ansvarlig'
                })
                ansv_rep = person_info.get('ansvarlig_epost')
                logger.warn("sending ansvarlig email to:%s" % ansv_rep)
            _send_mailq(mailq)

    def check_expired_sourcedata(self, expire_date):
        expire = mx.DateTime.DateFrom(expire_date)
        today = mx.DateTime.today()
        if expire < today:
            return True
        else:
            return False

    def _populate_account_affiliations(self, account_id, sysx_id):
        """
        Assert that the account has the same sysX affiliations as the person.

        """

        changes = []
        account_affs = self.accounts[account_id].get_affiliations()

        logger.debug("-->Person SysXID=%s has affs=%s",
                     sysx_id,
                     self.persons[sysx_id].get_affiliations())
        logger.debug(
            "-->Account_id=%s,SysXID=%s has account affs=%s" % (account_id,
                                                                sysx_id,
                                                                account_affs))
        for aff, ou, status in self.persons[sysx_id].get_affiliations():
            if not (aff, ou) in account_affs:
                changes.append(('set_ac_type', (ou, aff)))
        #  TODO: Fix removal of account affs
        return changes


class ExistingAccount(object):
    def __init__(self, sysx_id, expire_date):
        self._affs = []
        self._expire_date = expire_date
        self._sysx_id = sysx_id
        self._owner_id = None
        self._uid = None
        self._home = {}
        self._quarantines = []
        self._spreads = []
        self._traits = []

    def append_affiliation(self, affiliation, ou_id):
        self._affs.append((affiliation, ou_id))

    def append_quarantine(self, q):
        self._quarantines.append(q)

    def append_spread(self, spread):
        self._spreads.append(spread)

    def append_trait(self, trait_code, trait_str):
        self._traits.append((trait_code, trait_str))

    def get_affiliations(self):
        return self._affs

    def get_expire_date(self):
        return self._expire_date

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

    def get_sysxid(self):
        return int(self._sysx_id)

    def get_traits(self):
        return self._traits

    def has_affiliation(self, aff_cand):
        return aff_cand in [aff for aff, ou in self._affs]

    def has_homes(self):
        return len(self._home) > 0

    def set_posix(self, uid):
        self._uid = uid

    def set_home(self, spread, disk_id, homedir_id):
        self._home[spread] = (disk_id, homedir_id)


class ExistingPerson(object):
    def __init__(self):
        self._affs = []
        self._groups = []
        self._spreads = []
        self._accounts = []
        self._deceased_date = None

    def append_affiliation(self, affiliation, ou_id, status):
        self._affs.append((affiliation, ou_id, status))

    def get_affiliations(self):
        return self._affs

    def append_group(self, group_id):
        self._groups.append(group_id)

    def get_groups(self):
        return self._groups

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_spreads(self):
        return self._spreads

    def has_account(self):
        return len(self._accounts) > 0

    def append_account(self, acc_id):
        self._accounts.append(acc_id)

    def get_account(self):
        return self._accounts[0]

    def set_deceased_date(self, deceased_date):
        self._deceased_date = deceased_date

    def get_deceased_date(self):
        return self._deceased_date


def main():
    skipped = added = updated = unchanged = deletedaff = 0

    dryrun = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'd', ['dryrun'])
    except getopt.GetoptError as m:
        print("Unknown option: {}".format(m))
        usage()

    for opt, val in opts:
        if opt in ('--dryrun',):
            dryrun = True

    sysx = SYSX()
    sysx.list()
    persons, accounts = get_existing_accounts()

    build = Build(sysx, persons, accounts)
    build.process_all()

    if dryrun:
        logger.info("Dryrun: Rollback all changes")
        db.rollback()
    else:
        logger.info("Committing all changes to database")
        db.commit()


def usage():
    progname = __file__.split(os.sep)[-1]
    print("""
    usage:: %s [-d|--dryrun]
    --dryrun : do no commit changes to database
    --logger-name name: name of logger to use
    --logger-level level: loglevel to use
    """ % progname)
    sys.exit(1)


if __name__ == '__main__':
    main()
