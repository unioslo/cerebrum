#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2019 University of Oslo, Norway
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
TODO: What is the ultimate goal of this script??

Configuration
-------------
USER_EXPIRE_CONF
    A dict with the following values:

    - FIRST_WARNING: When to issue first expire notification
    - SECOND_WARNING: When to issue second expire notification
    - EXPIRING_THREASHOLD: ???

TEMPLATE_DIR
    Base directory for templates used in this script

USER_EXPIRE_MAIL
    A dict that maps email actions to email templates. Each action is a string
    on the format 'email<n>', where '<n>' is the action number.
    The templates should be relative to ``cereconf.TEMPLATE_DIR``.

    E.g.: ``{'mail1': 'email_template_1.txt', 'mail2': 'email_template_2'}``

USER_EXPIRE_INFO_PAGE
    Template file for the HTML report (relative to ``cereconf.TEMPLATE_DIR``).

"""
import argparse
import cPickle as pickle
import logging
import os

import mx.DateTime

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Entity import EntityName
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.email import sendmail

logger = logging.getLogger(__name__)

# TODO: remove global db-objects, cache
db = co = ac = prs = grp = ou = ef = None
entity2name = {}

today = mx.DateTime.today()
num_sent = 0

FIRST_WARNING = cereconf.USER_EXPIRE_CONF['FIRST_WARNING']
SECOND_WARNING = cereconf.USER_EXPIRE_CONF['SECOND_WARNING']


def get_email_template(action):
    """
    Get email template for a given action.

    :type action: int
    :param action:
        The action to fetch a template for.

    :rtype: list
    :returns:
        The template as a list of template lines. Returns an empty list if
        there is no template available.
    """
    key = 'mail{:d}'.format(action)
    template_dir = cereconf.TEMPLATE_DIR
    try:
        filename = os.path.join(template_dir, cereconf.USER_EXPIRE_MAIL[key])
    except AttributeError:
        logger.error("Missing USER_EXPIRE_MAIL in cereconf",
                     exc_info=True)
        return []
    except KeyError:
        logger.error("Missing template USER_EXPIRE_MAIL[%r] in cereconf",
                     key, exc_info=True)
        return []
    try:
        with open(filename) as f:
            lines = f.readlines()
            if not any(lines):
                logger.warning("template USER_EXPIRE_MAIL[%r] (%s) is empty",
                               key, filename)
            return lines
    except Exception:
        logger.error("Unable to read template USER_EXPIRE_MAIL[%r] (%r)",
                     key, filename, exc_info=True)
        return []


def load_entity_names(db, namespace):
    """Update global entity2name cache with namespace."""
    en = EntityName(db)
    entity2name.update(
        (x['entity_id'], x['entity_name'])
        for x in en.list_names(namespace))


#
# user_expire will not send notification emails from cleomedes.
# these messages are still sendt from leetah
#
def send_mail(uname, user_info, nr, forward=False):
    """
    Get template file based on user_info and expiring action number to create
    Subject and body of mail.

    Get mail addresses based on type of account and expiring action number. If
    a critical error occurs or sending the actual mail fails return False, else
    return True.
    """
    global num_sent

    logger.debug("send_mail(uname=%r, user_info=%r, nr=%r, forward=%r)",
                 uname, user_info, nr, forward)
    ac.clear()
    ac.find_by_name(uname)
    # Do not send mail to quarantined accounts
    if ac.get_entity_quarantine():
        logger.info("Account is quarantened - no mail sent: %s", uname)
        return False

    def compare(a, b):
        return cmp(a['type'], b['type']) or cmp(a['name'], b['name'])

    # Assume that there exists template files for the mail texts
    # and that cereconf.py has the dict USER_EXPIRE_MAIL
    lines = get_email_template(nr)
    if not lines:
        return False

    msg = []
    for line in lines:
        if line.strip().startswith('From:'):
            email_from = line.split(':')[1]
        elif line.strip().startswith('Subject:'):
            subject = line.split(':', 1)[1]
            subject = subject.replace('$USER$', uname)
        else:
            msg.append(unicode(line, 'utf8'))
    body = ''.join(msg)
    body = body.replace('$USER$', uname)
    body = body.replace('$EXPIRE_DATE$', user_info['expire_date'].date)
    # OK, tenk på hvordan dette skal gjøres pent.
    if user_info['ou']:
        body = body.replace('ved $OU$', 'ved %s' % user_info['ou'])
        body = body.replace('at $OU$', 'at %s' % user_info['ou'])

    email_addrs = []
    ac.clear()
    ac.find(user_info['account_id'])
    if ac.owner_type == co.entity_person:
        if nr != 3:    # Don't send mail to account that is expired
            try:
                email_addrs.append(ac.get_primary_mailaddress())
            except Errors.NotFoundError:
                # This account does not have an email address.
                # Return False to indicate no email to be sent
                logger.info("account:%s does not have an associated "
                            "email address", user_info['account_id'])
                return False
        # Get account owner's primary mail address or use current account
        try:
            prs.clear()
            prs.find(ac.owner_id)

            ac_prim = prs.get_primary_account()
            if ac_prim:
                ac.clear()
                ac.find(ac_prim)

            email_addrs.append(ac.get_primary_mailaddress())
        except Errors.NotFoundError:
            logger.warning("Couldn't find acoount owner's primary mail "
                           "adress: %s", uname)
    else:
        logger.debug("Impersonal account %s (%s, %s )",
                     uname, ac.owner_type, co.entity_person)
        # Aargh! Impersonal account. Get all direct members of group
        # that owns account.
        grp.clear()
        grp.find(ac.owner_id)
        members = []
        for row in grp.search_members(group_id=grp.entity_id,
                                      member_type=co.entity_account):
            member_id = int(row["member_id"])
            if member_id not in entity2name:
                logger.warn("No name for member id=%s in group %s %s",
                            member_id, grp.group_name, grp.entity_id)
                continue

            members.append({'id': member_id,
                            'type': str(row["member_type"]),
                            'name': entity2name[member_id]})
        members.sort(compare)
        # get email_addrs for members
        for m in members:
            ac.clear()
            try:
                ac.find(m['id'])
                email_addrs.append(ac.get_primary_mailaddress())
            except Errors.NotFoundError:
                logger.warn("Couldn't find member acoount %s " % m['id'] +
                            "or its primary mail adress")

    if forward:
        ef.clear()
        ef.find_by_target_entity(user_info['account_id'])
        for r in ef.get_forward():
            logger.debug("Forwarding on" + str(r))
            if r['enable'] == 'T':
                email_addrs.append(r['forward_to'])
    # Now send the mail
    email_addrs = unique_list(email_addrs)
    try:
        logger.info("Sending %d. mail To: %s", nr, ', '.join(email_addrs))
        sendmail(
            toaddr=', '.join(email_addrs),
            fromaddr=email_from,
            subject=subject,
            body=body.encode("iso8859-1"))
        if len(email_addrs) > 2:
            logger.error("%s - Should not have more than 2 email addresses",
                         email_addrs)
            return False
        return True
    except Exception as m:
        logger.warn("Couldn't sent mail To: %s Reason: %s",
                    ', '.join(email_addrs), m)
        return False


def decide_expiring_action(expire_date):
    """
    Decide what action to take about this user, based on date, user
    info, calendar exceptions or other types of exceptions.

    :rtype: int
    :return:
        An expire action code:

        *  0: User has no expire date set or expire_date > (today +
              FIRST_WARNING)
        * -1: User is expired and expire_date < (today - EXPIRING_THREASHOLD)
        *  1: User has come within FIRST_WARNING days limit of expire date
        *  2: User has come within SECOND_WARNING days limit of expire date
        *  3: User has become or will be expired within a short period.
        *  4: Normally return value 3 should be returned, but an
        *     exception is valid.
        *  5: Unexpected event.
    """
    if not expire_date:
        return 0
    dt = cereconf.USER_EXPIRE_CONF['EXPIRING_THREASHOLD']
    ret = 0
    # Special case 1: Is today within summer semester (24.06 - 08.08)?
    # It should really be from start of last week of june - end of
    # first week of august, but that is a bit troublesome...
    #              t    t+dt        SEC           FIRST
    # -------------|-----|------------|--------------------|-------
    #   -1         |  3  |     2      |         1          |   0
    if expire_date > (today + FIRST_WARNING):
        ret = 0
    elif expire_date <= today:
        ret = -1
    elif (expire_date <= (today + FIRST_WARNING) and
          expire_date > (today + SECOND_WARNING)):
        ret = 1
    elif (expire_date <= (today + SECOND_WARNING) and
          expire_date > (today + dt)):
        ret = 2
    elif expire_date <= (today + dt) and expire_date > today:
        ret = 3
    else:
        ret = 5
    return ret


def check_users(expiring_data):
    """Get all cerebrum users and check their expire date. If
    expire_date is soon or is passed take the neccessary actions as
    specified in user-expire.rst."""

    def get_expiring_data(row, expire_date):
        home = row.get(['home'])
        if not home:
            home = ''
        try:
            ou_name = get_ou_name(ou_id=row['ou_id'])
        except (KeyError, Errors.NotFoundError):
            ou_name = ''
        return {'account_id': int(row['account_id']),
                'home': home,
                'expire_date': expire_date,
                'ou': ou_name,
                'mail1': None,
                'mail2': None,
                'mail3': None}

    logger.debug("Check expiring info for all user accounts")
    for row in ac.list_all(filter_expired=False):
        uname = row['entity_name']
        ea_nr = decide_expiring_action(row['expire_date'])
        # Check if users expire_date has been changed since last run
        if uname in expiring_data and row['expire_date']:
            user_info = expiring_data[uname]
            new_ed = row['expire_date']
            old_ed = user_info['expire_date']
            if new_ed != old_ed:
                logger.info("Expire date for user %s changed. " % uname +
                            "Old date: %s, new date: %s" % (old_ed, new_ed))
                user_info['expire_date'] = row['expire_date']
                # If expire date is changed user_info['mail<n>'] might need
                # to be updated
                if ea_nr == 0:
                    if (user_info['mail1'] or
                            user_info['mail2'] or
                            user_info['mail3']):
                        # Tell user that expire_date has been reset and account
                        # is out of expire-warning time range
                        send_mail(uname, user_info, 4)
                    user_info['mail1'] = None
                # Do not send mail in these cases. It will be too many
                # mails which might confuse user, IMO.
                if ea_nr in (0, 1, 2):
                    user_info['mail3'] = None
                if ea_nr in (0, 1):
                    user_info['mail2'] = None

        # Check if we need to create or update expiring info for user
        if ea_nr == 0:
            # User not within expire threat range
            continue
        elif ea_nr == -1:
            # User is expired
            if uname not in expiring_data:
                logger.debug("User %s is expired, but no expiring info "
                             "exists - do nothing.", uname)
            continue

        expire_date = row['expire_date']
        if ea_nr == 1:
            # User within threat range 1
            if uname not in expiring_data:
                logger.info("Writing expiring info for %s with "
                            "expire date: %s", uname, str(expire_date))
                expiring_data[uname] = get_expiring_data(row, expire_date)
            if not expiring_data[uname]['mail1']:
                if send_mail(uname, expiring_data[uname], 1):
                    expiring_data[uname]['mail1'] = today
        elif ea_nr == 2:
            # User within threat range 2
            if uname in expiring_data:
                if not expiring_data[uname]['mail1']:
                    logger.warn("%s expire_date - today <= %s, but first "
                                "warning mail was not sent",
                                uname, SECOND_WARNING)
            else:
                logger.warn("expire_date - today <= %s, but no expiring info "
                            " exists for %s. Create info and send mail.",
                            uname, SECOND_WARNING)
                expiring_data[uname] = get_expiring_data(row, expire_date)
            if not expiring_data[uname]['mail2']:
                if send_mail(uname, expiring_data[uname], 2):
                    expiring_data[uname]['mail2'] = today
        elif ea_nr == 3:
            # User is about to expire
            if uname in expiring_data:
                if not expiring_data[uname]['mail1']:
                    logger.warn("%s: expire date reached, but first warning "
                                "mail was not sent", uname)
                if not expiring_data[uname]['mail2']:
                    logger.warn("%s: expire date reached, but second warning "
                                "mail was not sent", uname)
                if not expiring_data[uname]['mail3']:
                    if send_mail(uname, expiring_data[uname], 3, forward=True):
                        expiring_data[uname]['mail3'] = today
            else:
                logger.warn("User %s is about to expire, but no expiring info "
                            "exists. Create info and send mail.", uname)
                expiring_data[uname] = get_expiring_data(row, expire_date)
                if send_mail(uname, expiring_data[uname], 3, forward=True):
                    expiring_data[uname]['mail3'] = today
        elif ea_nr == 4:
            # Summer exception
            # User should normally be expired but an exception is at hand
            # Extend expire_date with two months
            ac.expire_date += mx.DateTime.RelativeDateTime(months=+2)
            ac.write_db()
            if uname in expiring_data:
                # send_mail(uname, expiring_data[uname], 4, forward=True)
                if expiring_data[uname]['mail2']:
                    expiring_data[uname]['mail2'] = None
        elif ea_nr == 5:
            # Error situation
            logger.error("None of the tests in check_users matched, "
                         "user_info=%s", repr(row))


# FIXME, vi kan muligens fjerne denne og bruke rapporteringsverktøyet
# for å lage denne oversikten i stedet.
# TODO: Replace template file with jinja2 template and proper HTML lists
def write_report(cache, report_file):
    """Generate info about expired users and create a web page"""
    has_expired = []
    got_mail2 = []
    will_expire = []
    for uname, user_info in cache.items():
        # Find users that has expired last FIRST_WARNING days
        if (user_info['mail1'] and
                (user_info['expire_date'] + FIRST_WARNING) > today):
            has_expired.append((uname, user_info['home']))
        # Find users that has been sent mail2 during the last SECOND_WARNING
        # days
        if (user_info['mail2'] and
                (user_info['mail2'] + SECOND_WARNING) > today):
            got_mail2.append((uname, user_info['home']))
        # Find users that will expire the next 5 days
        if (user_info['expire_date'] - 5) <= today:
            will_expire.append((uname, user_info['home']))

    context = {
        'HAS_EXPIRED': "\n".join(', '.join(tup) for tup in has_expired),
        'WILL_EXPIRE': "\n".join(', '.join(tup) for tup in will_expire),
        'GOT_MAIL': "\n".join(', '.join(tup) for tup in got_mail2),
    }

    # Get web page template
    template_file = os.path.join(cereconf.TEMPLATE_DIR,
                                 cereconf.USER_EXPIRE_INFO_PAGE)
    with open(template_file, 'r') as f:
        report = f.read()

    for k in context:
        report = report.replace("${" + k + "}", context[k])

    # Write file
    with open(report_file, 'w') as f:
        f.write(report)


def unique_list(seq):
    """Strip duplicates from a sequence."""
    seen = set()
    seen_add = seen.add  # prevents attr lookup on seen for each iteration
    return [x for x in seq if not (x in seen or seen_add(x))]


def get_ou_name(self, ou_id):
    ou.clear()
    ou.find(ou_id)
    return "%s (%02i%02i%02i)" % (ou.get_name_with_language(co.ou_name_short,
                                                            co.language_nb,
                                                            default=''),
                                  ou.fakultet, ou.institutt,
                                  ou.avdeling)


def load_cache(filename):
    """Load cache dict from file."""
    cache = {}
    if os.path.exists(filename):
        logger.info("Loading cache from file %r", filename)
        try:
            with open(filename, 'r') as f:
                cache.update(pickle.load(f))
            logger.info("Loaded %d items from cache", len(cache))
        except Exception:
            logger.error("Unable to load cache file %r",
                         filename, exc_info=True)
    else:
        logger.info("No cache file %r", filename)
    return cache


def dump_cache(cache, filename):
    """Dump cache dict to file."""
    logger.info("Dumping %d cached items to file %r",
                len(cache), filename)
    with open(filename, 'w') as f:
        pickle.dump(cache, f)


epilog = """
A cache file must always be specified. It can be non-existing or
empty, but without record of earlier data a lot of warnings will
be generated and expiring users might get duplicate warning mails.

generate_info reads the cache from a cache file and generates a
html file with info about expiring users.
""".strip()


def main(inargs=None):
    global db, co, ac, prs, grp, ou, ef

    parser = argparse.ArgumentParser(
        description="Process entity expire dates",
        epilog=epilog,
    )
    parser.add_argument(
        '--cache',
        dest='cache_file',
        required=True,
        help='Use cache %(metavar)s for comparison between runs',
        metavar='<cache-file>',
    )
    parser.add_argument(
        '--generate-info',
        dest='report_file',
        help='Write a HTML report on expired users to %(metavar)s',
        metavar='<report-file>',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    prs = Factory.get('Person')(db)
    grp = Factory.get('Group')(db)
    ou = Factory.get('OU')(db)
    ef = Email.EmailForward(db)

    for namespace in (co.account_namespace, co.group_namespace):
        logger.debug("Caching %s names", namespace)
        load_entity_names(db, namespace)

    cache = load_cache(args.cache_file)
    check_users(cache)
    dump_cache(cache, args.cache_file)

    # TODO: if commit, do that before rendering template - as the emails have
    # already been sent - if case rendering fails.

    if args.report_file:
        logger.info("Generating report")
        write_report(cache, args.report_file)
        logger.info("Report written to %r", args.report_file)

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
