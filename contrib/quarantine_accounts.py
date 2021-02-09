#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2017 University of Oslo, Norway
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
""" Quarantine accounts without person affiliations.

The accounts are warned, by e-mail, unless they are reserved, i.e. are not
registered with any spread.

NOTE! The script will delete and re-set quarantines that are temporarily
disabled! Only quarantines of the type supplied to the -q flag are checked
and set.

The script should be extended to do the following:
    - Send an SMS to account owners.

The flow of the script is something like this:
    1. Parse args and initialise globals in the main-function. This is
        also where the rest of the action is sparked.
    2. Call the find_candidates-function to collect all person IDs that are
        affiliated and are not affiliated.
    3. Call the set_quarantine-function. This sets a given quarantine on
        all accounts associated with the persons collected in step 2 if
        the notify_user-function successfully sends an email to the user.
    4. Optionally call the remove_quarantine-function, in order to remove
        quarantines set on persons who are affiliated.

"""

from __future__ import unicode_literals
from __future__ import print_function

import sys
import getopt
import smtplib
import email
import io
import datetime

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.utils.date import now
from Cerebrum.utils.email import sendmail

logger = Factory.get_logger('cronjob')


def usage(exitcode=0):
    print(__doc__)
    print("""Usage: %s

-q QUARANTINE   The quarantine to set (default 'auto_no_aff')

-i              (--ignore-quarantines) Do not consider other quarantines than
                the one specified. This will practically set the quarantine
                even if the person is already quarantined by other
                quarantine(s)

-r              Remove quarantines for those that have previously gotten the
                given quarantine, but have now gotten an affiliation. This is
                to automatically clean up those previously quarantined.

-o OFFSET       Quarantine offset in days. Default: 7.
                If a quarantine of the same type exists, and is longer away in
                the future than the offset defines, it will be removed and a
                new quarantine will be set

-a AFFILIATIONS Affiliations that should be ignored when checking, so that they
                will also be quarantined. This is typical affiliations like
                'MANUELL/inaktiv'. A person that has only affiliations from
                this list, will be considered as not affiliated, since they got
                ignored. This might be a bit confusing - do not put in proper
                affiliations here, like 'STUDENT'. The list should be comma
                separated.

--grace DAYS    The number of days to still consider a person affiliation as
                valid after it has been removed. This is to support glitches in
                the systems, where persons are temporarily removed due to known
                or unknown flaws in the registrations.

-m TEMPLATEFILE Specify the file containing the full template of the message to
                be sent, including headers. The file must be parseable by the
                python module email's "message_from_file(FILE)".

                Note: If no templatefile is given, the users will not be given
                e-mails.

-e              Print out the content of all e-mails that is sent out, to
                stdout. Note: To avoid sending out e-mails, use --dryrun.

-d --dryrun     Dryrun mode. Quarantines will not be set, and e-mails will not
                be sent to the users.

-h --help       Show this and quit.

    """ % sys.argv[0])
    sys.exit(exitcode)


def send_mail(mail_to, mail_from, subject, body, mail_cc=None):
    """Function for sending mail to users.

    Will respect dryrun, as that is given and handled by
    Cerebrum.utils.email.sendmail, which is then not sending the e-mail.

    @type mail_to: string
    @param mail_to: The recipient of the Email.

    @type mail_from: string
    @param mail_from: The senders address.

    @type subject: string
    @param subject: The messages subject.

    @type body: string
    @param body: The message body.

    @type mail_cc: string
    @param mail_cc: An optional address that the mail will be CCed to.

    @rtype: bool
    @return: A boolean that tells if the email was sent sucessfully or not.
    """
    try:
        ret = sendmail(mail_to, mail_from, subject, body,
                       cc=mail_cc, debug=dryrun)
        if debug_verbose:
            print("---- Mail: ---- \n" + ret)
    except smtplib.SMTPRecipientsRefused as e:
        failed_recipients = e.recipients
        logger.info("Failed to notify <%d> users", len(failed_recipients))
        for _, condition in failed_recipients.iteritems():
            logger.info("Failed to notify: %s", condition)
    except smtplib.SMTPException as msg:
        logger.warn("Error sending to %s: %s" % (mail_to, msg))
        return False
    return True


def notify_user(ac, quar_start_in_days):
    """Send a mail to the given user about the quarantine.

    :param Cerebrum._Account ac: The initiated Account object to notify

    :param dict email_info: A dictionary containing the Email-message to send.

    :param int quar_start_in_days:
        The number of days until the quarantine will be enforced.

    :rtype: bool
    :return: If the notification were successfully sent or not.

    """
    addr = None

    try:
        # By default we use the primary email address
        addr = ac.get_primary_mailaddress()
    except Errors.NotFoundError:
        pass

    if addr is None:
        # Look for forward addresses in entity_contact_info for the account
        try:
            addr = ac.list_contact_info(
                entity_id=ac.entity_id,
                contact_type=co.contact_email)[0]['contact_value']
            logger.debug(
                "Found email address for account:%s in entity contact info" %
                ac.account_name)
        except IndexError:
            pass

    if addr is None:
        # Look for forward addresses in entity_contact_info for the owner
        try:
            addr = ac.list_contact_info(
                entity_id=ac.owner_id,
                contact_type=co.contact_email)[0]['contact_value']
            logger.debug(
                "Found email address for account:%s "
                "in entity contact info for person:%i" % (
                    ac.account_name, ac.owner_id))
        except IndexError:
            pass

    if addr is None:
        logger.warn("No email address for account:%s, can't notify",
                    ac.account_name)
        return False

    body = email_info['Body']
    body = body.replace('${USERNAME}', ac.account_name)
    body = body.replace('${DAYS_TO_START}', str(quar_start_in_days))
    body = body.replace(
        '${QUARANTINE_DATE}',
        # (datetime.date.now() + quar_start_in_days).Format("%F"))
        (now() + quar_start_in_days).Format("%F"))

    try:
        first_name = (pe.search_person_names(
            person_id=ac.owner_id,
            name_variant=co.name_first,
            source_system=co.system_cached)[0])['name']
    except IndexError:
        first_name = ""

    body = body.replace('${FIRST_NAME}', first_name)

    subject = email_info['Subject'].replace('${USERNAME}', ac.account_name)

    return send_mail(addr, email_info['From'], subject, body, email_info['Cc'])


def find_candidates(exclude_aff=[], grace=0, quarantine=None):
    """Find persons who should be quarantined and dequarantined.

    :param list exclude_aff:
        A list of affiliations/statuses that should be ignored when finding the
        candidates. Persons with only affiliations from this list will be
        considered as not affiliated.

        The list contains tuples, either with affiliation or affiliation- and
        status-codes.

    :param int grace:
        Defines a grace period for when affiliations are still considered
        active, after their end period.

    :param None/QuarantineCode/sequence(QuarantineCode) quarantine:
        If not None, will filter the `quarantined` return value only to have
        these quarantines.

    :rtype: dict
    :return:
        Three elements are included in the dict:

        - `affiliated`: A set with person-IDs for those considered affiliatied.
        - `not_affiliated`: A set with person-IDs for those *not* affiliatied.
        - `quarantined`: A set with account-IDs for all quarantined accounts.

    """
    datelimit = now() + datetime.timedelta(days=int(grace))
    logger.debug2("Including affiliations deleted after: %s", datelimit)

    def is_aff_considered(row):
        """Check for if an affiliation should be considered or not."""
        # Exclude affiliations deleted before the datelimit:
        if row['deleted_date'] and row['deleted_date'] < datelimit:
            return False
        if (row['affiliation'], row['status']) in exclude_aff:
            return False
        if (row['affiliation'],) in exclude_aff:
            return False
        return True

    affs = filter(is_aff_considered,
                  pe.list_affiliations(include_deleted=True))
    affed = set(x['person_id'] for x in affs)
    logger.debug('Found %d persons with affiliations', len(affed))
    naffed = set(x['person_id'] for x in pe.list_persons()) - affed
    logger.debug('Found %d persons without affiliations', len(naffed))

    if quarantine is None:
        quarantined = QuarantineHandler.get_locked_entities(
            db, entity_types=co.entity_account)
    else:
        quarantined = set(x['entity_id'] for x in ac.list_entity_quarantines(
            entity_types=co.entity_account,
            only_active=True,
            quarantine_types=quarantine))
    logger.debug('Found %d quarantined accounts', len(quarantined))
    return {'affiliated': affed, 'not_affiliated': naffed,
            'quarantined': quarantined}


def set_quarantine(pids, quar, offset, quarantined):
    """Quarantine the given persons' accounts.

    :param list pids: Person IDs that will be evaluated for quarantine.

    :param _QuarantineCode quar:
        The quarantine that will be set on accounts referenced in `pids`.

    :param int offset: The number of days until the quarantine starts.

    :param set quarantined:
        Account IDs for those already in any active quarantine. Any account in
        here will neither be warned nor quarantined.

    :rtype: set
    :return: The account IDs for those that were quarantined in this round.

    """
    ac.clear()
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    creator = ac.entity_id

    success = set()
    failed_notify = 0
    no_processed = 0
    date = now() + datetime.timedelta(days=int(offset))


    # Cache what entities has the target quarantine:
    with_target_quar = set(
        r['entity_id'] for r in
        ac.list_entity_quarantines(quarantine_types=quar,
                                   only_active=False,
                                   entity_types=co.entity_account)
        if r['start_date'] <= date)
    logger.debug2('Accounts with target quarantine: %d', len(with_target_quar))
    # Cache the owner to account relationship:
    pid2acs = {}
    for row in ac.search(owner_type=co.entity_person):
        pid2acs.setdefault(row['owner_id'], []).append(row)
    logger.debug2('Mapped %d persons to accounts', len(pid2acs))

    for pid in pids:
        for row in pid2acs.get(pid, ()):
            if (row['account_id'] in quarantined) or (
                    row['account_id'] in success):
                continue
            no_processed += 1

            if row['account_id'] in with_target_quar:
                logger.debug2('Already got the quarantine: %s', row['name'])
                continue

            ac.clear()
            ac.find(row['account_id'])

            # We will not send any warning if
            # - In dryrun mode
            # - No mail template is set
            # - The account is reserved, i.e. has no spreads.
            #   This is in effect, at least for the user,
            #   about the same as being in quarantine.
            if ac.is_reserved() or not email_info or dryrun:
                notified = True
            else:
                notified = notify_user(ac, offset)

            if notified:
                ac.delete_entity_quarantine(quar)
                ac.add_entity_quarantine(quar, creator, start=date)
                # Commiting here to avoid that users get multiple emails if the
                # script is stopped before it's done.
                ac.commit()
                logger.info('Added %s quarantine for: %s', quar,
                            ac.account_name)
                success.add(ac.entity_id)
            else:
                failed_notify += 1
    logger.debug('Accounts processed: %d', no_processed)
    logger.debug('Quarantines added: %d', len(success))
    logger.debug('Accounts failed: %d', failed_notify)
    return success


def remove_quarantine(pids, quar):
    """Assert that the given quarantine is removed from the given persons.

    :param list pids:
        A list of person IDs that will have the quarantine removed from all
        their accounts.

    :param _QuarantineCode quar:
        The quarantine that will be removed from accounts referenced in `pids`.

    :rtype: list
    :return:
        The entity name of all the accounts that had a quarantine which got
        removed.

    """
    dequarantined = []

    # Cache the owner to account relationship:
    pid2acs = {}
    for row in ac.search(owner_type=co.entity_person):
        pid2acs.setdefault(row['owner_id'], []).append(row)

    with_quar = set(r['entity_id'] for r in
                    ac.list_entity_quarantines(quarantine_types=quar,
                                               only_active=False,
                                               entity_types=co.entity_account))

    for pid in pids:
        for row in pid2acs.get(pid, ()):
            if row['account_id'] not in with_quar:
                continue
            logger.info('Deleting quarantine from: %s', row['name'])
            ac.clear()
            ac.find(row['account_id'])
            ac.delete_entity_quarantine(quar)
            ac.write_db()
            dequarantined.append(row['name'])
    logger.debug('Quarantines removed in total: %d', len(dequarantined))
    return dequarantined


def parse_affs(affs):
    """
    Function for parsing affiliations

    @type affs: string
    @param affs: A string of affiliations, separated by commas

    @rtype: list
    @return: Returns a list of tuples with affiliation- or affiliation- and
        status-codes.
    """
    parsed = []
    for x in affs.split(','):
        aff = x.split('/', 1)
        try:
            if len(aff) > 1:
                aff = co.PersonAffStatus(aff[0], aff[1])
                parsed.append((int(aff.affiliation), int(aff),))
            else:
                aff = co.PersonAffiliation(x)
                parsed.append((int(aff),))
        except Errors.NotFoundError:
            raise Exception("Unknown affiliation: %s" % x)
    return parsed


if __name__ == '__main__':
    db = Factory.get('Database')()
    db.cl_init(change_program='quarantine_accounts')
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)

    quarantine = None
    ignore_quarantines = False
    quarantine_offset = 7
    dryrun = debug_verbose = False
    email_info = None
    remove = False
    ignore_aff = []
    grace = 0

    try:
        opts, j = getopt.getopt(sys.argv[1:], 'q:rdo:m:eha:i',
                                ['dryrun',
                                 'grace=',
                                 'help',
                                 'ignore-quarantines'])
    except getopt.GetoptError as e:
        print(e)
        usage(1)

    for opt, val in opts:
        if opt in ('-q',):
            try:
                quarantine = co.Quarantine(val.decode('UTF-8'))
                int(quarantine)
            except Errors.NotFoundError:
                raise Exception("Invalid quarantine: %s" % val)
        elif opt in ('-i', '--ignore-quarantines'):
            ignore_quarantines = True
        elif opt in ('-r',):
            remove = True
        elif opt in ('-d', '--dryrun'):
            db.commit = db.rollback
            dryrun = True
            logger.info("In dryrun mode, will rollback and not send e-mail")
        elif opt in ('-e',):
            debug_verbose = True
        elif opt in ('-o',):
            try:
                quarantine_offset = int(val)
            except ValueError:
                logger.error('\'%s\' is not an integer' % val)
                sys.exit(4)
        elif opt in ('-a',):
            ignore_aff = parse_affs(val.decode('UTF-8'))
        elif opt in ('-m',):
            try:
                with io.open(val, 'r', encoding='UTF-8') as f:
                    msg = email.message_from_file(f)
                email_info = {
                    'Subject': email.Header.decode_header(
                        msg['Subject'])[0][0],
                    'From': msg['From'],
                    'Cc': msg['Cc'],
                    'Body': msg.get_payload(decode=1)
                }
            except IOError as e:
                print('Mail body file: %s' % e)
                sys.exit(2)
        elif opt in ('--grace',):
            grace = int(val)
        elif opt in ('-h', '--help'):
            usage()
        else:
            print("Invalid argument: %s" % val)
            usage(1)

    if not email_info:
        print("Missing -m TEMPLATEFILE")
        usage(1)
    if not quarantine:
        quarantine = co.quarantine_auto_no_aff

    logger.info("Process started")
    logger.debug('Finding candidates for addition/removal of quarantine...')
    cands = find_candidates(ignore_aff,
                            grace,
                            quarantine if ignore_quarantines else None)
    logger.debug('Setting/removing quarantine on accounts')
    set_quarantine(cands['not_affiliated'], quarantine, quarantine_offset,
                   quarantined=cands['quarantined'])

    if remove:
        remove_quarantine(cands['affiliated'], quarantine)

    if dryrun:
        logger.info('This is a dryrun, rolling back DB')
    db.commit()
    logger.info("Process finished")
