#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2023 University of Oslo, Norway
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
Notify accounts that are about to expire.

This script scans the accounts in WebID and looks for accounts that are about
to expire. Specifically, expire_notifier.py performs these tasks:

  * Collects accounts (VA/FA only) that have expire date close in the future.
  * Generates a number of requests to reset the expire date.
  * Creates an associated URL, where the token for the request is embedded.
  * E-mails the URL to all the users who should be warned (i.e. users who are
    about to expire and who have not been warned).

In order for this approach to work additional cooperation is required from:

  * reaper.py. That job is supposed to deactivate expired accounts. If the
    expire date is reached without the user reacting, the account is set as
    inactive.

  * bofhd/PHP-interface. The URL mentioned earlier leads to a page where users
    confirm the request and push the expiration date into the future.


cereconf
--------
``EXPIRE_WARN_WINDOW``
    When to generate and send expire email notifications.

    Notification will be sent if there are less than ``EXPIRE_WARN_WINDOW``
    days left until the account expires.

``EXPIRE_CONFIRM_URL``
    Base URL for the 'keepalive' link in the email notification.

    The actual link provided in the email is ``EXPIRE_CONFIRM_URL +
    confirmation_key``.

``EXPIRE_MESSAGE_SENDER``
    *From* field in email notifications.

``EXPIRE_MESSAGE_SUBJECT``
    *Subject* field in email notifications.

``EXPIRE_MESSAGE_TEMPLATE``
    Template for the email notification message body.  The template is rendered
    using old-style string formatting:

    ::

        EXPIRE_MESSAGE_TEMPLATE % {
            "uname": "example",
            "expire_date": "1998-06-28",
            "url": EXPIRE_CONFIRM_URL + "c945...",
        }

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)
import argparse
import datetime
import logging
import smtplib

import six

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import json
from Cerebrum.utils.date import now
from Cerebrum.utils.date_compat import get_date, get_timedelta
from Cerebrum.utils.email import sendmail

logger = logging.getLogger(__name__)


def get_config(name):
    """Fetch the appropriate variable from cereconf.

    This is a convenience hack -- we get a nice error message, without
    cluttering the code with error checks.
    """

    if not hasattr(cereconf, name):
        raise RuntimeError("Variable %s is not defined in cereconf" %
                           str(name))

    return getattr(cereconf, name)


class UserAttributes(object):
    """Placeholder for related attributes for a user.

    This is a convenience class. Rather than construct a dict of dicts, we'll
    work with dicts of objects of this class.
    """
    def __init__(self, account):
        self.uname = account.account_name
        self.email = account.get_email_address()
        self.account_id = account.entity_id
        self.magic_key = None
        self.expire_date = get_date(account.expire_date)

    def set_magic_key(self, magic):
        self.magic_key = magic


def collect_warnable_accounts(database):
    """Collect all FA/VA that are about to expire.

    Both VA and FA are collected as candidates.
    """

    account = Factory.get("Account")(database)
    const = Factory.get("Constants")()

    today = datetime.date.today()
    warn_np_types = (const.virtaccount_type, const.fedaccount_type)
    warn_min_delta = datetime.timedelta(0)
    warn_max_delta = get_timedelta(get_config("EXPIRE_WARN_WINDOW"),
                                   allow_none=False)

    for row in account.list(filter_expired=True):
        if row["np_type"] not in warn_np_types:
            # wrong account type - we only notify "regular" accounts
            continue
        expire_date = get_date(row["expire_date"])
        if not expire_date:
            continue
        days_until_expire = expire_date - today
        if days_until_expire < warn_min_delta:
            # already expired
            continue
        if days_until_expire > warn_max_delta:
            # too many days until expire
            continue
        yield row["account_id"]


def collect_warned_accounts(database, account_ids=None):
    """Collect FA/VA that have an outstanding expire warning.

    :type account_ids: an int or a sequence thereof
    :param account_ids:
      Specific accounts the expire warning status of which we want.
    """
    clconst = Factory.get("CLConstants")
    for event in database.get_log_events(types=clconst.va_reset_expire_date,
                                         subject_entity=account_ids):
        account_id = event["subject_entity"]
        if account_id is None:
            logger.error(
                "event %s (change_id=%s) has no subject_entity",
                str(clconst.va_reset_expire_date), event["change_id"])
            continue
        yield account_id


def account_id2attributes(account_id, database):
    """Remap account_id to account's attributes."""
    account = Factory.get("Account")(database)
    try:
        account.find(account_id)
        return UserAttributes(account)
    except Errors.NotFoundError:
        return None


def create_request(attrs, cl_event_type, db):
    """Generate a confirmation request for the given account_id.
    """

    if not attrs.email:
        logger.warn("Account %s (id=%s) is missing an e-mail. "
                    "No expiration warning will be sent.",
                    attrs.uname, attrs.account_id)
        return None

    magic_key = db.log_pending_change(attrs.account_id,
                                      cl_event_type,
                                      attrs.account_id,
                                      change_params={"date": now(),
                                                     "to": attrs.email})
    db.write_log()
    logger.info("Created %s request for account %s (id=%s)",
                str(cl_event_type), attrs.uname, attrs.account_id)

    attrs.set_magic_key(magic_key)
    return magic_key


def cancel_request(attrs, db):
    """Revert a specific L{create_request} call.

    This is useful if an action following a pending_change_log/change_log
    update (such as e-mail sending) fails.
    """

    magic_key = attrs.magic_key
    try:
        db.get_pending_event(magic_key)
        db.remove_pending_log_event(magic_key)
        logger.debug("Cancelled request for %s/%s (request key: %s)",
                     attrs.uname, attrs.email, magic_key)
    except Errors.NotFoundError:
        logger.debug("Request with request key %s has already been cancelled",
                     magic_key)
        # Nothing to do here, since the request is no longer there...
        return


def generate_requests(database):
    """Create requests to push expire_date for some accounts.

    warnable_accounts is a collection of account_ids that we want
    warned. However, not all of them should have a request generated, as some
    may already have a similar request.
    """
    warnable_accounts = set(collect_warnable_accounts(database))
    already_warned = set(collect_warned_accounts(database))

    clconst = Factory.get("CLConstants")()
    # Ok, we have the warnable set and the exception set. Let's go.
    # 'addresses' maps account_ids to the info pertaining to the warn request.
    addresses = dict()
    for account_id in warnable_accounts:
        attrs = account_id2attributes(account_id, database)
        if account_id in already_warned:
            logger.debug("Account %s (id=%s) has already been warned about "
                         "approaching expire date. No additional warnings "
                         "will be generated",
                         attrs.uname, account_id)
            continue

        if create_request(attrs, clconst.va_reset_expire_date, database):
            addresses[account_id] = attrs

    return addresses


def send_email(requests, dryrun, database):
    """Send 'confirm you are still alive' e-mails.
    """
    logger.debug("%d e-mails to dispatch", len(requests))

    for account_id in requests:
        attrs = requests[account_id]
        email = attrs.email
        uname = attrs.uname
        account_id = attrs.account_id
        magic_key = attrs.magic_key
        expire_date = attrs.expire_date.strftime("%Y-%m-%d")
        confirm_url = get_config("EXPIRE_CONFIRM_URL") + magic_key

        message = get_config("EXPIRE_MESSAGE_TEMPLATE") % {
            "uname": uname,
            "expire_date": expire_date,
            "url": confirm_url,
        }

        logger.debug("Generated a message for %s/%s (request key: %s). ",
                     uname, email, magic_key)
        if dryrun:
            logger.info("Message for %s/%s (request key: %s) will not be sent"
                        " (this is a dry run)",
                        uname, email, magic_key)
        else:
            try:
                sendmail(email,
                         get_config("EXPIRE_MESSAGE_SENDER"),
                         get_config("EXPIRE_MESSAGE_SUBJECT"),
                         message)
                logger.info("Message for %s/%s (request key: %s) sent",
                            uname, email, magic_key)
            except smtplib.SMTPRecipientsRefused as e:
                error = e.recipients.get(email)
                logger.warn("Failed to send message to %s/%s (SMTP %d: %s)",
                            uname, email, error[0], error[1])
                if error[0] == 550:
                    continue
                else:
                    cancel_request(attrs, database)
            except smtplib.SMTPException:
                logger.exception(
                    "Failed to send message to %s/%s", uname, email)
                cancel_request(attrs, database)


def get_account(ident, database):
    """Try to locate an account associated with L{ident}.

    @return:
      An account proxy associated with whatever ident points to, or None, if
      no account match is possible.
    """

    account = Factory.get("Account")(database)
    try:
        if (isinstance(ident, six.integer_types)
                or isinstance(ident, six.string_types) and ident.isdigit()):
            account.find(int(ident))
        else:
            account.find_by_name(ident)

        return account
    except Errors.NotFoundError:
        return None


def typeset_change_log_row(row, database):
    account = get_account(row["subject_entity"], database)
    clconst = Factory.get("CLConstants")()

    if account:
        entity = "account: %s/id=%s" % (account.account_name,
                                        account.entity_id)
    else:
        entity = "id=%s" % row["subject_entity"]

    if row.get("confirmation_key") is not None:
        magic = "with request key %s " % str(row["confirmation_key"])
    else:
        magic = ""

    return "Event %s %sregistered @ %s for %s%s" % (
        str(clconst.ChangeType(row["change_type_id"])),
        magic,
        row["tstamp"].strftime("%F %R"),
        entity,
        row["change_params"] is not None and
        ", params=%s." % repr(json.loads(row["change_params"])) or ".")


def show_requests(ident, database):
    """Show change_log requests associated with L{ident}.

    Display all information available about specific change_log entries.

    This is useful for maintenance tasks.

    @param ident:
      ... designates either an account or a request key. We'll try to guess
      what the user meant. If an account is specified, we display *ALL*
      change_log entries for that account. If a specific pending request is
      specified, we use _that_ particular id to locate a single change_log
      entry corresponding to a request (typically expire reset request)
    """
    account = get_account(ident, database)
    if account is not None:
        # Let's fish out the requests based on the account
        results = database.get_pending_events(subject_entity=account.entity_id)
    else:
        # assume that ident means a request key
        results = database.get_pending_events(confirmation_key=ident)

    if len(results) < 1:
        logger.debug("No expire reset request is associated with: %s. "
                     "Either no such account, or no such expire request key",
                     ident)
        return

    results.sort(key=lambda x: x["tstamp"])
    for row in results:
        logger.debug(typeset_change_log_row(row, database))


def send_expire_warning(ident, dryrun, database):
    """Send an expiration warning to a user, regardless of its expire_date
    status.

    This is useful in a situation if a scheduled warning failed for some
    reason or we want to preempt the scheduled warning for some reason.
    """
    account = get_account(ident, database)
    clconst = Factory.get("CLConstants")()
    if account is None:
        logger.debug("No account matches %s. No warning will be generated",
                     ident)
        return

    warned = set(collect_warned_accounts(database, account.entity_id))
    if account.entity_id in warned:
        logger.debug("Account %s (id=%s) has already been warned about "
                     "approaching expire date. No additional warnings "
                     "will be generated",
                     account.account_name, account.entity_id)
        return

    attrs = account_id2attributes(account.entity_id, database)
    addresses = dict()
    if create_request(attrs, clconst.va_reset_expire_date, database):
        addresses[account.entity_id] = attrs

    return send_email(addresses, dryrun, database)


def remove_request(ident, dryrun, database):
    """Remove va_reset_expire_date request for a specific user/magic key.

    This may come in handy if we have a stale request that bothers us/our
    automatic routines for some reason. It should not be run from cron, but
    rather be available as a tool for manual fixing of reset expire requests.
    """
    clconst = Factory.get("CLConstants")(database)
    account = get_account(ident, database)
    if account is not None:
        # Let's fish out the requests based on the account
        results = database.get_pending_events(
            subject_entity=account.entity_id,
            types=clconst.va_reset_expire_date)
    else:
        # assume that ident means a request key
        results = database.get_pending_events(confirmation_key=ident)

    if len(results) < 1:
        logger.debug(
            "No expire reset request matches search criteria: %s.", ident)
        return
    elif len(results) > 1:
        logger.debug("Multiple requests exist the same id: %s", str(ident))
        return

    request = results[0]
    logger.debug("Removing request %s",
                 typeset_change_log_row(request, database))
    database.remove_log_event(request["change_id"])


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Notify accounts that are about to expire",
    )
    parser.add_argument(
        '-d', '--dryrun', '--dry-run',
        dest='dryrun',
        action='store_true',
    )
    parser.add_argument(
        '--show-request',
        dest='display_requests',
        action='append',
    )
    parser.add_argument(
        '--send-expire-warning',
        dest='explicit_requests',
        action='append',
    )
    parser.add_argument(
        '--remove-request',
        dest='remove_requests',
        action='append',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('start %s', parser.prog)

    dryrun = args.dryrun
    logger.info('dryrun: %r', dryrun)

    display_requests = set(args.display_requests or ())
    logger.info('display_requests: %r', display_requests)

    explicit_requests = set(args.explicit_requests or ())
    logger.info('explicit_requests: %r', explicit_requests)

    remove_requests = set(args.remove_requests or ())
    logger.info('remove_requests: %r', remove_requests)

    database = Factory.get("Database")()
    database.cl_init(change_program="expire_notifier")

    if display_requests:
        for ident in display_requests:
            show_requests(ident, database)

    if explicit_requests:
        for ident in explicit_requests:
            send_expire_warning(ident, dryrun, database)

    if remove_requests:
        for ident in remove_requests:
            remove_request(ident, dryrun, database)

    # using --show-request, --send-expire-warning, or --remove-request negates
    # the default behaviour:
    if not any((display_requests, explicit_requests, remove_requests)):
        logger.info('collecting new expire notifications...')
        requests = generate_requests(database)
        logger.info('found %d new expire notifications to send', len(requests))
        send_email(requests, dryrun, database)

    if dryrun:
        logger.info("rolling back changes (dryrun)")
        database.rollback()
    else:
        logger.info("commiting changes")
        database.commit()

    logger.debug("Done %s", parser.prog)


if __name__ == "__main__":
    main()
