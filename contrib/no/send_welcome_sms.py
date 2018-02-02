#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2016 University of Oslo, Norway
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
"""A script for sending out SMS to new users. Originally created for sending
out usernames to student accounts created by process_students.py, but it could
hopefully be used by other user groups if necessary."""

import sys
import os
import getopt

from mx.DateTime import now, DateTimeDelta

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.sms import SMSSender

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
db.cl_init(change_program='send_welcome_sms')
co = Factory.get('Constants')(db)
sms = SMSSender(logger=logger)


def usage(exitcode=0):
    print """Usage: %(scriptname)s [--commit] [options...]

    This script finds accounts that has the given trait and sends out a welcome
    SMS to them with their username. The 'sms_welcome' trait is set on SMS'ed
    accounts to avoid sending them duplicate SMSs.

    Note that we will not send out an SMS to the same account twice in a period
    of 180 days. We don't want to spam the users.

    --trait TRAIT   The trait that defines new accounts. Default:
                    trait_student_new

    --phone-types   The phone types and source systems to get phone numbers
                    from. Can be a comma separated list, and its format is:

                        <source sys name>:<contact type>,...

                    E.g. FS:MOBILE,FS:PRIVATEMOBILE,SAP:MOBILE

                    Source systems: FS, SAP
                    Contact types: MOBILE, PRIVATEMOBILE

                    Default: FS:MOBILE

    --affiliations  A comma separated list of affiliations. If set, the person
                    must have at least one affiliation of these types.

    --skip-if-password-set Do not send SMS if the account has had a password
                    set after the account recieved the trait defined by
                    --trait. Also remove the trait defined by --trait.

    --message-cereconf If the message is located in cereconf, this is its
                    variable name. Default: AUTOADMIN_WELCOME_SMS

    --message       The message to send to the users. Should not be given if
                    --message-cereconf is specified.

    --too-old DAYS  How many days the given trait can exist before we give up
                    trying to send the welcome SMS. This is for the cases where
                    the phone number e.g. is incorrect, or the person hasn't a
                    phone number. After a while it will be too late to try
                    sending the SMS. When the given number of days has passed,
                    the trait will be deleted, and a warning will be logged.
                    Default: 180 days.

    --min-attempts ATTEMPTS
                    The minimum number of attempts per account. If this option
                    is set, the trait will be removed if these two conditions
                    apply:
                        1) the trait is too old
                    and 2) number of attempts > minimum number of attempts

    --commit        Actual send out the SMSs and update traits.

    --help          Show this and quit
    """ % {'scriptname': os.path.basename(sys.argv[0])}
    sys.exit(exitcode)


def process(trait, message, phone_types, affiliations, too_old, min_attempts,
            commit=False, filters=[]):
    """Go through the given trait type and send out welcome SMSs to the users.
    Remove the traits, and set a new message-is-sent-trait, to avoid spamming
    the users."""
    logger.info('send_welcome_sms started')
    if not commit:
        logger.debug('In dryrun mode')

    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    for row in ac.list_traits(code=trait):
        ac.clear()
        ac.find(row['entity_id'])
        logger.debug('Found user %s', ac.account_name)

        # increase attempt counter for this account
        if min_attempts:
            attempt = inc_attempt(ac, row, commit)

        is_too_old = (row['date'] < (now() - too_old))

        # remove trait if older than too_old days and min_attempts is not set
        if is_too_old and not min_attempts:
            logger.warn('Too old trait %s for entity_id=%s, giving up',
                        trait, row['entity_id'])
            remove_trait(ac, trait, commit)
            continue

        # remove trait if more than min_attempts attempts have been made and
        # trait is too old
        if (min_attempts and is_too_old and min_attempts < attempt):
            logger.warn(
                'Too old trait and too many attempts (%s) for '
                'entity_id=%s, giving up',
                attempt, row['entity_id'])
            remove_trait(ac, trait, commit)
            continue

        if ac.owner_type != co.entity_person:
            logger.warn('Tagged new user %s not personal, skipping',
                        ac.account_name)
            # TODO: remove trait?
            continue
        if ac.is_expired():
            logger.debug('New user %s is expired, skipping', ac.account_name)
            # TODO: remove trait?
            continue

        # Apply custom filters that deem if this user should be processed
        # further.
        def apply_filters(filter_name, filter_func):
            if isinstance(filter_func, list):
                result = all(map(lambda fun: fun(ac, row), filter_func))
            else:
                result = filter_func(ac, row)

            if result:
                remove_trait(ac, trait, commit)
                logger.info(
                    'New user filtered out by {} function, '
                    'removing trait {}'.format(filter_name, row))
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
                logger.debug('No required person affiliation for %s, skipping',
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
            logger.debug('User %s already texted last %d days, removing trait',
                         ac.account_name, 180)
            remove_trait(ac, trait, commit)
            continue

        # get phone number
        phone = get_phone_number(pe=pe, phone_types=phone_types)
        if not phone:
            logger.debug('Person %s had no phone number, skipping for now',
                         ac.account_name)
            continue

        # get email
        email = ''
        try:
            if hasattr(ac, 'get_primary_mailaddress'):
                email = ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            pass

        msg = message % {'username': ac.account_name,
                         'email': email}
        if not send_sms(phone, msg, commit):
            logger.warn('Could not send SMS to %s (%s)',
                        ac.account_name,
                        phone)
            continue

        # sms sent, now update the traits
        ac.delete_trait(trait)
        ac.populate_trait(code=co.trait_sms_welcome, date=now())
        ac.write_db()
        if commit:
            db.commit()
        else:
            db.rollback()
        logger.debug('Traits updated for %s', ac.account_name)
    if not commit:
        logger.debug('Changes rolled back')
    logger.info('send_welcome_sms done')


def remove_trait(ac, trait, commit=False):
    """Remove a given trait from an account."""
    logger.debug("Deleting trait %s from account %s", trait, ac.account_name)
    ac.delete_trait(code=trait)
    ac.write_db()
    if commit:
        db.commit()
    else:
        db.rollback()


def inc_attempt(ac, row, commit=False):
    """Increase the attempt counter (stored in trait) for a given account."""
    attempt = row['numval']
    if not attempt:
        attempt = 1
    else:
        attempt = int(attempt) + 1
    logger.debug("Attempt number %s for account %s", attempt, ac.account_name)
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
    logger.debug('Sending SMS to %s: %s', phone, message)
    if not commit:
        logger.debug('Dryrun mode, SMS not sent')
        return True
    return sms(phone, message)


def skip_if_password_set(ac, trait):
    """ Has the password been changed after the trait was set? """
    # The trait and initial password is set in the same transaction. We add
    # a minute to skip this initial password change event.
    try:
        after = trait['date'] + DateTimeDelta(0, 0, 1)  # delta = 1 minute
    except:
        after = ac.created_at + DateTimeDelta(0, 0, 1)
    return True if [x for x in db.get_log_events(
        subject_entity=ac.entity_id,
        sdate=after,
        types=co.account_password)] else False


def main():
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'h',
            ['trait=', 'phone-types=', 'affiliations=', 'message=',
             'too-old=', 'message-cereconf=', 'commit', 'min-attempts=',
             'skip-if-password-set'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    affiliations = []
    phone_types = []
    message = trait = None
    commit = False
    too_old = 180
    min_attempts = None
    filters = []

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt == '--trait':
            trait = getattr(co, arg)
        elif opt == '--too-old':
            too_old = int(arg)
            assert 0 < too_old, "--too_old must be a positive integer"
        elif opt == '--min-attempts':
            min_attempts = int(arg)
            assert 0 < min_attempts, ("--min-attempts must be a positive "
                                      "integer")
        elif opt == '--phone-types':
            phone_types.extend(
                (co.human2constant(t[0], co.AuthoritativeSystem),
                 co.human2constant(t[1], co.ContactInfo))
                for t in (a.split(':') for a in arg.split(',')))
        elif opt == '--affiliations':
            affiliations.extend(co.human2constant(a, (co.PersonAffiliation,
                                                      co.PersonAffStatus))
                                for a in arg.split(','))
        elif opt == '--skip-if-password-set':
            filters.append(('skip-if-password-set', skip_if_password_set))
        elif opt == '--message':
            if message:
                print 'Message already set'
                usage(1)
            message = arg
        elif opt == '--message-cereconf':
            if message:
                print 'Message already set'
                usage(1)
            message = arg
        elif opt == '--commit':
            commit = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    # DEFAULTS
    if not message:
        message = cereconf.AUTOADMIN_WELCOME_SMS
    if not phone_types:
        phone_types = [(co.system_fs, co.contact_mobile_phone,)]
    if not trait:
        trait = co.trait_student_new

    process(trait=trait,
            message=message,
            phone_types=phone_types,
            affiliations=affiliations,
            too_old=too_old,
            min_attempts=min_attempts,
            commit=commit,
            filters=filters)

if __name__ == '__main__':
    main()
