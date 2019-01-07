#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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
""" A script for sending out SMS to new users.

This script finds accounts that has the given trait and sends out a welcome
SMS to them with their username. The 'sms_welcome' trait is set on SMS'ed
accounts to avoid sending them duplicate SMSs.

Note that we will not send out an SMS to the same account twice in a period
of 180 days. We don't want to spam the users.

Originally created for sending out usernames to student accounts created by
process_students.py, but it could hopefully be used by other user groups if
necessary.
"""
import argparse
import functools
import logging

from mx.DateTime import now, DateTimeDelta
from six import text_type

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.sms import SMSSender
from Cerebrum.utils import argutils


logger = logging.getLogger(__name__)
sms = SMSSender(logger=logger)


class SMSManager(object):
    def __init__(self, db, trait):
        self.db = db
        self.trait = trait
        self.ac = Factory.get('Account')(self.db)


class ReminderManager(SMSManager):
    # def __init__(self, db, trait):
    #     super(ReminderManager, self).__init__(db, trait)

    def __iter__(self):
        for row in self.ac.list_traits(code=self.trait, numval=1):
            yield row

    def remove_trait(self, ac, commit=False):
        """In reminder mode we skip all trait removal operations."""
        logger.debug("In reminder mode, keeping trait %s on account %s",
                     self.trait, ac.account_name)
        pass


class WelcomeManager(SMSManager):
    # def __init__(self, db, trait):
    #     super(WelcomeManager, self).__init__(db, trait)

    def __iter__(self):
        for row in self.ac.list_traits(code=self.trait, numval=None):
            yield row

    def remove_trait(self, ac, commit=False):
        """Remove a given trait from an account."""
        logger.debug("Deleting trait %s from account %s", self.trait,
                     ac.account_name)
        ac.delete_trait(code=self.trait)
        ac.write_db()
        if commit:
            self.db.commit()
        else:
            self.db.rollback()


def process(manager, message, phone_types, affiliations, too_old,
            min_attempts, commit=False, filters=[]):
    """Go through the given trait type and send out welcome SMSs to the users.

    Remove the traits, and set a new message-is-sent-trait, to avoid spamming
    the users.
    """
    logger.info('send_welcome_sms started')
    if not commit:
        logger.debug('In dryrun mode')

    co = Factory.get('Constants')(manager.db)
    ac = Factory.get('Account')(manager.db)
    pe = Factory.get('Person')(manager.db)

    for row in manager:
        ac.clear()
        ac.find(row['entity_id'])
        logger.debug('Found user %s', ac.account_name)

        # increase attempt counter for this account
        if min_attempts:
            attempt = inc_attempt(manager.db, ac, row, commit)

        is_too_old = (row['date'] < (now() - too_old))

        # remove trait if older than too_old days and min_attempts is not set
        if is_too_old and not min_attempts:
            logger.warn('Too old trait %s for entity_id=%s, giving up',
                        text_type(manager.trait), row['entity_id'])
            manager.remove_trait(ac, commit)
            continue

        # remove trait if more than min_attempts attempts have been made and
        # trait is too old
        if min_attempts and is_too_old and min_attempts < attempt:
            logger.warn(
                'Too old trait and too many attempts (%r) for '
                'entity_id=%r, giving up',
                attempt, row['entity_id'])
            manager.remove_trait(ac, commit)
            continue

        if ac.owner_type != co.entity_person:
            logger.info('Tagged new user %r not personal, skipping',
                        ac.account_name)
            # TODO: remove trait?
            continue
        if ac.is_expired():
            logger.debug('New user %r is expired, skipping', ac.account_name)
            # TODO: remove trait?
            continue

        if list(ac.get_entity_quarantine(only_active=True,
                                         filter_disable_until=False)):
            # Skipping sms until all quarantines are removed.
            logger.warn('Tagged new user %r with quarantine, skipping',
                        ac.account_name)
            continue

        # Apply custom filters that deem if this user should be processed
        # further.
        def apply_filters(filter_name, filter_func):
            if isinstance(filter_func, list):
                result = all(map(lambda fun: fun(manager.db, ac, row), filter_func))
            else:
                result = filter_func(manager.db, ac, row)

            if result:
                manager.remove_trait(ac, commit)
                logger.info(
                    'New user filtered out by %r function, '
                    'removing trait %r', filter_name, row)
                return True
            return False

        if any(map(lambda (k, v): apply_filters(k, v), filters)):
            continue

        # check person affiliations
        if affiliations:
            affs = []
            for a in pe.list_affiliations(person_id=ac.owner_id):
                affs.append(a['affiliation'])
                affs.append(a['status'])
            if not any(a in affs for a in affiliations):
                logger.debug('No required person affiliation for %r, skipping',
                             ac.account_name)
                # TODO: Doesn't remove trait, in case the person gets it later
                # on.
                #       Should the trait be removed?
                continue
        pe.clear()
        pe.find(ac.owner_id)

        # Check if user already has been texted. If so, the trait is removed.
        tr = ac.get_trait(co.trait_sms_welcome)
        if tr and tr['date'] > (now() - 300):
            logger.debug('User %r already texted last %d days, removing trait',
                         ac.account_name, 180)
            manager.remove_trait(ac, commit)
            continue

        # get phone number
        phone = get_phone_number(pe=pe, phone_types=phone_types)
        if not phone:
            logger.debug('User %r had no phone number, skipping for now',
                         ac.account_name)
            continue

        # get email
        email = ''
        try:
            if hasattr(ac, 'get_primary_mailaddress'):
                email = ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            pass

        # get student number
        studentnumber = None
        try:
            studentnumber = pe.get_external_id(
                co.system_fs,
                co.externalid_studentnr)[0]['external_id']
        except (IndexError, AttributeError):
            pass

        def u(db_value):
            if isinstance(db_value, bytes):
                return db_value.decode(manager.db.encoding)
            return text_type(db_value)

        msg = message % {
            'username': u(ac.account_name),
            'studentnumber': u(studentnumber),
            'email': u(email),
        }
        if not send_sms(phone, msg, commit):
            logger.warn('Could not send SMS to %r (%r)',
                        ac.account_name,
                        phone)
            continue

        # sms sent, now update the traits
        manager.remove_trait(ac, commit)
        ac.populate_trait(code=co.trait_sms_welcome, date=now())
        ac.write_db()
        if commit:
            manager.db.commit()
        else:
            manager.db.rollback()
        logger.debug('Traits updated for %r', ac.account_name)
    if not commit:
        logger.debug('Changes rolled back')
    logger.info('send_welcome_sms done')


def inc_attempt(db, ac, row, commit=False):
    """Increase the attempt counter (stored in trait) for a given account."""
    attempt = row['numval']
    if not attempt:
        attempt = 1
    else:
        attempt = int(attempt) + 1
    logger.debug("Attempt number %r for account %r", attempt, ac.account_name)
    ac.populate_trait(code=row['code'], numval=attempt, date=row['date'])
    ac.write_db()
    if commit:
        db.commit()
    else:
        db.rollback()
    return attempt


def get_phone_number(pe, phone_types):
    """Search through a person's contact info and return the first found info
    value as defined by the given types and source systems."""
    for source_system, contact_type in phone_types:
        for row in pe.get_contact_info(source=source_system,
                                       type=contact_type):
            return row['contact_value']


def send_sms(phone, message, commit=False):
    """Send an SMS to a given phone number"""
    logger.debug('Sending SMS to %r: %r', phone, message)
    if not commit:
        logger.debug('Dryrun mode, SMS not sent')
        return True
    return sms(phone, message)


def skip_if_password_set(db, ac, trait):
    """ Has the password been changed after the trait was set? """
    clconst = Factory.get('CLConstants')(db)
    # The trait and initial password is set in the same transaction. We add
    # a minute to skip this initial password change event.
    try:
        after = trait['date'] + DateTimeDelta(0, 0, 1)  # delta = 1 minute
    except:
        after = ac.created_at + DateTimeDelta(0, 0, 1)
    return True if [x for x in db.get_log_events(
        subject_entity=ac.entity_id,
        sdate=after,
        types=clconst.account_password)] else False


def lalign(s):
    lines = s.split('\n')
    striplen = min(len(l) - len(l.lstrip())
                   for l in lines
                   if len(l.lstrip()))
    return '\n'.join(l[striplen:] for l in lines)


def try_decode(value):
    # TODO: Temporary fix, args.message should *always* be unicode from
    # cereconf!
    if isinstance(value, bytes):
        tmp = value
        for encoding in ('utf-8', 'latin-1'):
            try:
                value = tmp.decode(encoding)
                break
            except UnicodeError:
                continue
        else:
            raise ValueError("Unable to decode cereconf-value")
    return text_type(value)


DEFAULT_TRAIT = 'trait_student_new'
DEFAULT_PHONES = ['FS:MOBILE']
DEFAULT_MESSAGE_ATTR = 'AUTOADMIN_WELCOME_SMS'
DEFAULT_TOO_OLD = 180


def main(inargs=None):
    doc = __doc__.strip().splitlines()

    parser = argparse.ArgumentParser(
        description=doc[0],
        epilog='\n'.join(doc[1:]),
        formatter_class=argparse.RawTextHelpFormatter)

    # TODO: send_welcome_sms *really* needs a config
    trait_arg = parser.add_argument(
        '--trait',
        default=DEFAULT_TRAIT,
        metavar='TRAIT',
        help='The trait that defines new accounts,\n'
             'default: %(default)s')

    phone_arg = parser.add_argument(
        '--phone-types',
        action='append',
        default=[],
        help=lalign(
            """
            The phone types and source systems to get phone numbers
            from. Can be a comma separated list, and its format is:

                <source sys name>:<contact type>,...

            E.g. FS:MOBILE,FS:PRIVATEMOBILE,SAP:MOBILE

            Source systems: FS, SAP
            Contact types: MOBILE, PRIVATEMOBILE

            Default: {0}
            """).strip().format(','.join(DEFAULT_PHONES)))

    aff_arg = parser.add_argument(
        '--affiliations',
        action='append',
        default=[],
        help=lalign(
            """
            A comma separated list of affiliations. If set, the person
            must have at least one affiliation of these types.
            """).strip())

    parser.add_argument(
        '--skip-if-password-set',
        dest='filters',
        action='append_const',
        const=('skip-if-password-set', skip_if_password_set),
        help=lalign(
            """
            Do not send SMS if the account has had a password
            set after the account recieved the trait defined by
            --trait. Also remove the trait defined by --trait.
            """).strip())

    msg_group = parser.add_mutually_exclusive_group()
    msg_group.add_argument(
        '--message-cereconf',
        dest='message',
        type=argutils.attr_type(cereconf, try_decode),
        default=DEFAULT_MESSAGE_ATTR,
        metavar='ATTR',
        help=lalign(
            """
            If the message is located in cereconf, this is its
            variable name. Default: %(default)s
            """).strip())

    msg_group.add_argument(
        '--message',
        dest='message',
        type=argutils.UnicodeType(),
        help=lalign(
            """
            The message to send to the users. Should not be given if
            --message-cereconf is specified.
            """).strip())

    parser.add_argument(
        '--too-old',
        type=argutils.IntegerType(minval=0),
        default=DEFAULT_TOO_OLD,
        metavar='DAYS',
        help=lalign(
            """
            How many days the given trait can exist before we give up
            trying to send the welcome SMS. This is for the cases where
            the phone number e.g. is incorrect, or the person hasn't a
            phone number. After a while it will be too late to try
            sending the SMS. When the given number of days has passed,
            the trait will be deleted, and a warning will be logged.
            Default: %(default)s days.
            """).strip())

    parser.add_argument(
        '--min-attempts',
        type=argutils.IntegerType(minval=0),
        default=None,
        metavar='ATTEMPTS',
        help=lalign(
            """
            The minimum number of attempts per account. If this option
            is set, the trait will be removed if these two conditions
            apply:
                1) the trait is too old
            and 2) number of attempts > minimum number of attempts
            """).strip())

    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help="Actually send out the SMSs and update traits.")

    parser.add_argument(
        '--reminder',
        action='store_true',
        default=False,
        help="Send reminder to users who have not set their password even "
             "though they have gotten an sms before.")

    parser.set_defaults(filters=[])
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    check_constant = functools.partial(argutils.get_constant, db, parser)

    trait = check_constant(co.EntityTrait, args.trait, trait_arg)

    # so ','.join(list).split(',') is a little weird -- but the getopt
    # parsing allowed e.g. "--phone-types foo,bar --phone-types baz"
    phone_types = [
        (check_constant(co.AuthoritativeSystem, t[0], phone_arg),
         check_constant(co.ContactInfo, t[1], phone_arg))
        for t in (a.split(':')
                  for a in ','.join(args.phone_types or
                                    DEFAULT_PHONES).split(','))]
    affiliations = [
        check_constant((co.PersonAffiliation, co.PersonAffStatus), v, aff_arg)
        for v in ','.join(args.affiliations).split(',') if v]

    Cerebrum.logutils.autoconf('cronjob', args)
    db.cl_init(change_program='send_welcome_sms')

    logger.info('Start of script %s', parser.prog)
    logger.debug("trait:        %r", trait)
    logger.debug("phone-types:  %r", phone_types)
    logger.debug("affiliations: %r", affiliations)
    logger.debug("message:      %r", args.message)
    logger.debug("too-old:      %r", args.too_old)
    logger.debug("min-attempts: %r", args.min_attempts)
    logger.debug("commit:       %r", args.commit)
    logger.debug("filters:      %r", args.filters)

    if args.reminder:
        manager = ReminderManager(db, trait)
    else:
        manager = WelcomeManager(db, trait)

    process(
        manager=manager,
        message=args.message,
        phone_types=phone_types,
        affiliations=affiliations,
        too_old=args.too_old,
        min_attempts=args.min_attempts,
        commit=args.commit,
        filters=args.filters,
    )


if __name__ == '__main__':
    main()
