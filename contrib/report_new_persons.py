#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2018 University of Oslo, Norway
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
""" Report statistics about new persons in Cerebrum. """
import argparse
import logging

from mx.DateTime import now, ISO, RelativeDateTime
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.email import sendmail


logger = logging.getLogger(__name__)


def text_decoder(encoding, allow_none=True):
    def to_text(value):
        if allow_none and value is None:
            return None
        if isinstance(value, bytes):
            return value.decode(encoding)
        return text_type(value)
    return to_text


def get_new_persons(db, start_date, change_program=None):
    clconst = Factory.get('CLConstants')(db)
    pe_cls = Factory.get('Person')
    ac_cls = Factory.get('Account')
    u = text_decoder(db.encoding)

    log_events = [clconst.person_create]

    def get_person(person_id):
        pe = pe_cls(db)
        try:
            pe.find(person_id)
            return pe
        except Errors.NotFoundError:
            return None

    def get_account(account_id):
        ac = ac_cls(db)
        try:
            ac.clear()
            ac.find(account_id)
            return ac
        except Errors.NotFoundError:
            return None

    for row in db.get_log_events(sdate=start_date,
                                 types=log_events,
                                 change_program=change_program):
        logger.debug("New person: %s" % row['subject_entity'])
        pe = get_person(row['subject_entity'])
        if pe is None:
            logger.error("Couldn't find a person with entity_id=%r",
                         row['subject_entity'])
            continue

        account_name = None
        ac = get_account(pe.get_primary_account())
        if ac is not None:
            account_name = u(ac.account_name)

        yield pe.entity_id, account_name


def report_new_persons(new_persons):
    fields_fmt = u"{0:>10} {1}"
    yield u"New persons"
    yield u""
    yield fields_fmt.format('entity_id', 'account')
    yield fields_fmt.format(u'-' * len('entity_id'), u'-' * len('account'))
    for person_id, account_name in new_persons:
        yield fields_fmt.format(text_type(person_id), account_name or u'')


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)

    dryrun_arg = parser.add_argument(
        '-d', '--dryrun',
        dest='dryrun',
        action='store_true',
        default=False,
        help='Dry-run (do not send report email)')

    parser.add_argument(
        '-s', '--start-date',
        dest='start_date',
        type=ISO.ParseDate,
        default=now() + RelativeDateTime(days=-1),
        help='Start date (YYYY-MM-DD) for events,'
             ' defaults to %(default)s (1 day ago)')

    parser.add_argument(
        '-c', '--change-program',
        dest='change_program',
        help='Only get events for %(metavar)s')

    mail_to_arg = parser.add_argument(
        '-t', '--mail-to',
        dest='mail_to',
        metavar='ADDR',
        help="Send an email report to %(metavar)s")
    mail_from_arg = parser.add_argument(
        '-f', '--mail-from',
        dest='mail_from',
        metavar='ADDR',
        help="Send reports from %(metavar)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    # Require mail_to and mail_from, or neither
    if bool(args.mail_from) ^ bool(args.mail_to):
        apply_to = mail_to_arg if args.mail_to else mail_from_arg
        missing = mail_from_arg if args.mail_to else mail_to_arg
        parser.error(argparse.ArgumentError(
            apply_to,
            "Must set {0} as well".format('/'.join(missing.option_strings))))

    # Require mail_to or dryrun to be set
    if not any((args.mail_to, args.dryrun)):
        parser.error(argparse.ArgumentError(
            mail_to_arg,
            "Must set {0} if not sending mail".format(
                '/'.join(dryrun_arg.option_strings))))

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get('Database')()
    new_persons = list(
        get_new_persons(
            db,
            args.start_date,
            change_program=args.change_program))

    if args.change_program:
        subject = u'New persons from %s since %s' % (args.change_program,
                                                     args.start_date.date)
    else:
        subject = u'New persons since %s' % (args.start_date.date, )
    message = u'\n'.join(report_new_persons(new_persons))

    if new_persons:
        if args.mail_to and not args.dryrun:
            sendmail(args.mail_to, args.mail_from, subject, message)
            logger.info("Sent report to %s", args.mail_to)
        else:
            print("To: {0}".format(args.mail_to))
            print("From: {0}".format(args.mail_from))
            print("Subject: {0}".format(subject))
            print("")
            print(message)
    else:
        logger.info("Nothing to report")

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
