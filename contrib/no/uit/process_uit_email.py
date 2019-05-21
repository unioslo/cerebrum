#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
This script creates/updates email addresses for all accounts in cerebrum
that has a email spread.
"""

import argparse
import logging

import cereconf
import Cerebrum.logutils

from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailAddress
from Cerebrum.modules.no.uit import Email
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)

try_only_first = False
uit_addresses_in_use = []
uit_addresses_new = []
uit_account_affs = {}
exch_users = {}
uname2accid = {}
ownerid2uname = {}
uit_mails = {}
num2const = {}


def get_sko(ou, ou_id):
    ou.clear()
    ou.find(ou_id)
    return "{0}{1}{2}".format(str(ou.fakultet).zfill(2),
                              str(ou.institutt).zfill(2),
                              str(ou.avdeling).zfill(2))


get_sko = memoize(get_sko)


def _get_alternatives(ac, account_name):
    ac.clear()
    ac.find_by_name(account_name)
    alternatives = []
    first_choise = ac.get_email_cn_local_part(given_names=1,
                                              max_initials=1,
                                              keep_dash=True)
    alternatives.append(first_choise)

    #    #FIXME this part of the function slows things down. Alot! 20x'ish!
    #    #The reason is that get_email_cn_local_part instansiates a person_obj
    #    # then does a find(person_id), followed by get_names(system_cached)
    #    for each call to that function!
    #    #find other alternatives!
    given_names = (3, 2, 1, 0, -1)
    max_initials = (1, 2, 0, 3, 4)
    for nm in given_names:
        for mlm in max_initials:
            for dash in (True, False):
                local_part = ac.get_email_cn_local_part(given_names=nm,
                                                        max_initials=mlm,
                                                        keep_dash=dash)
                if "." not in local_part:
                    continue
                if local_part not in alternatives:
                    alternatives.append(local_part)
    logger.debug("Alternatives for %s: %s", account_name, alternatives)
    return alternatives


def is_cnaddr_free(local_part, domain_part):
    addr = "@".join((local_part, domain_part))
    if addr in uit_addresses_in_use:
        logger.error("Address %s not free, in DB", addr)
        return False
    elif addr in uit_addresses_new:
        logger.error("Address %s not free, in new set", addr)
        return False
    return True


def has_cnaddr_in_domain(adresses, domain_part):
    """
    Check if a list of addresses in a given domain contains a cnaddr
    style address.
    """
    test_str = "@{0}".format(domain_part)
    result = None
    for addr in adresses:
        logger.debug("has_cnaddr_in_domain, cheking %s", addr)
        if addr.endswith(test_str):
            try:
                addr.split("@")[0].index(".")
                logger.debug("has_cnaddr_in_domain found %s", addr)
                result = addr.split("@")[0]
                break  # exit loop
            except ValueError:
                # "." not found in addr, not a cn-style addr then
                pass
    logger.debug("has_cnaddr_in_domain returns %s", result)
    return result


def emailaddress_in_exchangecontrolled_domain(address):
    """
    Checks if address given is in one of the exchange controlled domains.

    Returns empty list if none of these matches or list of domains it matches.
    """
    if address is None:
        return []
    return [domain for domain in cereconf.EXCHANGE_CONTROLLED_DOMAINS if
            address.endswith("@{0}".format(domain))]


def get_cn_addr(ac, username, domain):
    old_cn = has_cnaddr_in_domain(uit_mails.get(username, []), domain)
    logger.debug("old cn is:%s", old_cn)
    if old_cn:
        return old_cn

    alternatives = _get_alternatives(ac, username)
    if try_only_first:
        logger.info("Trying only first alternative!")
        alternatives = alternatives[:1]
        for em_addr in alternatives:
            if is_cnaddr_free(em_addr, domain):
                return em_addr
            else:
                logger.error("First alternative not free! %s@%s/%s",
                             em_addr, domain, username)
    else:
        for em_addr in alternatives:
            if is_cnaddr_free(em_addr, domain):
                return em_addr
            else:
                logger.error("alternative not free! %s@%s/%s",
                             em_addr, domain, username)
        # logger.error("NOT IMPLEMENTED, only using suggested mailaddr nr 1")
    return None


def calculate_uit_emails(ac, co, uname, affs):
    """
    Calculate aliases and primary email for user: uname and affiliation: affs.
    """
    cnaddr = False
    # logger.debug("in calculate_uit_emails:%s" % affs)
    for (aff, sko, status) in affs:
        # set cnaddr == true if you are an employee (but not if you are a
        # "timelønnet employee")
        if aff == co.affiliation_ansatt:
            valid_cnaddr_aff = False
            for item in status:
                if item != co.affiliation_status_timelonnet_midlertidig:
                    valid_cnaddr_aff = True
            if valid_cnaddr_aff:
                cnaddr = True

                # even if you are an employee you do not get cnaddr==True if
                # you belong to a stedkode defined in
                # EMPLOYEE_FILTER_EXCHANGE_SKO
                for flt in cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO:
                    # TBD hva om bruker har flere affs og en av dem matcher?
                    # TBD kanskje også se på priority mellom affs?
                    if sko.startswith(flt):
                        logger.warning(
                            "employee %s has affiliation with sko(%s) that "
                            "is in cn-filterset %s",
                            uname, sko, flt)
                        cnaddr = False

        elif co.affiliation_status_student_drgrad in status:
            cnaddr = True
            logger.debug("aff:%s, aff status:%s", aff, status)
            for flt in cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO:
                # TBD hva om bruker har flere affs og en av dem matcher?
                # TBD kanskje også se på priority mellom affs?
                logger.debug("Filter: %s on %s", flt, sko)
                if sko.startswith(flt):
                    logger.warning(
                        "drgrad student %s has affiliation with sko(%s) "
                        "that is in cn-filterset %s",
                        uname, sko, flt)
                    cnaddr = False

    new_addrs = []
    primary = ""

    if cnaddr:
        dom_part = "uit.no"
        # dom_part=cereconf.EMPLOYEE_MAILDOMAIN

        # TBD if user already has CNADDR in @uit.no, no recalculation needed.
        # if we do recalculation, script runningtime multiplies due to
        # large number of cerebrum object instansiations
        user_cn = get_cn_addr(ac, uname, dom_part)
        if user_cn:
            cnaddr = "@".join((user_cn, dom_part))
            new_addrs.append(cnaddr)
            primary = cnaddr

        # Should always have a uidaddr in this domain
        uidaddr = "@".join((uname, dom_part))
        new_addrs.append(uidaddr)
        if not primary:
            primary = uidaddr

    else:
        dom_part = "post.uit.no"
        # dom_part=cereconf.NONEMPLOYEE_MAILDOMAIN
        uidaddr = "@".join((uname, dom_part))
        new_addrs.append(uidaddr)
        if not primary:
            primary = uidaddr

    return new_addrs, primary


def process_mail(db):
    logger.info("Start Caching affiliations")
    ac = Factory.get('Account')(db)
    p = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    ou = Factory.get('OU')(db)

    emdb = Email.email_address(db, logger=logger)

    phone_list = {}
    # get all account affiliations that belongs to UiT
    aff_cached = aff_skipped = 0
    for row in ac.list_accounts_by_type(filter_expired=True,
                                        primary_only=False,
                                        fetchall=False):
        p.clear()
        p.find(row['person_id'])

        # get person work phone number
        # phone_list = p.get_contact_info(source = const.system_tlf,type =
        # const.contact_phone)
        # save the data on the form {account_id: phonenr}
        temp_list = p.get_contact_info(source=co.system_tlf,
                                       type=co.contact_phone)
        try:
            phone_list[row['account_id']] = temp_list[0][4]
        except IndexError:
            phone_list[row['account_id']] = ''

        person_affs = p.get_affiliations(include_deleted=False)
        aff_status = {}
        for item in person_affs:
            try:
                aff_status[item['affiliation']] += [item['status']]
            except KeyError:
                aff_status[item['affiliation']] = [item['status']]

        if row['affiliation'] in (co.affiliation_ansatt,
                                  co.affiliation_student,
                                  co.affiliation_tilknyttet,
                                  co.affiliation_manuell):
            try:
                uit_account_affs.setdefault(
                    row['account_id'],
                    []).append((row['affiliation'],
                                get_sko(ou, row['ou_id']),
                                aff_status[row['affiliation']]))
            except EntityExpiredError:
                # get_sko cannot find active stedkode. continue to next account
                logger.debug(
                    "unable to get affiliation stedkode ou_id:%s for "
                    "account_id:%s Skip.",
                    row['ou_id'], row['account_id'])
                continue
            except KeyError:
                pass
            aff_cached += 1
        else:
            aff_skipped += 1
    logger.debug("Cached %d affiliations", aff_cached)

    logger.info("Start get constants")
    for c in dir(co):
        tmp = getattr(co, c)
        if isinstance(tmp, _CerebrumCode):
            num2const[int(tmp)] = tmp

    logger.info("Get all accounts with AD_account spread")
    count = 0
    skipped = 0
    for a in ac.search(spread=co.spread_uit_ad_account):
        if a['account_id'] in uit_account_affs.keys():
            count += 1
            exch_users[a['account_id']] = a['name']
            uname2accid[a['name']] = a['account_id']
            ownerid2uname.setdefault(a['owner_id'], []).append(a['name'])
    logger.info("got %d accounts (%s)", len(exch_users), count)
    logger.info("got %d account", len(uname2accid))
    logger.info("skipped %d account", skipped)
    for owner, uname in ownerid2uname.iteritems():
        if len(uname) > 1:
            logger.debug(
                "Owner %s has %s accounts: %s", owner, len(uname), uname)

    logger.info("get all email targets for uit")
    mail_addr_cache = 0
    for uname, data in ac.getdict_uname2mailinfo().iteritems():
        if uname2accid.get(uname, None):  # account is in our working set
            for em in data:
                if em['domain'].endswith('uit.no'):
                    mail_addr_cache += 1
                    uit_mails.setdefault(uname, []).append(
                        "@".join((em['local_part'], em['domain'])))

    logger.debug("Cached %d mailaddrs", mail_addr_cache)
    logger.debug("Caching primary mailaddrs")
    current_primaryemail = ac.getdict_uname2mailaddr(primary_only=True)

    # variabled holding whoom shall we build emailaddrs for?
    all_emails = {}
    new_primaryemail = {}
    for account_id, uname in exch_users.iteritems():

        # need to calculate what address(es) user should have
        # then compare to what address(es) they have.
        old_addrs = uit_mails.get(uname, None)
        logger.debug("old addrs=%s", old_addrs)
        old_addrs_set = set(old_addrs)
        should_have_addrs, new_primary_addr = calculate_uit_emails(
            ac,
            co,
            uname,
            uit_account_affs.get(account_id))
        new_primaryemail[account_id] = new_primary_addr

        logger.debug("should have addrs=%s", should_have_addrs)
        logger.debug("new primary is %s", new_primary_addr)
        logger.debug("current primary is %s",
                     current_primaryemail.get(uname, None))
        should_have_addrs_set = set(should_have_addrs)

        if old_addrs:
            logger.debug("User %s has mailaddress %s", uname, old_addrs)
            new_addrs_set = should_have_addrs_set - old_addrs_set
        else:
            new_addrs_set = should_have_addrs_set

        if list(new_addrs_set):
            logger.info("user %s is missing UIT email address %s, queueing",
                        uname, list(new_addrs_set))
            uit_addresses_new.extend(list(new_addrs_set))
            all_emails[account_id] = list(new_addrs_set)
        else:
            logger.debug("compare primary:%s = %s",
                         current_primaryemail.get(uname, None),
                         new_primary_addr)

            def contains_digits(new_primary_addr):
                c = ""
                for i in new_primary_addr:
                    if i.isdigit():
                        c += i
                if c != "":
                    return True
                else:
                    return False

            # if new_email_style = False => email is employee style
            # if new_email_style == True => email is student style
            new_email_style = contains_digits(new_primary_addr)
            if current_primaryemail.get(uname, None) is not None:
                old_email_style = contains_digits(
                    current_primaryemail.get(uname, None))

            logger.debug("old email style:%s ,new email style:%s for email:%s",
                         old_email_style, new_email_style, new_primary_addr)

            # Only change primary email if new_email_style != old_email_style.
            # Meaning one is of student style and the other of employee style
            # This ensures we don't change primary address within each domain,
            # even if calculate_primary_email says so.
            if (list(new_addrs_set) == [] and
                    current_primaryemail.get(uname, None) !=
                    new_primary_addr and new_email_style != old_email_style):
                # if old primary is empty, then set primary, even if
                # new_addrs_set is empty
                logger.debug(
                    "We are to change primary to:%s", new_primary_addr)
                new_primary_addr_list = []
                new_primary_addr_list.append(new_primary_addr)
                new_primary_addr_set = set(new_primary_addr_list)

                uit_addresses_new.extend(new_primary_addr_set)
                all_emails[account_id] = new_primary_addr_set

            else:
                logger.info("User %s already has correct addresses",
                            uname)

    # update all email addresses
    logger.debug("Update %s accounts with UiT emailaddresses",
                 len(all_emails))
    for account_id, emaillist in all_emails.iteritems():
        for addr in emaillist:
            is_primary = False
            new_primary_address = new_primaryemail.get(account_id, None)
            current_primary_address = current_primaryemail.get(
                exch_users.get(account_id), None)
            exchange_controlled = 'NA'
            logger.debug("now cheking if any emails needs to be changed")
            logger.debug("addr:%s == primary_address:%s",
                         addr, new_primary_address)
            if addr == new_primary_address:
                exchange_controlled = \
                    emailaddress_in_exchangecontrolled_domain(
                        current_primary_address)
                logger.debug(
                    "new_primary_adress:%s != current_primary_adress:%s",
                    new_primary_address, current_primary_address)
                if ((new_primary_address != current_primary_address) and
                        (not exchange_controlled)):

                    affs = ",".join(
                        ["@".join((str(num2const[status[0]]), sko)) for
                         aff, sko, status in
                         uit_account_affs.get(account_id, ())])
                    affs = affs.replace("/", ",")
                    account_primary_affiliation = get_priority(db, account_id)
                    logger.debug("Affs:%s", affs)

                    logger.info("Changing Primary address: %s;%s;%s;%s;%s;%s",
                                exch_users[account_id],
                                phone_list[account_id],
                                current_primary_address,
                                new_primary_address,
                                account_primary_affiliation,
                                affs)
                    is_primary = True
            logger.debug("Set mailaddr %s/%s/%s/%s(%s)",
                         account_id, exch_users[account_id], addr, is_primary,
                         exchange_controlled)

            emdb.process_mail(account_id, addr, is_primary=is_primary)


def get_priority(db, account_id):
    """
    Returns account primary affiliation based on
    cereconf.ACCOUNT_PRIORITY_RANGES
    """
    logger.debug("calculate primary affiliation based on "
                 "cereconf.ACCOUNT_PRIORITY_RANGES")
    pri_ranges = cereconf.ACCOUNT_PRIORITY_RANGES
    priority = 1000
    tmp_ac = Factory.get('Account')(db)
    tmp_ac.clear()
    tmp_ac.find(account_id)
    ac_list = tmp_ac.get_account_types()
    for ac_entry in ac_list:
        if ac_entry['priority'] < priority:
            priority = ac_entry['priority']

    for key, val in pri_ranges.iteritems():
        for affiliation, range in val.iteritems():
            if priority <= range[1] and priority >= range[0]:
                return key


def get_existing_emails(db):
    """
    Return list of all email addresses with domain = 'post.uit.no' or 'uit.no',

    format is: uit_addresse_in_use = ['localpart@domainpart']..
    [localpart@domainpart]]
    """
    ea = EmailAddress(db)
    addresses_in_use = []
    uit_no_list = ea.list_email_addresses_ext('uit.no')

    # TODO: Use the post addresses as well.
    post_uit_no_list = ea.list_email_addresses_ext('post.uit.no')
    for item in uit_no_list:
        email_address = "{0}@{1}".format(item['local_part'], item['domain'])
        addresses_in_use.append(email_address)
        logger.debug("existing email: %s", email_address)
    return addresses_in_use


def main():
    global persons, accounts, uit_addresses_in_use
    import datetime as dt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c',
                        '--commit',
                        dest='commit',
                        action='store_true',
                        help='Commit changes to database',
                        )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='process_uit_email')

    starttime = dt.datetime.now()

    uit_addresses_in_use = get_existing_emails(db)
    process_mail(db)

    if args.commit:
        db.commit()
        logger.info("Committing all changes to DB")
    else:
        db.rollback()
        logger.info("Dryrun, rollback changes")

    endtime = dt.datetime.now()
    runningtime = endtime - starttime
    logger.info("Script running time was %s",
                str(dt.timedelta(seconds=runningtime.seconds)))


if __name__ == '__main__':
    main()
