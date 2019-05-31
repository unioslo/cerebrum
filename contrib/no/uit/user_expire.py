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
Send email notifications to users with an expire_date in the near future.

Configuration
-------------
USER_EXPIRE_CONF
    A mapping of when to issue the different notifications, in days relative to
    the current date.
    Should be a dict with the following values:

    - FIRST_WARNING: When to issue first expire notification
    - SECOND_WARNING: When to issue second expire notification
    - EXPIRING_THREASHOLD: When to issue last warning

    Note that FIRST_WARNING > SECOND_WARNING > EXPIRING_THREASHOLD, otherwise
    the user will get the wrong notifications.

TEMPLATE_DIR
    Base directory for templates used in this script

USER_EXPIRE_MAIL
    A dict that maps email names to actual email templates. Each name is a
    string on the format 'email<n>', where '<n>' is a number 1-4.
    The templates should be relative to ``cereconf.TEMPLATE_DIR``.

    E.g.: ``{'mail1': 'email_template_1.txt', 'mail2': 'email_template_2'}``

USER_EXPIRE_INFO_PAGE
    Template file for the HTML report (relative to ``cereconf.TEMPLATE_DIR``).

"""
import argparse
import cPickle as pickle
import datetime
import io
import logging
import os

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


class _EmailTemplates(object):
    """
    Settings for the email templates.
    """
    email_templates = dict(
        (name, os.path.join(cereconf.TEMPLATE_DIR, value))
        for name, value in cereconf.USER_EXPIRE_MAIL.items())

    template_encoding = 'utf-8'

    # First expire notification template
    email_first = 1

    # Second expire notification template
    email_second = 2

    # Last expire notification template
    email_soon = 3

    # Expire notification reset template
    email_reset = 4

    def get_template(self, template_no):
        """
        Get email template for a given action.

        :type template_no: int
        :param template_no:
            The template to fetch.

        :rtype: list
        :returns:
            The template as a list of template lines. Returns an empty list if
            there is no template available.
        """
        key = 'mail{:d}'.format(template_no)
        try:
            filename = self.email_templates[key]
        except AttributeError:
            logger.error("Missing USER_EXPIRE_MAIL in cereconf",
                         exc_info=True)
            return []
        except KeyError:
            logger.error("Missing template USER_EXPIRE_MAIL[%r] in cereconf",
                         key, exc_info=True)
            return []
        try:
            with io.open(filename, 'r', encoding=self.template_encoding) as f:
                lines = f.readlines()
                if not any(lines):
                    logger.warning("template USER_EXPIRE_MAIL[%r] (%s) is "
                                   "empty", key, filename)
                return lines
        except Exception:
            logger.error("Unable to read template USER_EXPIRE_MAIL[%r] (%r)",
                         key, filename, exc_info=True)
            return []


email_templates = _EmailTemplates()


class _ExpireSettings(object):
    """
    Settings for the expire notifications.
    """

    delta_threshold = datetime.timedelta(
        days=cereconf.USER_EXPIRE_CONF['EXPIRING_THREASHOLD'])

    delta_first_warning = datetime.timedelta(
        days=cereconf.USER_EXPIRE_CONF['FIRST_WARNING'])

    delta_second_warning = datetime.timedelta(
        days=cereconf.USER_EXPIRE_CONF['SECOND_WARNING'])

    # User has an expire_date that has expired
    action_expired = -1

    # User has no expire date, or expire date is too far into the future
    action_none = 0

    # User has an expire date which will be reached within <first-warning>,
    action_first_warn = 1

    # User has an expire date which will be reached within <second-warning>,
    action_second_warn = 2

    # User has an expire date which will be reached within <threshold>
    action_soon = 3

    def __init__(self):
        self.today = datetime.date.today()

    def get_action(self, expire_date):
        if not expire_date:
            # no expire_date, no action
            return self.action_none
        elif expire_date <= self.today:
            # expire_date already reached
            return self.action_expired
        elif expire_date <= (self.today + self.delta_threshold):
            # expire_date will be reached within <delta_threshold>
            return self.action_soon
        elif expire_date <= (self.today + self.delta_second_warning):
            # expire_date will be reached within <delta_second_warning>
            return self.action_second_warn
        elif expire_date <= (self.today + self.delta_first_warning):
            # will be reached within <delta_first_warning>
            return self.action_first_warn
        else:
            # expire_date more than <delta_first_warning> into the future
            return self.action_none


expire_settings = _ExpireSettings()


class UserExpireUtil(object):

    def __init__(self, db, dryrun):
        self.db = db
        self.co = Factory.get('Constants')(db)
        self.dryrun = dryrun

        en = EntityName(self.db)
        self.entity2name = {}
        for namespace in (self.co.account_namespace, self.co.group_namespace):
            logger.debug("Caching %s names", namespace)
            self.entity2name.update(
                (x['entity_id'], x['entity_name'])
                for x in en.list_names(namespace))

    def get_email_addresses(self, account_id, template_nr, forward):
        """
        Get email addresses for a given account_id
        """
        email_addrs = []

        ac = Factory.get('Account')(self.db)
        ac.find(account_id)
        uname = ac.account_name
        owner_type = self.co.EntityType(ac.owner_type)

        if owner_type == self.co.entity_person:
            if template_nr != email_templates.email_soon:
                # Don't send mail to account that is expired
                try:
                    email_addrs.append(ac.get_primary_mailaddress())
                except Errors.NotFoundError:
                    # This account does not have an email address.
                    # Return empty list to indicate no email to be sent
                    logger.info("account_id=%r (%s) does not have an "
                                "associated email address", account_id, uname)
                    return []
            # Get account owner's primary mail address or use current account
            prs = Factory.get('Person')(self.db)
            try:
                prs.find(ac.owner_id)
                ac_prim = prs.get_primary_account()
                if ac_prim:
                    ac.clear()
                    ac.find(ac_prim)

                email_addrs.append(ac.get_primary_mailaddress())
            except Errors.NotFoundError:
                logger.warning("Could not find primary email address for "
                               "account_id=%r (%s), owner_id=%r",
                               account_id, uname, ac.owner_id)
        else:
            logger.debug("Impersonal account_id=%r (%s), owner_type=%s",
                         account_id, uname, owner_type)
            # Aargh! Impersonal account. Get all direct members of group
            # that owns account.
            grp = Factory.get('Group')(self.db)
            grp.find(ac.owner_id)
            members = []
            for row in grp.search_members(group_id=grp.entity_id,
                                          member_type=self.co.entity_account):
                member_id = int(row["member_id"])
                if member_id not in self.entity2name:
                    logger.warn("No name for member id=%s in group %s %s",
                                member_id, grp.group_name, grp.entity_id)
                    continue

                members.append({
                    'id': member_id,
                    'type': str(row["member_type"]),
                    'name': self.entity2name[member_id],
                })
            # get email_addrs for members
            for m in sorted(members,
                            key=lambda d: (d.get('type'), d.get('name'))):
                ac.clear()
                try:
                    ac.find(m['id'])
                    email_addrs.append(ac.get_primary_mailaddress())
                except Errors.NotFoundError:
                    logger.warning("Could not find member email address for "
                                   "owner_id=%r, member_id=%r (%s)",
                                   ac.owner_id, m['id'], m['name'])

        if forward:
            ef = Email.EmailForward(self.db)
            ef.find_by_target_entity(account_id)
            for r in ef.get_forward():
                logger.debug("Forwarding on: %s", repr(r))
                if r['enable'] == 'T':
                    email_addrs.append(r['forward_to'])

        return unique_list(email_addrs)

    #
    # user_expire will not send notification emails from cleomedes.
    # these messages are still sendt from leetah
    #
    def send_mail(self, uname, user_info, nr, forward=False):
        """
        Get template file based on user_info and expiring action number to
        create Subject and body of mail.

        Get mail addresses based on type of account and expiring action number.
        If a critical error occurs or sending the actual mail fails return
        False, else return True.
        """
        logger.debug("send_mail(uname=%r, user_info=%r, nr=%r, forward=%r)",
                     uname, user_info, nr, forward)

        ac = Factory.get('Account')(self.db)
        ac.find_by_name(uname)
        # Do not send mail to quarantined accounts
        if ac.get_entity_quarantine():
            logger.info("Account is quarantened - no mail sent: %s", uname)
            return False

        # Assume that there exists template files for the mail texts
        # and that cereconf.py has the dict USER_EXPIRE_MAIL
        lines = email_templates.get_template(nr)
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
                msg.append(line)
        body = ''.join(msg)
        body = body.replace('$USER$', uname)
        body = body.replace('$EXPIRE_DATE$',
                            user_info['expire_date'].strftime('%Y-%m-%d'))

        # OK, tenk på hvordan dette skal gjøres pent.
        if user_info['ou']:
            body = body.replace('ved $OU$', 'ved %s' % user_info['ou'])
            body = body.replace('at $OU$', 'at %s' % user_info['ou'])

        email_addrs = self.get_email_addresses(user_info['account_id'],
                                               nr, forward)
        if not email_addrs:
            logger.warning("No email addresses available for user_info=%s",
                           repr(user_info))
            return False

        try:
            logger.info("Sending %d. mail To: %s", nr, ', '.join(email_addrs))
            sendmail(
                toaddr=', '.join(email_addrs),
                fromaddr=email_from,
                subject=subject,
                body=body.encode("iso8859-1"),
                debug=self.dryrun,
            )
            if len(email_addrs) > 2:
                logger.warning("Multiple email addrs for account_id=%r (%r)",
                               user_info['account_id'], email_addrs)
                # TODO: We return False, even though we sent emails?
                return False
            return True
        except Exception:
            logger.error("Could not send mail To: %s",
                         ', '.join(email_addrs), exc_info=True)
            return False

    def get_ou_name(self, ou_id):
        ou = Factory.get('OU')(self.db)
        ou.find(ou_id)
        return "%s (%02i%02i%02i)" % (
            ou.get_name_with_language(self.co.ou_name_short,
                                      self.co.language_nb,
                                      default=''),
            ou.fakultet, ou.institutt, ou.avdeling)

    def check_users(self, expiring_data):
        """Get all cerebrum users and check their expire date. If
        expire_date is soon or is passed take the neccessary actions as
        specified in user-expire.rst."""
        today = expire_settings.today

        def get_expiring_data(row, expire_date):
            home = row.get(['home'])
            if not home:
                home = ''
            try:
                ou_name = self.get_ou_name(row['ou_id'])
            except (KeyError, Errors.NotFoundError):
                ou_name = ''
            return {
                'account_id': int(row['account_id']),
                'home': home,
                'expire_date': expire_date,
                'ou': ou_name,
                'mail1': None,
                'mail2': None,
                'mail3': None,
            }

        logger.debug("Check expiring info for all user accounts")
        ac = Factory.get('Account')(self.db)
        for row in ac.list_all(filter_expired=False):
            uname = row['entity_name']
            expire_date = (row['expire_date'].pydate()
                           if row['expire_date'] else None)
            ea_nr = expire_settings.get_action(expire_date)
            # Check if users expire_date has been changed since last run
            if uname in expiring_data and expire_date:
                user_info = expiring_data[uname]
                new_ed = expire_date
                old_ed = user_info['expire_date']
                if new_ed != old_ed:
                    logger.info("Expire date for user %r changed from "
                                "old_date=%s to new_date=%s. ",
                                uname, repr(old_ed), repr(new_ed))
                    user_info['expire_date'] = expire_date
                    # If expire date is changed user_info['mail<n>'] might need
                    # to be updated
                    if ea_nr == expire_settings.action_none:
                        if (user_info['mail1'] or
                                user_info['mail2'] or
                                user_info['mail3']):
                            # Tell user that expire_date has been reset and
                            # account is out of expire-warning time range
                            self.send_mail(uname, user_info,
                                           email_templates.email_reset)
                        user_info['mail1'] = None
                    # Do not send mail in these cases. It will be too many
                    # mails which might confuse user, IMO.
                    if ea_nr in (expire_settings.action_none,
                                 expire_settings.action_first_warn,
                                 expire_settings.action_second_warn):
                        user_info['mail3'] = None
                    if ea_nr in (expire_settings.action_none,
                                 expire_settings.action_first_warn):
                        user_info['mail2'] = None

            # Check if we need to create or update expiring info for user
            if ea_nr == expire_settings.action_none:
                # User not within expire threat range
                continue
            elif ea_nr == expire_settings.action_expired:
                # User is expired
                continue

            if ea_nr == expire_settings.action_first_warn:
                # User within threat range 1
                if uname not in expiring_data:
                    logger.info("Writing expiring info for %s with "
                                "expire date: %s", uname, str(expire_date))
                    expiring_data[uname] = get_expiring_data(row, expire_date)
                if not expiring_data[uname]['mail1']:
                    if self.send_mail(uname, expiring_data[uname],
                                      email_templates.email_first):
                        expiring_data[uname]['mail1'] = today
            elif ea_nr == expire_settings.action_second_warn:
                # User within threat range 2
                if uname in expiring_data:
                    if not expiring_data[uname]['mail1']:
                        logger.warn("%s expire_date - today <= %s, but first "
                                    "warning mail was not sent", uname,
                                    expire_settings.delta_second_warning)
                else:
                    logger.warn("expire_date - today <= %s, but no expiring "
                                "info exists for %s. Create info and send "
                                "mail.",
                                uname, expire_settings.delta_second_warning)
                    expiring_data[uname] = get_expiring_data(row, expire_date)
                if not expiring_data[uname]['mail2']:
                    if self.send_mail(uname, expiring_data[uname],
                                      email_templates.email_second):
                        expiring_data[uname]['mail2'] = today
            elif ea_nr == expire_settings.action_soon:
                # User is about to expire
                if uname in expiring_data:
                    if not expiring_data[uname]['mail1']:
                        logger.warn("%s: expire date reached, but first "
                                    "warning mail was not sent", uname)
                    if not expiring_data[uname]['mail2']:
                        logger.warn("%s: expire date reached, but second "
                                    "warning mail was not sent", uname)
                    if not expiring_data[uname]['mail3']:
                        if self.send_mail(uname, expiring_data[uname],
                                          email_templates.email_soon,
                                          forward=True):
                            expiring_data[uname]['mail3'] = today
                else:
                    logger.warn("User %s is about to expire, but no expiring "
                                "info exists. Create info and send mail.",
                                uname)
                    expiring_data[uname] = get_expiring_data(row, expire_date)
                    if self.send_mail(uname, expiring_data[uname],
                                      email_templates.email_soon,
                                      forward=True):
                        expiring_data[uname]['mail3'] = today
            else:
                # Error situation
                logger.error("Invalid expire_action=%r for user_data=%s",
                             ea_nr, repr(row))


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
                (user_info['expire_date'] > (
                    expire_settings.today -
                    expire_settings.delta_first_warning))):
            has_expired.append((uname, user_info['home']))
        # Find users that has been sent mail2 during the last SECOND_WARNING
        # days
        if (user_info['mail2'] and
                (user_info['mail2'] > (
                    expire_settings.today -
                    expire_settings.delta_second_warning))):
            got_mail2.append((uname, user_info['home']))
        # Find users that will expire the next 5 days
        if (user_info['expire_date'] <= (expire_settings.today +
                                         datetime.timedelta(days=5))):
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
be generated and users might get duplicate notifications.

--generate-info generates a html report on users that:

- should have been notified, and has expired recently
- should have gotten a second notification
- will soon expire
""".strip()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Send expire date notification emails",
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
    commit_group = parser.add_argument_group(
        'Commiting',
        'Unless --commit is provided, script will run in dryrun mode. '
        'In this mode, no emails will be sent.')
    add_commit_args(commit_group)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get('Database')()

    expire_util = UserExpireUtil(db, not args.commit)

    cache = load_cache(args.cache_file)
    expire_util.check_users(cache)
    dump_cache(cache, args.cache_file)

    if args.report_file:
        logger.info("Generating report")
        write_report(cache, args.report_file)
        logger.info("Report written to %r", args.report_file)

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
