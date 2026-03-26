#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2026 University of Oslo, Norway""
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
Generate a report of person primary accounts and affiliations.

The report only includes persons with a given spread.  The report can be
written to a file (or stdout), or it can be sent by email using the Cerebrum
email templating system.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import email
import io
import logging
import smtplib
import textwrap

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import file_stream
from Cerebrum.utils.email import sendmail

logger = logging.getLogger(__name__)


class TemplateSender(object):
    """ Self contained email template sender. """

    def __init__(self, filename):
        with io.open(filename, mode="r", encoding="ascii") as f:
            self.msg = email.message_from_file(f)

    @property
    def template(self):
        return self.msg.get_payload(decode=1)

    def __call__(self, report):
        send_mail(
            self.msg['To'],
            self.msg['From'],
            self.msg['Subject'],
            self.template.replace('${REPORT}', report),
            self.msg['Cc'],
        )
        logger.info("Email sent to %s and %s (copy)",
                    self.msg['To'], self.msg['Cc'])


def get_location_codes(db):
    ou = Factory.get('OU')(db)
    for row in ou.get_stedkoder():
        location_code = ("%02d" * 3) % (row['fakultet'], row['institutt'],
                                        row['avdeling'])
        yield (row['ou_id'], location_code)


def get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def get_persons_with_spread(db, spread):
    """ Get person ids with the given *spread*. """
    pe = Factory.get("Person")(db)
    candidates = set(
        row['entity_id']
        for row in pe.list_all_with_spread(
            spreads=(int(spread),),
            entity_types=(int(pe.const.entity_person),),
        )
    )
    logger.debug("found %d candidates with spread %s", len(candidates), spread)
    return candidates


def get_report_data(db, person_ids):
    """ Get primary users and affiliations for the given persons. """
    pe = Factory.get('Person')(db)
    ac = Factory.get("Account")(db)

    stedkoder = dict(get_location_codes(db))

    def get_primary_username(pid):
        person_accounts = ac.list_accounts_by_owner_id(person_id)
        account_id = person_accounts[0]['account_id']
        account = get_account_by_id(db, account_id)
        return account.account_name

    def get_affiliations(pid):
        for row in pe.list_affiliations(person_id=int(pid)):
            yield "@".join((
                str(pe.const.PersonAffStatus(row['status'])),
                stedkoder[row['ou_id']],
            ))

    for person_id in person_ids:
        try:
            username = get_primary_username(person_id)
        except Exception:
            logger.warning("No primary account found for person id=%d",
                           person_id)
            continue

        affiliations = list(get_affiliations(person_id))

        yield (username, affiliations)


def format_report(items):
    def _generate_lines():
        for username, affiliations in sorted(items,
                                             key=lambda t: t[0]):
            yield "\t".join((username,) + tuple(affiliations))

    lines = list(_generate_lines())
    logger.debug("Prepared report with %d entries", len(lines))
    return "\n".join(lines) + "\n"


def write_report(filename, report):
    with file_stream.get_output_context(filename, encoding="utf-8") as f:
        f.write(report)
        logger.info("Wrote report to: %s", f)


def send_mail(mail_to, mail_from, subject, body, mail_cc=None):
    try:
        sendmail(mail_to, mail_from, subject, body, cc=mail_cc)
    except smtplib.SMTPRecipientsRefused as e:
        failed_recipients = e.recipients
        logger.error("Failed to send report <%d>", len(failed_recipients))
        for _, condition in failed_recipients.iteritems():
            logger.error("Failed to send report: %s", condition)
    except smtplib.SMTPException as msg:
        logger.error("Error sending to %s: %s" % (mail_to, msg))
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Generate a report of person primary accounts and affiliations.
            """
        ).strip(),
        epilog=textwrap.dedent(
            """
            FILE:
                An optional file where the report will be written.  Use '{}' to
                write report to stdout.

            TEMPLATE:
                An optional template for sending the report by email.

                This uses the legacy email template system in Cerebrum, where
                the template itself defines recipients in its email headers.
                The ${{REPORT}} template variable will be replaced with the
                report.  See Cerebrum.utils.email for more details on this
                templating system.

            Report:
                The report consists of the primary account username, and a list
                of affiliations, on format: `<username>[\\t<affiliation>...]`.

                Example:

                    foo<tab>ANSATT@900000<tab>STUDENT@900000
                    bar<tab>TILKNYTTET@900000
            """
        ).strip().format(file_stream.DEFAULT_STDOUT_NAME),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    spread_arg = parser.add_argument(
        "-s", "--spread",
        required=True,
        help="Only include persons with spread %(metavar)s (required)",
        metavar="SPREAD",
    )
    parser.add_argument(
        "-f", "--file",
        dest="filename",
        help="Write report to %(metavar)s",
        metavar="FILE",
    )
    parser.add_argument(
        "-m", "--mail",
        dest="template",
        help="Send report by email using template %(metavar)s",
        metavar="TEMPLATE",
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("cronjob", args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    # Check and prepare arguments

    if not any((args.filename, args.template)):
        parser.error("Missing template or report file")

    spread = argutils.get_constant(db, parser, co.Spread,
                                   args.spread, spread_arg)
    logger.debug("using person spread: %s", spread)

    send_report = None
    if args.template:
        send_report = TemplateSender(args.template)
        logger.debug("read email template: %s", repr(args.template))

    filename = args.filename
    if filename:
        logger.debug("writing report to: %s", repr(filename))

    # Generate and write report

    candidates = get_persons_with_spread(db, spread)
    report_data = list(get_report_data(db, candidates))
    report = format_report(report_data)

    if send_report:
        send_report(report)

    if filename:
        write_report(filename, report)

    logger.info("Done %s", parser.prog)


if __name__ == "__main__":
    main()
