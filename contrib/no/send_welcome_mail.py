#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 University of Oslo, Norway
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
Send a welcome e-mail to each new employee.

This script processes the changelog for account creation events.  For each
created account, it checks whether the owner (person) has a person-affiliation
of the specified type.  If so, a welcome e-mail is prepared from a template
file and sent to the account's primary e-mail address.

The script uses the CLHandler to track which changelog events have been
processed, so it can be run repeatedly without sending duplicate mails.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import functools
import logging
import textwrap
from datetime import timedelta

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.date
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
from Cerebrum.utils import argutils, date_compat
from Cerebrum.utils.email import mail_template

logger = logging.getLogger(__name__)

DEFAULT_CHANGE_KEY = 'send_welcome_mail'
DEFAULT_SENDER = 'noreply@uio.no'
DEFAULT_TOO_OLD_DAYS = 14
DEFAULT_TOO_FRESH_DAYS = 3


def has_affiliation(pe, person_id, affiliation):
    """
    Check if person has a matching person-affiliation.

    :param pe: Person database object
    :param int person_id: The person entity id
    :param affiliation: A PersonAffiliation or PersonAffStatus constant

    :returns bool: True if a matching affiliation exists
    """
    for row in pe.list_affiliations(person_id=person_id):
        if int(affiliation) in (row['affiliation'], row['status']):
            return True
    return False


def get_account(ac, co, account_id):
    """
    Find account by given id and populate `ac` object.
    """
    ac.clear()
    try:
        ac.find(account_id)
    except Errors.NotFoundError:
        logger.warning("Account entity_id=%s not found, skipping",
                       account_id)
        return False

    if ac.owner_type != co.entity_person:
        logger.debug("Account %s is not personal, skipping",
                     ac.account_name)
        return False
    return True


def get_primary_email(ac):
    """
    Get primary e-mail address for an account.

    :param ac: A populated Account object
    :returns str: The primary e-mail address, or None if not found
    """
    try:
        return ac.get_primary_mailaddress()
    except Errors.NotFoundError:
        return None


def process_account_creation(db, change_key, template_file, sender,
                             affiliation, too_old_days, too_fresh_days,
                             commit=False):
    """
    Process account creation events and send welcome mails.

    Goes through the changelog using CLHandler to find unprocessed
    account_create events.  For each event, checks if the account owner
    has a person-affiliation of the given type.  If so, prepares and sends
    a welcome mail from the given template.

    :param db: Database connection
    :param str change_key: CLHandler key for tracking processed events
    :param str template_file: Path to the e-mail template file
    :param str sender: Sender e-mail address
    :param affiliation: A PersonAffiliation or PersonAffStatus constant
    :param int too_old_days: Skip events older than this many days
    :param int too_fresh_days: Delay events younger than this many days
    :param bool commit: If True, actually send e-mails and commit changes
    """
    co = Factory.get('Constants')(db)
    clconst = Factory.get('CLConstants')(db)
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    cl = CLHandler.CLHandler(db)
    change_types = (clconst.account_create,)

    events = cl.get_events(change_key, change_types)
    logger.info("Found %d unprocessed account_create events", len(events))

    now = Cerebrum.utils.date.now()
    too_old = now - timedelta(days=too_old_days)
    too_fresh = now - timedelta(days=too_fresh_days)

    stats = {'seen': 0, 'sent': 0, 'skipped': 0, 'delayed': 0, 'failed': 0}
    for evt in events:
        stats['seen'] += 1
        account_id = evt['subject_entity']

        tstamp = date_compat.get_datetime_tz(evt['tstamp'])
        if tstamp and tstamp < too_old:
            logger.debug("Skipping too old change_id=%s (tstamp=%s)",
                         evt['change_id'], tstamp)
            cl.confirm_event(evt)
            stats['skipped'] += 1
            continue

        if tstamp and tstamp > too_fresh:
            logger.debug("Skipping too fresh change_id=%s (tstamp=%s)",
                         evt['change_id'], tstamp)
            stats['delayed'] += 1
            continue

        if not get_account(ac, co, account_id):
            logger.debug("Ignore account, change_id=%s (tstamp=%s)",
                         evt['change_id'], tstamp)
            cl.confirm_event(evt)
            stats['skipped'] += 1
            continue

        person_id = ac.owner_id
        if not has_affiliation(pe, person_id, affiliation):
            logger.debug(
                "Account %s owner (person_id=%s) has no %s affiliation, "
                "skipping",
                ac.account_name, person_id, affiliation)
            cl.confirm_event(evt)
            stats['skipped'] += 1
            continue

        email_addr = get_primary_email(ac)
        if not email_addr:
            logger.warning(
                "No primary e-mail for account %s, skipping",
                ac.account_name)
            cl.confirm_event(evt)
            stats['skipped'] += 1
            continue

        logger.info("Send welcome mail to %s (%s)", ac.account_name,
                    email_addr)

        try:
            result = mail_template(
                email_addr,
                template_file,
                sender=sender,
                debug=not commit,
                substitute={
                    'USERNAME': ac.account_name,
                },
            )
            if commit:
                logger.info("Mail sent to %s", ac.account_name)
            else:
                logger.debug("Dryrun, but would send mail:\n%s", result)
        except Exception:
            logger.error("Failed to send welcome mail to %s",
                         email_addr, exc_info=True)
            stats['failed'] += 1
            continue

        cl.confirm_event(evt)
        stats['sent'] += 1
        logger.info("Welcome mail prepared for %s", ac.account_name)

    if commit:
        cl.commit_confirmations()
        logger.info("Committed changelog confirmations")
    else:
        logger.info("Dry run, not committing changelog confirmations")

    logger.info(
        "Done: seen=%d, sent=%d, skipped=%d, delayed=%d, failed=%d",
        stats['seen'], stats['sent'], stats['skipped'], stats['delayed'],
        stats['failed'])


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Send welcome e-mail to new employees.

            Processes the changelog for account creation events and sends
            a welcome e-mail to accounts whose owner (person) has a
            person-affiliation of the specified type.
            """
        ).lstrip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    aff_arg = parser.add_argument(
        '--affiliation',
        required=True,
        metavar='AFF',
        help=textwrap.dedent(
            """
            Person affiliation type required for sending the welcome mail.
            Can be an affiliation (e.g. ANSATT, STUDENT) or an affiliation
            status (e.g. ANSATT/tekadm).  Persons without an affiliation
            of this type are skipped.
            Example: --affiliation ANSATT
            """
        ).lstrip(),
    )
    parser.add_argument(
        '--template',
        required=True,
        metavar='FILE',
        help=textwrap.dedent(
            """
            Path to the e-mail template file.  Can be an absolute path, or
            a path relative to cereconf.TEMPLATE_DIR.  The template may
            contain ${USERNAME} and ${RECIPIENT} substitution variables.
            """
        ).lstrip(),
    )
    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help="Actually send e-mails and commit changelog changes.",
    )
    parser.add_argument(
        '--change-key',
        default=DEFAULT_CHANGE_KEY,
        metavar='KEY',
        help="CLHandler key for tracking processed events. "
             "Default: %(default)s",
    )
    parser.add_argument(
        '--sender',
        default=DEFAULT_SENDER,
        metavar='ADDR',
        help="The From address. Default: %(default)s",
    )
    parser.add_argument(
        '--too-old',
        type=int,
        default=DEFAULT_TOO_OLD_DAYS,
        metavar='DAYS',
        help="Skip events older than this many days. Default: %(default)s",
    )
    parser.add_argument(
        '--too-fresh',
        type=int,
        default=DEFAULT_TOO_FRESH_DAYS,
        metavar='DAYS',
        help="Delay events younger than this many days. Default: %(default)s",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    co = Factory.get('Constants')(db)

    check_constant = functools.partial(argutils.get_constant, db, parser)
    affiliation = check_constant(
        (co.PersonAffiliation, co.PersonAffStatus),
        args.affiliation,
        aff_arg,
    )
    logger.debug("affiliation: %r", affiliation)

    process_account_creation(
        db=db,
        change_key=args.change_key,
        template_file=args.template,
        sender=args.sender,
        affiliation=affiliation,
        too_old_days=args.too_old,
        too_fresh_days=args.too_fresh,
        commit=args.commit,
    )

    if not args.commit:
        db.rollback()

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
