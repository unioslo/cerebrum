#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2012 University of Oslo, Norway
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
"""Script for sending out a new SMS to those who already have retrieved a
welcome SMS, but have not changed their password yet. The purpose of this is to
make sure that most of the users do change their password before a certain day.

The script does:

- Go through all the active users with the given check-trait.
- Users that are inactive or in quarantine are ignored.
- Users that has already changed their password the last year gets ignored.
- Users that has already gotten the set-trait the last given number of days are
  ignored.
- Each user then gets an SMS with a given message, and gets the set-trait.

TODO: This was requested by ØFK, but it should be generic enough to be used by
other instances too.

"""

import cereconf

import sys
import os
import getopt
from mx.DateTime import now

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.sms import SMSSender
from Cerebrum.QuarantineHandler import QuarantineHandler

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
db.cl_init(change_program='SMS-reminder')
co = Factory.get('Constants')(db)
sms = SMSSender(logger=logger)

commit = False

def usage(exitcode = 0):
    print """Usage: %(file)s --check-trait TRAIT --set-trait TRAIT [--days DAYS]

    %(doc)s

    --check-trait TRAIT     The trait which is checked for. Only users with the
                            given trait will be processed and targeted for a new
                            SMS. Example: trait_sms_welcome.

    --set-trait TRAIT       The trait to set when we have sent out the new SMS.
                            TODO: Could we instead add a number to the
                            check-trait's numval, or would that be confusing?
                            Example: trait_sms_reminder.

    --phone-types SOURCE:TYPE The phone types and source systems that could be
                            searched for phone numbers. Could be a comma
                            separated list - number are searched for in the same
                            order. Example: 

                                FS:MOBILE,EKSTENS:PRIVATEMOBILE

    --only-aff AFFIILATIONS If set, only persons with the given person
                            affiliations will be processed.

    --messageconf CONF      The name of a cereconf variable that contains the
                            message to send. The variable must be a string, and
                            could contain %%(username)s. Default: SMS_REMINDER_MSG.

    --days DAYS             How many days back the script should go and find
                            users with the proper traits. Users that has traits
                            older than this number of days gets ignored.
                            Default: 180.

    -h --help               Show this and quit.

    """ % {'file': os.path.basename(sys.argv[0]),
           'doc': __doc__}
    sys.exit(exitcode)

def process(check_trait, set_trait, days, phone_types, message, only_aff):
    logger.info("SMS-reminder started")
    if commit:
        logger.info("In commit, will send out SMS")
    else:
        logger.info("In dryrun, will not send SMS")

    limit_date = now() - days
    logger.debug('Matching only traits newer than: %s', limit_date)

    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    target_traits = set(t['entity_id'] for t in ac.list_traits(code=check_trait)
                        if (t['date'] >= limit_date and # Filter out old traits.
                            t['date'] < (now() - 1)))   # Filter out traits from
                                                        # the last 24 hours.
    logger.debug('Found %d traits of type %s from last %d days to check',
                 len(target_traits), check_trait, days)
    set_traits = set(t['entity_id'] for t in ac.list_traits(code=set_trait)
                     if t['date'] >= limit_date)
    logger.debug('Found %d already set traits of type %s from last %d days',
                 len(set_traits), set_trait, days)
    target_traits.difference_update(set_traits)
    logger.debug('Then %d traits of type %s remains to be checked',
                 len(target_traits), check_trait)

    pe_affs = set()
    if only_aff:
        for a in only_aff:
            pe_affs.update(r['person_id'] for r in
                           pe.list_affiliations(affiliation=a))
        logger.debug('Found %d person affiliations to filter by', len(pe_affs))
    else:
        logger.debug('No only_aff specified, so no filtering on affiliation')

    processed = 0

    for account_id in target_traits:
        ac.clear()
        try:
            ac.find(account_id)
        except Errors.NotFoundError:
            logger.error("Could not find user with entity_id: %s, skipping",
                         account_id)
            continue

        if ac.is_expired():
            logger.info("Account %s is expired, skipping", ac.account_name)
            continue
        if QuarantineHandler.check_entity_quarantines(
                db, ac.entity_id).is_locked():
            logger.info("Account %s is quarantined, skipping", ac.account_name)
            continue
        if pe_affs and ac.owner_id not in pe_affs:
            logger.info('Account %s without given person affiliation, skipping',
                        ac.account_name)
            continue

        # Check password changes for the user
        if have_changed_password(ac):
            logger.info("Account %s already changed password, skipping",
                        ac.account_name)
            continue

        # Everything ready, should send the SMS
        if send_sms(ac, pe, phone_types, message=message):
            ac.populate_trait(code=set_trait, date=now())
            ac.write_db()
            if commit:
                db.commit()
            else:
                db.rollback()
            logger.debug("Trait set for %s", ac.account_name)
            processed += 1
        else:
            logger.warn('Failed to send SMS to %s', ac.account_name)

    logger.info("SMS-reminder done, %d accounts processed" % processed)

def have_changed_password(ac):
    for event in db.get_log_events(types=co.account_password,
                                   subject_entity=ac.entity_id,
                                   return_last_only=True):
        # If the user has change it himself, we know for sure:
        if event['change_by'] == ac.entity_id:
            return True
        # If the user has used the forgotten-password-service
        if event['change_program'] == 'individuation_service':
            return True
        # If process_entity or process_students have set the password, we know
        # that the user does not know the password, as it's not sent out anymore
        # when we use the SMS service instead of password letters.
        if event['change_program'] in ('proc_ent', 'process_students'):
            return False
        # If the latest password change is older than a year ago, and the user
        # has not changed it, we considered as not changed.
        # TODO: is this correct?
        if event['tstamp'] < now() - 365:
            return False

        # TODO: other things to check?
        logger.warn("Unknown passw-event for %s: %s", ac.account_name, event)
    return False

def send_sms(ac, pe, phone_types, message):
    """Send out the SMS-reminders."""
    pe.clear()
    try:
        pe.find(ac.owner_id)
    except Errors.NotFoundError:
        logger.error('Could not find person of account %s', ac.account_name)
        return False

    phone_number = None
    for source, type in phone_types:
        info = pe.get_contact_info(source, type)
        if info:
            phone_number = info[0]['contact_value']
            break
    if not phone_number:
        logger.warn('Could not find phone number for %s, skipping',
                    ac.account_name)
        return False
    msg = message % {'username': ac.account_name}
    logger.info("Sending SMS for %s to %s: %s", ac.account_name, phone_number,
                msg)
    if not commit:
        logger.debug('Dryrun, SMS not sent')
        # assumes gets sent okay
        return True
    return sms(phone_number, msg)

if __name__ == '__main__':
    try:
        opts, vals = getopt.getopt(sys.argv[1:], 'h',
                          ['help',
                           'commit',
                           'days=',
                           'messageconf=',
                           'only-aff=',
                           'check-trait=',
                           'phone-types=',
                           'set-trait='])
    except getopt.GetOptError, e:
        print e
        usage(1)

    days = 180
    check_trait = set_trait = message = None
    phone_types = []
    only_aff = []

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt == '--days':
            days = int(val)
        elif opt == '--messageconf':
            message = getattr(cereconf, val)
        elif opt == '--commit':
            commit = True
        elif opt == '--check-trait':
            check_trait = getattr(co, val)
        elif opt == '--only-aff':
            only_aff.extend(int(co.PersonAffiliation(a))
                            for a in val.split(','))
        elif opt == '--set-trait':
            set_trait = getattr(co, val)
        elif opt == '--phone-types':
            for v in val.split(','):
                t = v.split(':', 1)
                source = co.human2constant(t[0], co.AuthoritativeSystem)
                if not source:
                    raise Exception('Unknown source system: %s' % t[0])
                type = co.human2constant(t[1], co.ContactInfo)
                if not type:
                    raise Exception('Unknown phone type: %s' % t[1])
                phone_types.append((source, type))
        else:
            print "Unknown option: %s" % opt
            usage(1)

    if not check_trait:
        print "Need to specify the trait to check for."
        usage(1)
    if not set_trait:
        print "Need to specify the trait to set."
        usage(1)
    if not phone_types:
        print "Need to specify the phone types to use."
        usage(1)
    if not message:
        message = cereconf.SMS_REMINDER_MSG

    process(days=days, set_trait=set_trait, check_trait=check_trait,
            phone_types=phone_types, message=message, only_aff=only_aff)
