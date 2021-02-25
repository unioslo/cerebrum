#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
A script for sending notification on the automatic creation of new users.

This script finds accounts that have a given trait, and sends a notification
to the users it-organization.
"""
import argparse
import functools
import logging
from datetime import datetime

import six

from smtplib import SMTPException

from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils, date_compat
from Cerebrum.utils.email import mail_template


logger = logging.getLogger(__name__)

def compare_dates(database_date, now):
    if datebase_date is None:
        return false
    else:
        database_date = date_compat.get_datetime_naive(database_date)
        return database_date > now

class AccountsWithTraitManager(object):

    def __init__(self, db, trait):
        self.db = db
        self.trait = trait
        self.ac = Factory.get('Account')(self.db)

    def __iter__(self):
        """
        The iterator for the WelcomeManager only checks if the account has the
        trait.

        The reason for this is that we want to include everyone with the
        trait, and remove it when we do send an SMS, or give up on it.
        """
        for row in self.ac.list_traits(code=self.trait):
            yield row


def get_ou_contact_emails(ou, co):
    """Get the contact email(s) of an ou, if any.

    :param ou: A populated OU object
    :param co: Constants
    """
    contact_emails = ou.local_it_contact(co.perspective_sap)
    contact_emails = [a['contact_value'] for a in contact_emails]
    return contact_emails


class AccountCreationNotifier(object):

    def __init__(self, db, trait, too_old, affiliations=None, commit=False):
        self.db = db
        self.co = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.trait = trait
        self.commit = commit
        self.too_old = too_old
        self.affiliations = affiliations
        self.manager = AccountsWithTraitManager(self.db, trait)

    def find_ou(self, ou_id):
        """Attempt to do self.ou.find(ou_id)"""
        self.ou.clear()
        try:
            self.ou.find(ou_id)
        except Errors.NotFoundError:
            logger.error(
                'Unknown OU. Something is probably wrong, ou_id %s',
                ou_id)
            return False
        return True

    def notify(self):
        """Notify lkit on the creation of new accounts"""
        logger.info('send_new_account_notification_mail start')

        ou_notify = self.get_ous_and_users_to_notify()

        # Combine all accounts per contact address to minimize the number of
        # emails sent.
        email_content = {}
        for ou_id, users in six.iteritems(ou_notify):

            if not self.find_ou(ou_id):
                continue

            contact_emails = get_ou_contact_emails(self.ou, self.co)
            stedkode = self.ou.get_stedkode()

            logger.info('Found users %s with trait, on ou %s', users, stedkode)

            if not contact_emails:
                logger.info('No contact email for ou %s, skipping', stedkode)
                continue

            for addr in contact_emails:
                if addr not in email_content:
                    email_content[addr] = {}

                if stedkode in email_content[addr]:
                    email_content[addr][stedkode].extend(users)
                else:
                    email_content[addr][stedkode] = users

        notified_users = []
        for addr, ous in six.iteritems(email_content):
            msg = []
            users_in_mail = []
            for ou, users in six.iteritems(ous):
                msg.append('Nye brukere ved stedkode {}:'.format(ou))
                msg.append('\n'.join(users))
                msg.append('')
                users_in_mail.extend(users)

            logger.info('Sending mail to %s about %d new users',
                        addr, len(users_in_mail))
            try:
                result = mail_template(
                    addr,
                    'no_NO/email/rapport_automatisk_brukeroppretting.txt',
                    sender='noreply@uio.no',
                    debug=not self.commit,
                    substitute={
                        'USERS': '\n'.join(msg),
                        'CONTACT': addr
                    }
                )
                if not self.commit:
                    # Print the mail in dry run mode
                    logger.debug(result)
            except SMTPException as e:
                logger.error(
                    'Could not send email to address %s. Error: %s', addr, e)
            else:
                notified_users.extend(users_in_mail)

        # Remove the trait from notified users
        ac = Factory.get('Account')(self.db)
        notified_users = list(set(notified_users))
        for user in notified_users:
            ac.find_by_name(user)
            self.remove_trait(ac)
            ac.clear()
        logger.info('Notification on %d new users sent!', len(notified_users))
        logger.info('send_new_account_notification_mail done')

    def remove_trait(self, ac):
        """Remove the notify trait from an account."""
        logger.debug("Remove trait %s from account %s", self.trait,
                     ac.account_name)
        ac.delete_trait(code=self.trait)
        ac.write_db()

        if self.commit:
            self.db.commit()
            logger.debug('Remove trait: Changes written to db')
        else:
            self.db.rollback()
            logger.debug('Remove trait: Changes rolled back')

    def get_ous_and_users_to_notify(self):
        """
        Find new automatically create users.

        The users are returned as a dict with the corresponding OU as key.
        If a use has affiliations from multiple OUs, we notify all.
        """
        ac = Factory.get('Account')(self.db)
        pe = Factory.get('Person')(self.db)

        ou_notify = {}

        for row in self.manager:
            ac.clear()
            ac.find(row['entity_id'])

            if (self.too_old and
                compare_dates(row['date'], (datetime.now() - self.too_old))):

                # Trait is to old, remove it
                logger.warn('Too old trait %s for entity_id=%s, giving up',
                            text_type(self.manager.trait), row['entity_id'])
                self.remove_trait(ac)
                continue

            # Do not notify non-personal accounts
            if ac.owner_type != self.co.entity_person:
                logger.info('Tagged new user %r not personal, skipping',
                            ac.account_name)
                # User is not personal, remove the trait
                self.remove_trait(ac)
                continue

            if ac.is_expired():
                # User is expired, remove the trait
                logger.info('New user %r is expired, skipping',
                            ac.account_name)
                self.remove_trait(ac)
                continue

            ou_ids = []
            for a in pe.list_affiliations(person_id=ac.owner_id):
                affs = [a['affiliation'], a['status']]
                if (self.affiliations and
                        not any(a in affs for a in self.affiliations)):
                    # Skip affiliation if not specified.
                    logger.info(
                        'Skipping affiliation %s for person %s',
                        a,
                        ac.owner_id)
                    continue
                ou_ids.append(a['ou_id'])
            pe.clear()

            if len(ou_ids) == 0:
                # No affiliation found, skipping.
                logger.info('No required person affiliation for %r, skipping',
                            ac.account_name)
                continue

            for ou_id in ou_ids:
                if ou_id in ou_notify:
                    ou_notify[ou_id].append(ac.account_name)
                else:
                    ou_notify[ou_id] = [ac.account_name]

        return ou_notify


DEFAULT_TRAIT = 'trait_new_account_notification_pending'
DEFAULT_TOO_OLD = 30


def main(inargs=None):
    doc = __doc__.strip().splitlines()

    parser = argparse.ArgumentParser(
        description=doc[0],
        epilog='\n'.join(doc[1:]),
        formatter_class=argparse.RawTextHelpFormatter)

    trait_arg = parser.add_argument(
        '--trait',
        default=DEFAULT_TRAIT,
        metavar='TRAIT',
        help='The trait that defines new accounts,\n'
        'default: %(default)s')

    aff_arg = parser.add_argument(
        '--affiliations',
        action='append',
        default=[],
        help='A comma separated list of affiliations. If set, the person\n'
        'must have at least one affiliation of these types')

    parser.add_argument(
        '--too-old',
        type=argutils.IntegerType(minval=0),
        default=DEFAULT_TOO_OLD,
        metavar='DAYS',
        help='How many days the given trait can exist before we give up.\n'
        'Default: %(default)s days.')

    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help="Actually send out the SMSs and update traits.")

    parser.set_defaults(filters=[])
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    check_constant = functools.partial(argutils.get_constant, db, parser)

    trait = check_constant(co.EntityTrait, args.trait, trait_arg)

    affiliations = [
        check_constant((co.PersonAffiliation, co.PersonAffStatus), v, aff_arg)
        for v in ','.join(args.affiliations).split(',') if v]

    Cerebrum.logutils.autoconf('cronjob', args)
    db.cl_init(change_program='new_automatic_account_notification')

    logger.info('Start of script %s', parser.prog)
    logger.debug("trait:        %r", trait)
    logger.debug("affiliations: %r", affiliations)
    logger.debug("commit:       %r", args.commit)

    notifier = AccountCreationNotifier(
        db=db,
        trait=trait,
        too_old=args.too_old,
        affiliations=affiliations,
        commit=args.commit
    )

    notifier.notify()


if __name__ == '__main__':
    main()
