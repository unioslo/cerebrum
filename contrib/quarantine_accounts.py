#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2022 University of Oslo, Norway
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
Quarantine all account where the owner no longer has any affiliations.

The accounts are warned, by e-mail, unless they are reserved, i.e. are not
registered with any spread.

... important::
    The script will delete and re-set quarantines that are temporarily
    disabled!  Only the quarantine of the type supplied to the -q flag are
    checked and set.
"""
from __future__ import unicode_literals
from __future__ import print_function

import argparse
import datetime
import email
import io
import logging
import smtplib

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Constants import _PersonAffiliationCode, _PersonAffStatusCode
from Cerebrum.Utils import Factory
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.utils.date_compat import get_date
from Cerebrum.utils.email import sendmail

logger = logging.getLogger(__name__)

#
# Globals - these settings are updated by main(), but gets set here to somewhat
# safe values if this script is imported as a module
#

# debug_verbose - note: defaults to `False` in main()
debug_verbose = True

# dryrun - note: defaults to `False` in main()
dryrun = True


class EmailTemplate(object):
    """
    Email template for notifications.
    """
    def __init__(self, from_addr, subject, body, cc_addrs=None):
        self.from_addr = from_addr
        self.subject = subject
        self.body = body
        self.cc_addrs = cc_addrs

    @classmethod
    def from_file(cls, filename):
        with io.open(filename, 'r', encoding='utf-8') as f:
            msg = email.message_from_file(f)

        return cls(
            from_addr=msg['From'],
            subject=email.Header.decode_header(msg['Subject'])[0][0],
            body=msg.get_payload(decode=1),
            cc_addrs=msg['Cc'],
        )

    def format_subject(self, username):
        return self.subject.replace('${USERNAME}', username)

    def format_body(self, username, quarantine_offset, first_name):
        quarantine_date = (datetime.date.today()
                           + datetime.timedelta(days=int(quarantine_offset)))
        first_name = first_name or ""
        body = self.body
        body = body.replace('${USERNAME}', username)
        body = body.replace('${DAYS_TO_START}', str(quarantine_offset))
        body = body.replace('${QUARANTINE_DATE}', str(quarantine_date))
        body = body.replace('${FIRST_NAME}', first_name)
        return body


def send_mail(mail_to, mail_from, subject, body, mail_cc=None):
    """
    Function for sending mail to users.

    Will respect dryrun, as that is given and handled by
    Cerebrum.utils.email.sendmail, which is then not sending the e-mail.

    :param str mail_to: email address of the intended recipient
    :param str mail_from: email address of the sender (from-header)
    :param str subject: email subject header
    :param str body: email content/body
    :param str mail_cc: optional address for copy

    :returns bool:
        if the email was successfully sent

        - True: email was sent (or rejected by one or more recipiets)
        - False: email sending failed (e.g. smtp server unavailable)
    """
    try:
        ret = sendmail(mail_to, mail_from, subject, body,
                       cc=mail_cc, debug=dryrun)
        if debug_verbose:
            # TODO: how is this supposed to work?
            # sendmail only returns a message if email is disabled (dryrun or
            # cereconf.EMAIL_DISABLED) - but this function is only called if
            # dryrun=False.
            print("---- Mail: ---- \n" + ret)
    except smtplib.SMTPRecipientsRefused as e:
        failed_recipients = e.recipients
        logger.warning("failed to notify %d recipients",
                       len(failed_recipients))
        for _, condition in failed_recipients.items():
            logger.info("failed to notify: %s", condition)
    except smtplib.SMTPException as msg:
        logger.warning("error sending to %s: %s" % (mail_to, msg))
        return False
    return True


def get_notify_addr(ac):
    """
    Get notification email address for a given account.

    :param ac: An Account-object for a given user.

    :returns: An email address, or `None` if no address can be found.
    """
    addr = None
    co = ac.const

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
                "found email address for account %s in contact info",
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
                "found email address for account %s "
                "in contact info for owner (person_id=%d)",
                ac.account_name, ac.owner_id)
        except IndexError:
            pass

    return addr or None


def notify_user(template, ac, quarantine_offset):
    """
    Send an email to notify the quarantined user.

    :param template: EmailTemplate object to use for the notification
    :param ac: Account-object for the quarantined user
    :param int quarantine_offset: number of days until quarantine starts

    :returns bool: if the user was notified (see py:func:`.send_mail`)
    """
    co = ac.const

    addr_to = get_notify_addr(ac)
    if not addr_to:
        logger.warning("no email address for account %s, can't notify",
                       ac.account_name)
        # TODO: `False` when no email address exists, but `True` if
        # recipient refuses email (see send_mail)?
        return False

    try:
        pe = Factory.get("Person")(ac._db)
        first_name = pe.search_person_names(
            person_id=ac.owner_id,
            name_variant=co.name_first,
            source_system=co.system_cached,
        )[0]['name']
    except IndexError:
        first_name = ""

    subject = template.format_subject(ac.account_name)
    body = template.format_body(ac.account_name, quarantine_offset, first_name)
    addr_from = template.from_addr
    addr_cc = template.cc_addrs

    return send_mail(addr_to, addr_from, subject, body, addr_cc)


def find_candidates(db, invalid_affs, grace):
    """
    Find persons who should be quarantined and de-quarantined.

    :param list invalid_affs:
        A list of affiliations or affiliation status constants that should be
        ignored when finding the candidates.  Persons with only affiliations
        from this list will be considered as not affiliated.

        The list contains tuples, either with affiliation or affiliation- and
        status-codes.

    :param int grace:
        Defines a grace period for when affiliations are still considered
        active, after their end period.

    :returns tuple:
        A tuple of two sets: (affiliated_ids, not_affiliated_ids)
    """
    date_cutoff = datetime.date.today() - datetime.timedelta(days=int(grace))
    logger.info("including affiliations deleted after: %s", date_cutoff)

    # convert constants to set of (aff, status) or (aff,) int tuples for
    # easy filtering
    exclude_aff = set()
    for aff_const in invalid_affs:
        if isinstance(aff_const, _PersonAffiliationCode):
            exclude_aff.add((int(aff_const),))
        elif isinstance(aff_const, _PersonAffStatusCode):
            exclude_aff.add((int(aff_const.affiliation), int(aff_const)))
        else:
            raise ValueError("invalid affilition const: " + repr(aff_const))

    def is_aff_considered(row):
        """ Check if affiliation is valid """
        deleted_date = get_date(row['deleted_date'])

        # Exclude affiliations deleted before the datelimit:
        if deleted_date and deleted_date < date_cutoff:
            return False
        if (row['affiliation'], row['status']) in exclude_aff:
            return False
        if (row['affiliation'],) in exclude_aff:
            return False
        return True

    pe = Factory.get('Person')(db)

    affs = filter(is_aff_considered,
                  pe.list_affiliations(include_deleted=True))
    affiliated = set(x['person_id'] for x in affs)
    logger.info('affiliated: %d persons', len(affiliated))
    not_affiliated = (
        set(x['person_id'] for x in pe.list_persons())
        - affiliated)
    logger.info('not affiliated: %d persons', len(not_affiliated))

    return affiliated, not_affiliated


def find_quarantined_accounts(db, quarantines):
    """
    Get all quarantined accounts.

    This is used to decide if a given account needs to be quarantined if its
    owner is no longer affiliated.

    :param None/QuarantineCode/sequence(QuarantineCode) quarantine:
        If not None, will filter the `quarantined` return value only to have
        these quarantines.

    :rtype: set
    :returns:
        A set of all accounts that are considered quarantined
    """
    co = Factory.get('Constants')(db)

    if quarantines is None:
        quarantined = set(
            QuarantineHandler.get_locked_entities(
                db, entity_types=co.entity_account))
    else:
        ac = Factory.get('Account')(db)
        quarantined = set(
            x['entity_id']
            for x in ac.list_entity_quarantines(
                entity_types=co.entity_account,
                only_active=True,
                quarantine_types=quarantines))
    logger.info('already quarantined: %d accounts', len(quarantined))
    return quarantined


def set_quarantine(db, template, pids, quar, offset, quarantined):
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
    ac = Factory.get('Account')(db)
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    creator = ac.entity_id

    co = Factory.get('Constants')(db)

    success = set()
    failed_notify = 0
    no_processed = 0
    q_start = datetime.date.today() + datetime.timedelta(days=int(offset))

    # Cache what entities has the target quarantine:
    with_target_quar = set(
        r['entity_id']
        for r in ac.list_entity_quarantines(
            quarantine_types=quar,
            only_active=False,
            entity_types=co.entity_account)
        if r['start_date'] and get_date(r['start_date']) <= q_start)
    logger.debug("found %d accounts with active target quarantine",
                 len(with_target_quar))
    # Cache the owner to account relationship:
    pid2acs = {}
    for row in ac.search(owner_type=co.entity_person):
        pid2acs.setdefault(row['owner_id'], []).append(row)
    logger.debug("found %d persons with accounts", len(pid2acs))

    for pid in pids:
        for row in pid2acs.get(pid, ()):
            if (row['account_id'] in quarantined
                    or row['account_id'] in success):
                continue
            no_processed += 1

            if row['account_id'] in with_target_quar:
                logger.debug("already quarantined: %s (%d)",
                             row['name'], row['account_id'])
                continue

            ac.clear()
            ac.find(row['account_id'])

            # We will not send any warning if
            # - In dryrun mode
            # - The account is reserved, i.e. has no spreads.
            #   This is in effect, at least for the user,
            #   about the same as being in quarantine.
            if ac.is_reserved() or dryrun:
                notified = True
            else:
                notified = notify_user(template, ac, offset)

            if notified:
                ac.delete_entity_quarantine(quar)
                ac.add_entity_quarantine(quar, creator, start=str(q_start))
                # Commiting here to avoid that users get multiple emails if the
                # script is stopped before it's done.
                # Note that db.commit = db.rollback in dryrun mode
                ac.commit()
                logger.info("added %s quarantine for: %s (%d)",
                            quar, ac.account_name, ac.entity_id)
                success.add(ac.entity_id)
            else:
                # TODO: shouldn't we do an explicit rollback here to mirror the
                # commit in the other branch?
                failed_notify += 1

    logger.info("accounts processed: %d", no_processed)
    logger.info("quarantines added: %d", len(success))
    logger.info("accounts failed: %d", failed_notify)
    return success


def remove_quarantine(db, pids, quar):
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

    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)

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
            logger.info("removing %s quarantine from: %s (%d)",
                        quar, row['name'], row['account_id'])
            ac.clear()
            ac.find(row['account_id'])
            ac.delete_entity_quarantine(quar)
            ac.write_db()
            dequarantined.append(row['name'])
    logger.info('quarantines removed: %d', len(dequarantined))
    return dequarantined


def parse_affs(const, affs):
    """
    Function for parsing affiliations.

    :param str affs:
        a comma-separated string of affiliations

    :rtype: generator
    :returns:
        generates an aff or aff-status constant for each affiliation
    """
    for aff_hint in affs.split(','):
        aff, status = const.get_affiliation(aff_hint)
        if status is None:
            yield aff
        else:
            yield status


def get_email_template(filename):
    """
    Email template for notifications.

    :param filename: email template file to read

    :rtype: dict
    :returns:
        a dict with:

        Subject: email Subject template for notifications
        From: email From address for notifications
        Cc: email Cc addresses for notifications
        Body: email Body template for notifications
    """
    with io.open(filename, 'r', encoding='utf-8') as f:
        msg = email.message_from_file(f)

    return {
        'Subject': email.Header.decode_header(msg['Subject'])[0][0],
        'From': msg['From'],
        'Cc': msg['Cc'],
        'Body': msg.get_payload(decode=1)
    }


description = """
Set a quarantine on all accounts owned by *un-affiliated* persons.
""".strip()

epilog = """
Affiliations and grace
----------------------
An *un-affiliated* person is any person that has no *valid affiliations*.

By default all active affiliations are valid, but certain affiliations can be
ignored, e.g.: `-a MANUELL` or `-a MANUELL/inaktiv`.  Multiple affiliations can
be ignored by repeating the option.  Note that *proper* affiliations like
`ANSATT` or `STUDENT` should never be ignored.

It's usually a good idea to add a *grace-period*, which considers deleted
affiliations as active/valid for a few extra days.  E.g. `--grace 3` to avoid
quarantine/notification email to users that has lost their last *valid*
affiliation in the last 3 days, usually due to de-sync between source systems.

Quarantines and offset
----------------------
The quarantine start date can be delayed, to provide the user with basic access
to files and email for some time after getting notified.  E.g. `-o 30` to delay
quarantine start for 30 days.

If an account already has the given quarantine, but with a start date further
away in the future than the offset defines, it will be removed and a new
quarantine with the correct offset will be re-added.

By default, the given quarantine will not be added to accounts that are
quarantined by some other means.  To force the given quarantine for
un-affiliated users, use `--ignore-quarantines`.

To remove the given quarantine for users that have been *re-affiliated*,
use the `-r` flag.

Template
--------
An email template for notifying quarantined users *must* be provided using the
`-m` option.  The template file is a raw email text (including headers) with
placeholders for certain values:

- ${USERNAME} (subject, body) - name of the quarantined account
- ${DAYS_TO_START} (body) - number of days until quarantine starts
- ${QUARANTINE_DATE} (body) - date of quarantine start
- ${FIRST_NAME} (body) - first name of the account owner

Note that only the `From`, `Cc`, and `Subject` headers are read from the
template.

The template is parsed using `email.message_from_file()` in the standard
library.

Debugging
---------
To disable email and database changes, use the `--dryrun` flag.  Email can also
be disabled in ``cereconf`` (see py:mod:`Cerebrum.utils.email`).

To inspect e-mails, use the `-e` flag.  Note that this does *not* enable
dryrun.
""".lstrip()


def main(inargs=None):
    global dryrun, debug_verbose

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    aff_args = parser.add_argument_group('affiliation settings')
    aff_args.add_argument(
        "-a", "--ignore-affiliation",
        action="append",
        dest="invalid_affs",
        help=(
            "Do not consider %(metavar)s as a valid affiliation. "
            "Can be repeated."
        ),
        metavar="<aff>",
    )
    aff_args.add_argument(
        "--grace",
        default=0,
        dest="grace",
        type=int,
        help=(
            "Consider deleted affiliations as valid for %(metavar)s days "
            "(default %(default)s)"
        ),
        metavar="<n>",
    )

    q_args = parser.add_argument_group('quarantine settings')
    q_args.add_argument(
        "-q", "--quarantine",
        default="auto_no_aff",
        dest="quarantine",
        help="The quarantine to set (default '%(default)s')",
        metavar="<quarantine>",
    )
    q_args.add_argument(
        "-i", "--ignore-quarantines",
        action="store_true",
        default=False,
        dest="force_quarantine",
        help="Set the quarantine even if other quarantines exists",
    )
    q_args.add_argument(
        "-r", "--remove-quarantine",
        action="store_true",
        default=False,
        dest="remove_quarantine",
        help="Remove the quarantine if person has been re-affiliated",
    )
    q_args.add_argument(
        "-o", "--offset",
        default=7,
        dest="offset_quarantine",
        type=int,
        help=(
            "Offset start date for the quarantine by %(metavar)s days "
            "(default %(default)s)"
        ),
        metavar="<n>",
    )

    email_args = parser.add_argument_group('email settings')
    email_args.add_argument(
        "-m", "--template",
        dest="notify_template_file",
        required=True,
        help="Notify quarantined users using the template in %(metavar)s",
        metavar="<file>",
    )
    email_args.add_argument(
        "-e", "--print-emails",
        action="store_true",
        dest="print_emails",
        default=False,
        help="Verbose output - Prints all e-mails that is sent out to stdout",
    )

    parser.add_argument(
        "-d", "--dryrun",
        action="store_true",
        dest="dryrun",
        default=False,
        help="Dryrun - quarantines will not be set, emails will not be sent",
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='quarantine_accounts')
    co = Factory.get('Constants')(db)

    quarantine = co.get_constant(co.Quarantine, args.quarantine)
    force_q = args.force_quarantine
    remove_q = args.remove_quarantine
    offset_q = args.offset_quarantine

    invalid_affs = []
    for raw_affs in (args.invalid_affs or ()):
        # - arg (-a) can be given multiple times,
        # - each arg may also be a comma-separated list of affs
        invalid_affs.extend(parse_affs(co, raw_affs))

    grace = args.grace
    template = EmailTemplate.from_file(args.notify_template_file)
    dryrun = args.dryrun
    if dryrun:
        db.commit = db.rollback
    debug_verbose = args.print_emails

    logger.info("start %s", parser.prog)
    logger.info('quarantine: %s (offset=%d, force=%r, remove=%r)',
                quarantine, offset_q, force_q, remove_q)
    logger.info('affiliation: ignore=%s, grace=%d',
                [six.text_type(a) for a in invalid_affs], grace)
    logger.info('template: %s', args.notify_template_file)
    logger.info('dryrun: %s', repr(dryrun))

    logger.info("caching affiliated/unaffiliated persons...")
    affiliated, not_affiliated = find_candidates(db, invalid_affs, grace)

    logger.info("caching quarantined accounts...")
    quarantined = find_quarantined_accounts(
        db, quarantine if force_q else None)

    logger.info("setting quarantines...")
    set_quarantine(db,
                   template=template,
                   pids=not_affiliated,
                   quar=quarantine,
                   offset=offset_q,
                   quarantined=quarantined)

    if remove_q:
        logger.info('clearing quarantines...')
        remove_quarantine(db, affiliated, quarantine)

    if dryrun:
        logger.info('rolling back changes (dryrun)...')
        db.rollback()
    else:
        logger.info('commiting changes...')
        db.commit()

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
